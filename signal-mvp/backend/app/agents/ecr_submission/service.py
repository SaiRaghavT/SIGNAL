from sqlalchemy.orm import Session

from backend.app.ecr.builder import build_ecr
from backend.app.models.case import Case
from backend.app.models.submissions import Submission
from backend.app.schemas.validation import validate_ecr
from backend.app.submission.service import submit_ecr

from .schemas import (
    ECRSubmissionRequest,
    ECRSubmissionResponse,
)


class ECRSubmissionService:

    def submit(
        self,
        request: ECRSubmissionRequest,
        db: Session,
    ) -> ECRSubmissionResponse:

        # ---------------------------------------------------------
        # 1. Load persisted case
        # ---------------------------------------------------------
        case = (
            db.query(Case)
            .filter(
                Case.case_id == request.case_id
            )
            .first()
        )

        if case is None:
            raise ValueError(
                f"Case not found: {request.case_id}"
            )

        # ---------------------------------------------------------
        # 2. Build ECR from the persisted case
        # ---------------------------------------------------------
        ecr = build_ecr(case)

        # ---------------------------------------------------------
        # 3. Validate ECR
        # ---------------------------------------------------------
        validation = validate_ecr(ecr)

        # ---------------------------------------------------------
        # 4. Submit using existing submission service
        # ---------------------------------------------------------
        result = submit_ecr(
            ecr,
            validation,
        )

        # ---------------------------------------------------------
        # 5. Persist submission
        # ---------------------------------------------------------
        submission = Submission(
            submission_id=result.submission_id,
            case_id=str(case.case_id),
            ecr_id=ecr.ecr_id,
            destination=result.destination,
            status=result.status,
            errors=result.errors,
            warnings=result.warnings,
        )

        db.add(submission)
        db.commit()
        db.refresh(submission)

        # ---------------------------------------------------------
        # 6. Return API response
        # ---------------------------------------------------------
        return ECRSubmissionResponse(
            case_id=str(case.case_id),
            ecr_id=ecr.ecr_id,
            submission_id=submission.submission_id,
            status=submission.status,
            destination=submission.destination,
            errors=submission.errors,
            warnings=submission.warnings,
        )
