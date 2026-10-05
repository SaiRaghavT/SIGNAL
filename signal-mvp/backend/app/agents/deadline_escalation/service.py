from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.agents.deadline_calculation.service import DeadlineCalculationService

from .schemas import (
    DeadlineEscalationRequest,
    DeadlineEscalationResponse,
)


class DeadlineEscalationService:

    def evaluate_current_state(
        self,
        deadline: datetime,
        rule: dict,
        *,
        current_time: datetime | None = None,
        warning_window_minutes: int | None = None,
    ) -> dict:
        """Evaluate a deadline with the same rules used by case escalations, without persisting an event."""
        current_time = current_time or datetime.now(timezone.utc)
        if current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)

        minutes_remaining = int((deadline - current_time).total_seconds() / 60)
        window = warning_window_minutes
        if window is None:
            window = int(rule.get("severity_warning_minutes", 60))

        reporting = rule.get("reporting", {})
        timing = str(reporting.get("timing", "")).upper()
        value = reporting.get("value")
        minutes_per_unit = {"MINUTES": 1, "HOURS": 60, "DAYS": 1440}
        rule_window_minutes = (
            int(value) * minutes_per_unit[timing]
            if timing in minutes_per_unit and isinstance(value, int)
            else 0
        )

        if minutes_remaining < 0:
            status = "OVERDUE"
            escalation_required = True
            message = f"Reporting deadline is overdue by {abs(minutes_remaining)} minutes."
            urgency = "CRITICAL"
        elif minutes_remaining <= window:
            status = "UPCOMING"
            escalation_required = True
            message = f"Reporting deadline is approaching. {minutes_remaining} minutes remaining."
            urgency = "HIGH"
        else:
            status = "WITHIN_WINDOW"
            escalation_required = False
            message = f"Reporting deadline is not yet approaching. {minutes_remaining} minutes remaining."
            urgency = "MEDIUM" if minutes_remaining <= rule_window_minutes else "LOW"

        return {
            "status": status,
            "urgency": urgency,
            "escalation_required": escalation_required,
            "minutes_remaining": minutes_remaining,
            "deadline": deadline,
            "message": message,
        }

    def evaluate(
        self,
        request: DeadlineEscalationRequest,
        db: Session,
    ) -> DeadlineEscalationResponse:

        deadline = request.deadline
        try:
            from uuid import UUID

            case_uuid = UUID(request.case_id)
        except ValueError as exc:
            raise ValueError(f"Invalid case ID: {request.case_id}") from exc
        case = db.query(Case).filter(Case.case_id == case_uuid).first()
        if case is None:
            raise ValueError(f"Case not found: {request.case_id}")
        rule = DeadlineCalculationService()._load_rule(
            disease=case.disease or "",
            jurisdiction=request.jurisdiction or case.jurisdiction or "",
            rule_id=request.rule_id or case.rule_id,
        )
        state = self.evaluate_current_state(
            deadline,
            rule,
            current_time=request.current_time,
            warning_window_minutes=request.warning_window_minutes,
        )
        case.deadline = state["deadline"]
        case.severity = state["urgency"]

        escalation = DeadlineEscalation(
            escalation_id=f"ESC-{uuid4()}",
            case_id=request.case_id,
            status=state["status"],
            escalation_required=state["escalation_required"],
            minutes_remaining=state["minutes_remaining"],
            deadline=state["deadline"],
            message=state["message"],
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
            urgency=state["urgency"],
            escalation_required=escalation.escalation_required,
            minutes_remaining=escalation.minutes_remaining,
            deadline=escalation.deadline,
            message=escalation.message,
            jurisdiction=escalation.jurisdiction,
            rule_id=escalation.rule_id,
        )
