from sqlalchemy.orm import Session
from dataclasses import asdict
import json
from uuid import uuid4

from backend.app.ecr.builder import build_ecr
from backend.app.config.settings import settings
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.service import submit_ecr
from backend.app.submission.gates import smart_fields_for_case

from .schemas import (
    ECRSubmissionRequest,
    ECRSubmissionResponse,
)


class ECRSubmissionService:

    def submit(
        self,
        request: ECRSubmissionRequest,
        db: Session,
        *,
        local_demo: bool = False,
    ) -> ECRSubmissionResponse:

        # ---------------------------------------------------------
        # 1. Load persisted case
        # ---------------------------------------------------------
        case = (
            db.query(Case)
            .filter(
                Case.case_id == request.case_id
            )
            .with_for_update()
            .first()
        )

        if case is None:
            raise ValueError(
                f"Case not found: {request.case_id}"
            )

        existing = (
            db.query(Submission)
            .filter(Submission.case_id == str(case.case_id))
            .order_by(Submission.created_at.desc())
            .first()
        )
        if existing and (existing.status or "").upper() in {"SUBMITTED", "ACKNOWLEDGED", "ACCEPTED"}:
            raise ValueError(f"Case already has a successful submission ({existing.submission_id}).")
        queue = (
            db.query(CaseWorkflowRecord)
            .filter(
                CaseWorkflowRecord.case_id == str(case.case_id),
                CaseWorkflowRecord.record_type == "ADMIN_QUEUE",
            )
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )
        if local_demo and (
            not settings.demo_queue_enabled
            or queue is None
            or not (queue.payload or {}).get("demo_submission")
        ):
            raise ValueError("Local PHA submission is only available for an enabled demo-queued case.")

        # ---------------------------------------------------------
        # 2. Build ECR from the persisted case
        # ---------------------------------------------------------
        ecr = build_ecr(case)

        report = (
            db.query(Report)
            .filter(Report.case_id == str(case.case_id), Report.status == "GENERATED")
            .order_by(Report.created_at.desc())
            .first()
        )
        if report is None:
            raise ValueError("A generated report is required before submission.")
        review = (
            db.query(CaseWorkflowRecord)
            .filter(CaseWorkflowRecord.case_id == str(case.case_id), CaseWorkflowRecord.record_type == "REVIEW")
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )
        if review is None or str(review.status or "").upper() not in {"APPROVE", "APPROVED"}:
            raise ValueError("An approved review is required before submission.")
        if local_demo:
            # The demo approval is valid only for this local Mock PHA handoff.
            # It does not modify the persisted case or authorize external reporting.
            ecr.status = "REPORT"

        # ---------------------------------------------------------
        # 3. Validate ECR
        # ---------------------------------------------------------
        validation = validate_ecr(ecr, smart_fields_for_case(case))

        # ---------------------------------------------------------
        # 4. Submit using existing submission service
        # ---------------------------------------------------------
        result = submit_ecr(
            ecr,
            validation,
            reviewed=True,
        )

        # ---------------------------------------------------------
        # 5. Persist submission
        # ---------------------------------------------------------
        ecr_payload = json.loads(json.dumps(asdict(ecr), default=str))
        ecr_payload["report_form"] = {
            "report_id": report.report_id,
            "form_id": report.form_id,
            "form_version": report.form_version,
            "document_url": (
                f"/api/agents/form-rendering/{report.render_id}"
                if report.render_id else None
            ),
        }
        submission = Submission(
            # Submission IDs identify attempts. The ECR ID remains stable for
            # a case, so it cannot also serve as the primary key on resubmits.
            submission_id=f"SUB-{uuid4()}",
            case_id=str(case.case_id),
            submission_mode=case.submission_mode,
            report_id=report.report_id,
            ecr_id=ecr.ecr_id,
            channel="eCR",
            destination=result.destination,
            status=result.status,
            errors=result.errors,
            warnings=result.warnings,
            ecr_payload=ecr_payload,
        )

        db.add(submission)
        db.commit()
        db.refresh(submission)
        AuditLedgerService().record_event(
            AuditEventCreate(
                entity_type="CASE",
                entity_id=str(case.case_id),
                event_type="SUBMITTED",
                actor_type="USER",
                actor_id=request.submitted_by,
                source_agent="ecr_submission",
                status=submission.status,
                new_value={"submission_id": submission.submission_id, "destination": submission.destination, "batch_id": request.batch_id},
                workflow_stage="SUBMISSION",
            ),
            db,
        )

        # ---------------------------------------------------------
        # 6. Return API response
        # ---------------------------------------------------------
        return ECRSubmissionResponse(
            case_id=str(case.case_id),
            submission_mode=submission.submission_mode,
            report_id=report.report_id,
            ecr_id=ecr.ecr_id,
            submission_id=submission.submission_id,
            status=submission.status,
            destination=submission.destination,
            errors=submission.errors,
            warnings=submission.warnings,
        )
