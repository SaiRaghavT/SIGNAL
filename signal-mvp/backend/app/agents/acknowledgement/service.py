from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.submissions import Submission

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

        submission.warnings = list(
            submission.warnings or []
        )

        submission.warnings.append(
            "Acknowledgement is simulated; "
            "no real PHA response received."
        )

        db.commit()
        db.refresh(submission)

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
