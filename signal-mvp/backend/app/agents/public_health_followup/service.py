from datetime import datetime, time, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
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
            raise ValueError(f"Unsupported follow-up action: {action}")

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
            submission_id=request.submission_id,
            patient_id=str((case.patient or {}).get("patient_id") or (case.patient or {}).get("id") or "") or None,
            disease=case.disease,
            next_action=request.next_action,
            due_date=(
                datetime.combine(request.due_date, time.min, tzinfo=timezone.utc)
                if request.due_date
                else None
            ),
        )

        db.add(follow_up)
        db.commit()
        db.refresh(follow_up)
        AuditLedgerService().record_event(
            AuditEventCreate(
                entity_type="CASE",
                entity_id=str(case.case_id),
                event_type="FOLLOW_UP_CREATED",
                actor_type="SYSTEM",
                actor_id="SIGNAL",
                source_agent="public_health_followup",
                status=follow_up.status,
                new_value={"followup_id": followup_id, "action": action},
                workflow_stage="PHA_FOLLOW_UP",
            ),
            db,
        )

        # ---------------------------------------------------------
        # 6. Return follow-up response
        # ---------------------------------------------------------
        return PublicHealthFollowupResponse(
            case_id=str(case.case_id),
            status=follow_up.status,
            action=follow_up.action,
            followup_id=follow_up.followup_id,
            notes=follow_up.notes,
            submission_id=follow_up.submission_id,
            patient_id=follow_up.patient_id,
            disease=follow_up.disease,
            next_action=follow_up.next_action,
            due_date=follow_up.due_date.date() if follow_up.due_date else None,
            errors=[],
            warnings=[
                "Public health follow-up is simulated; "
                "no real PHA action was performed."
            ],
        )