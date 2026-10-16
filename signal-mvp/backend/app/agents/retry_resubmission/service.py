from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.submissions import Submission
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord, Report, SubmissionAttempt
from backend.app.ecr.builder import build_ecr
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.gates import case_has_current_attestation, smart_fields_for_case
from backend.app.submission.service import submit_ecr

from .schemas import (
    RetryResubmissionRequest,
    RetryResubmissionResponse,
)


class RetryResubmissionService:
    @staticmethod
    def _record_blocked_attempt(
        db: Session,
        request: RetryResubmissionRequest,
        submission: Submission,
        retry_count: int,
        error: str,
    ) -> RetryResubmissionResponse:
        db.add(
            SubmissionAttempt(
                original_submission_id=submission.submission_id,
                attempt_number=retry_count,
                reason=request.reason,
                status="BLOCKED",
            )
        )
        db.commit()
        return RetryResubmissionResponse(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            ecr_id=submission.ecr_id,
            status="BLOCKED",
            retry_count=retry_count,
            new_submission_id=None,
            errors=[error],
            warnings=list(submission.warnings or []),
        )

    def retry(
        self,
        request: RetryResubmissionRequest,
        db: Session,
    ) -> RetryResubmissionResponse:

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

        warnings = list(submission.warnings or [])
        retry_count = (
            db.query(SubmissionAttempt)
            .filter(SubmissionAttempt.original_submission_id == submission.submission_id)
            .count()
            + 1
        )

        # ---------------------------------------------------------
        # Only failed/rejected submissions can be retried
        # ---------------------------------------------------------
        retryable_statuses = {
            "REJECTED",
            "FAILED",
            "ERROR",
        }

        if (submission.status or "").upper() not in retryable_statuses:
            db.add(SubmissionAttempt(
                original_submission_id=submission.submission_id,
                attempt_number=retry_count,
                reason=request.reason,
                status="NOT_ELIGIBLE",
            ))
            db.commit()
            return RetryResubmissionResponse(
                submission_id=submission.submission_id,
                case_id=submission.case_id,
                ecr_id=submission.ecr_id,
                status="NOT_ELIGIBLE",
                retry_count=retry_count,
                new_submission_id=None,
                errors=[
                    f"Submission status "
                    f"'{submission.status}' "
                    f"is not eligible for retry."
                ],
                warnings=warnings,
            )

        active_attempt = (
            db.query(SubmissionAttempt)
            .filter(
                SubmissionAttempt.original_submission_id == submission.submission_id,
                SubmissionAttempt.new_submission_id.is_not(None),
            )
            .order_by(SubmissionAttempt.created_at.desc())
            .first()
        )
        if active_attempt is not None and active_attempt.new_submission_id:
            active_submission = (
                db.query(Submission)
                .filter(Submission.submission_id == active_attempt.new_submission_id)
                .first()
            )
            if active_submission and (active_submission.status or "").upper() in {
                "SUBMITTED",
                "ACKNOWLEDGED",
            }:
                return RetryResubmissionResponse(
                    submission_id=submission.submission_id,
                    case_id=submission.case_id,
                    ecr_id=submission.ecr_id,
                    status="RESUBMITTED",
                    retry_count=active_attempt.attempt_number,
                    new_submission_id=active_submission.submission_id,
                    errors=[],
                    warnings=list(active_submission.warnings or []),
                )

        case = db.query(Case).filter(Case.case_id == submission.case_id).first()
        if case is None:
            return self._record_blocked_attempt(
                db,
                request,
                submission,
                retry_count,
                "The persisted case for this submission was not found.",
            )

        report = (
            db.query(Report)
            .filter(
                Report.report_id == submission.report_id,
                Report.status == "GENERATED",
            )
            .first()
        )
        if report is None:
            return self._record_blocked_attempt(
                db,
                request,
                submission,
                retry_count,
                "A generated report is required before retrying submission.",
            )

        review = (
            db.query(CaseWorkflowRecord)
            .filter(
                CaseWorkflowRecord.case_id == submission.case_id,
                CaseWorkflowRecord.record_type == "REVIEW",
            )
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )
        if review is None or review.status != "APPROVE":
            return self._record_blocked_attempt(
                db,
                request,
                submission,
                retry_count,
                "An approved review is required before retrying submission.",
            )

        attestation = (
            db.query(CaseWorkflowRecord)
            .filter(
                CaseWorkflowRecord.case_id == submission.case_id,
                CaseWorkflowRecord.record_type == "ATTESTATION",
            )
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )
        if attestation is None or attestation.status != "ATTESTED":
            return self._record_blocked_attempt(
                db,
                request,
                submission,
                retry_count,
                "A persisted attestation is required before retrying submission.",
            )

        ecr = build_ecr(case)
        validation = validate_ecr(ecr, smart_fields_for_case(case))
        gate = submit_ecr(
            ecr,
            validation,
            attested=case_has_current_attestation(db, case),
        )
        if gate.status != "SUBMITTED":
            return self._record_blocked_attempt(
                db,
                request,
                submission,
                retry_count,
                "; ".join(gate.errors) or "Submission validation did not pass.",
            )

        # ---------------------------------------------------------
        # Create a new submission ID
        # ---------------------------------------------------------
        new_submission_id = f"SUB-RETRY-{uuid4()}"

        retry_submission = Submission(
            submission_id=new_submission_id,
            case_id=submission.case_id,
            submission_mode=getattr(case, "submission_mode", None),
            report_id=submission.report_id,
            ecr_id=submission.ecr_id,
            channel=submission.channel,
            destination=submission.destination,
            status="SUBMITTED",
            errors=[],
            warnings=[
                *warnings,
                "Submission created through "
                "retry/resubmission workflow.",
                "Resubmission is simulated; "
                "no real PHA transmission occurred.",
            ],
            ecr_payload=submission.ecr_payload or {},
        )

        db.add(retry_submission)
        db.add(SubmissionAttempt(
            original_submission_id=submission.submission_id,
            new_submission_id=new_submission_id,
            attempt_number=retry_count,
            reason=request.reason,
            status="SUBMITTED",
        ))
        db.commit()
        db.refresh(retry_submission)

        return RetryResubmissionResponse(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            ecr_id=submission.ecr_id,
            status="RESUBMITTED",
            retry_count=retry_count,
            new_submission_id=new_submission_id,
            errors=[],
            warnings=retry_submission.warnings,
        )
