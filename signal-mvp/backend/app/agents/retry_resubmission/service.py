from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.submissions import Submission

from .schemas import (
    RetryResubmissionRequest,
    RetryResubmissionResponse,
)


class RetryResubmissionService:

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
        errors = []

        # ---------------------------------------------------------
        # Only failed/rejected submissions can be retried
        # ---------------------------------------------------------
        retryable_statuses = {
            "REJECTED",
            "FAILED",
            "ERROR",
        }

        if submission.status not in retryable_statuses:
            return RetryResubmissionResponse(
                submission_id=submission.submission_id,
                case_id=submission.case_id,
                ecr_id=submission.ecr_id,
                status="NOT_ELIGIBLE",
                retry_count=0,
                new_submission_id=None,
                errors=[
                    f"Submission status "
                    f"'{submission.status}' "
                    f"is not eligible for retry."
                ],
                warnings=warnings,
            )

        # ---------------------------------------------------------
        # Create a new submission ID
        # ---------------------------------------------------------
        new_submission_id = f"SUB-RETRY-{uuid4()}"

        retry_submission = Submission(
            submission_id=new_submission_id,
            case_id=submission.case_id,
            ecr_id=submission.ecr_id,
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
        )

        db.add(retry_submission)
        db.commit()
        db.refresh(retry_submission)

        return RetryResubmissionResponse(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            ecr_id=submission.ecr_id,
            status="RESUBMITTED",
            retry_count=1,
            new_submission_id=new_submission_id,
            errors=errors,
            warnings=retry_submission.warnings,
        )
