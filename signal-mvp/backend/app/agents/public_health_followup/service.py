from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.follow_up import FollowUp

from .schemas import (
    PublicHealthFollowupRequest,
    PublicHealthFollowupResponse,
)


class PublicHealthFollowupService:

    ALLOWED_ACTIONS = {
        "REQUEST_INFORMATION",
        "INVESTIGATION",
        "OUTCOME_UPDATE",
        "CLOSE",
    }

    def process(
        self,
        request: PublicHealthFollowupRequest,
        db: Session,
    ) -> PublicHealthFollowupResponse:

        # ---------------------------------------------------------
        # 1. Find the persisted case
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
        # 2. Validate follow-up action
        # ---------------------------------------------------------
        action = request.action.upper().strip()

        if action not in self.ALLOWED_ACTIONS:
            return PublicHealthFollowupResponse(
                case_id=str(case.case_id),
                status="INVALID_ACTION",
                action=action,
                followup_id="",
                notes=request.notes,
                errors=[
                    f"Unsupported follow-up action: {action}"
                ],
                warnings=[],
            )

        # ---------------------------------------------------------
        # 3. Generate follow-up tracking ID
        # ---------------------------------------------------------
        followup_id = f"FOLLOWUP-{uuid4()}"

        # ---------------------------------------------------------
        # 4. Determine workflow status
        # ---------------------------------------------------------
        if action == "CLOSE":
            status = "CLOSED"
        else:
            status = "FOLLOWUP_PENDING"

        # ---------------------------------------------------------
        # 5. Persist follow-up record
        # ---------------------------------------------------------
        follow_up = FollowUp(
            followup_id=followup_id,
            case_id=str(case.case_id),
            action=action,
            status=status,
            notes=request.notes,
        )

        db.add(follow_up)
        db.commit()
        db.refresh(follow_up)

        # ---------------------------------------------------------
        # 6. Return follow-up response
        # ---------------------------------------------------------
        return PublicHealthFollowupResponse(
            case_id=str(case.case_id),
            status=follow_up.status,
            action=follow_up.action,
            followup_id=follow_up.followup_id,
            notes=follow_up.notes,
            errors=[],
            warnings=[
                "Public health follow-up is simulated; "
                "no real PHA action was performed."
            ],
        )