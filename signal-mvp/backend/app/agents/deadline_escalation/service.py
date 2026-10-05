from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.deadline_escalation import DeadlineEscalation

from .schemas import (
    DeadlineEscalationRequest,
    DeadlineEscalationResponse,
)


class DeadlineEscalationService:

    def evaluate(
        self,
        request: DeadlineEscalationRequest,
        db: Session,
    ) -> DeadlineEscalationResponse:

        current_time = request.current_time

        if current_time is None:
            current_time = datetime.now(timezone.utc)

        if current_time.tzinfo is None:
            current_time = current_time.replace(
                tzinfo=timezone.utc
            )

        deadline = request.deadline

        if deadline.tzinfo is None:
            deadline = deadline.replace(
                tzinfo=timezone.utc
            )

        difference = deadline - current_time

        minutes_remaining = int(
            difference.total_seconds() / 60
        )

        if minutes_remaining < 0:
            status = "OVERDUE"
            escalation_required = True

            message = (
                f"Reporting deadline is overdue by "
                f"{abs(minutes_remaining)} minutes."
            )

        elif minutes_remaining <= request.warning_window_minutes:
            status = "UPCOMING"
            escalation_required = True

            message = (
                f"Reporting deadline is approaching. "
                f"{minutes_remaining} minutes remaining."
            )

        else:
            status = "WITHIN_WINDOW"
            escalation_required = False

            message = (
                f"Reporting deadline is not yet approaching. "
                f"{minutes_remaining} minutes remaining."
            )

        escalation = DeadlineEscalation(
            escalation_id=f"ESC-{uuid4()}",
            case_id=request.case_id,
            status=status,
            escalation_required=escalation_required,
            minutes_remaining=minutes_remaining,
            deadline=deadline,
            message=message,
            jurisdiction=request.jurisdiction,
            rule_id=request.rule_id,
        )

        db.add(escalation)
        db.commit()
        db.refresh(escalation)

        return DeadlineEscalationResponse(
            escalation_id=escalation.escalation_id,
            case_id=escalation.case_id,
            status=escalation.status,
            escalation_required=escalation.escalation_required,
            minutes_remaining=escalation.minutes_remaining,
            deadline=escalation.deadline,
            message=escalation.message,
            jurisdiction=escalation.jurisdiction,
            rule_id=escalation.rule_id,
        )