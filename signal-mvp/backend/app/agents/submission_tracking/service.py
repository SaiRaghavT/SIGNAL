from sqlalchemy.orm import Session

from backend.app.models.submissions import Submission

from .schemas import (
    SubmissionTrackingRequest,
    SubmissionTrackingResponse,
)


class SubmissionTrackingService:

    def track(
        self,
        request: SubmissionTrackingRequest,
        db: Session,
    ) -> SubmissionTrackingResponse:

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

        return SubmissionTrackingResponse(
            submission_id=submission.submission_id,
            case_id=submission.case_id,
            ecr_id=submission.ecr_id,
            status=submission.status,
            destination=submission.destination,
            errors=submission.errors or [],
            warnings=submission.warnings or [],
        )
