from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.models.submissions import Submission
from backend.app.models.workflow_records import Acknowledgement

from .schemas import (
    AcknowledgementRequest,
    AcknowledgementResponse,
)


class AcknowledgementService:

    def process_acknowledgement(
        self,
        request: AcknowledgementRequest,
        db: Session,
    ) -> AcknowledgementResponse:

        # ---------------------------------------------------------
        # 1. Find persisted submission
        # ---------------------------------------------------------
        submission = (
            db.query(Submission)
            .filter(
                Submission.submission_id
                == request.submission_id
            )
            .first()
        )

        if submission is None:
            raise ValueError(
                f"Submission not found: "
                f"{request.submission_id}"
            )

        # ---------------------------------------------------------
        # 2. Only submitted ECRs can receive an ACK
        # ---------------------------------------------------------
        if submission.status != "SUBMITTED":
            return AcknowledgementResponse(
                submission_id=submission.submission_id,
                ecr_id=submission.ecr_id,
                acknowledgement_id=None,
                pha_case_id=None,
                status="NOT_ELIGIBLE",
                errors=[
                    "Only a SUBMITTED submission "
                    "can receive an acknowledgement."
                ],
                warnings=[],
            )

        # ---------------------------------------------------------
        # 3. Generate mock acknowledgement identifiers
        # ---------------------------------------------------------
        acknowledgement_id = (
            f"ACK-{uuid4()}"
        )

        pha_case_id = (
            f"PHA-{uuid4()}"
        )

        # ---------------------------------------------------------
        # 4. Update submission status
        # ---------------------------------------------------------
        submission.status = "ACKNOWLEDGED"
        submission.acknowledgement_id = acknowledgement_id
        submission.pha_case_id = pha_case_id

        submission.warnings = list(
            submission.warnings or []
        )

        submission.warnings.append(
            "Acknowledgement is simulated; "
            "no real PHA response received."
        )

        acknowledgement = Acknowledgement(
            acknowledgement_id=acknowledgement_id,
            submission_id=submission.submission_id,
            pha_id=pha_case_id,
            status="ACKNOWLEDGED",
            response={"simulated": True, "status": "ACKNOWLEDGED"},
            errors=[],
        )
        db.add(acknowledgement)
        db.commit()
        db.refresh(submission)
        AuditLedgerService().record_event(
            AuditEventCreate(
                entity_type="SUBMISSION",
                entity_id=submission.submission_id,
                event_type="ACKNOWLEDGED",
                actor_type="SYSTEM",
                actor_id="SIGNAL",
                source_agent="acknowledgement",
                status="SIMULATED",
                new_value={"acknowledgement_id": acknowledgement_id, "pha_case_id": pha_case_id},
                workflow_stage="ACKNOWLEDGEMENT",
            ),
            db,
        )

        # ---------------------------------------------------------
        # 5. Return acknowledgement
        # ---------------------------------------------------------
        return AcknowledgementResponse(
            submission_id=submission.submission_id,
            ecr_id=submission.ecr_id,
            acknowledgement_id=acknowledgement_id,
            pha_case_id=pha_case_id,
            status="ACKNOWLEDGED",
            errors=[],
            warnings=submission.warnings,
        )
