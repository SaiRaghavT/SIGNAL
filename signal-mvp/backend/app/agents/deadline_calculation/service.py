from calendar import monthrange
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.rules.resolver import RuleResolutionError, resolve_rule
from .schemas import (
    DeadlineCalculationRequest,
    DeadlineCalculationResponse,
)


class DeadlineCalculationService:

    @staticmethod
    def _add_work_days(event_time: datetime, value: int) -> datetime:
        """Add weekdays while preserving local time and timezone."""
        deadline = event_time
        remaining = value
        while remaining:
            deadline += timedelta(days=1)
            if deadline.weekday() < 5:
                remaining -= 1
        return deadline

    @staticmethod
    def _add_calendar_months(event_time: datetime, value: int) -> datetime:
        month_index = event_time.month - 1 + value
        year = event_time.year + month_index // 12
        month = month_index % 12 + 1
        day = min(event_time.day, monthrange(year, month)[1])
        return event_time.replace(year=year, month=month, day=day)

    def _load_rule(
        self,
        disease: str,
        jurisdiction: str,
        rule_id: str | None,
    ) -> dict:

        try:
            return resolve_rule(disease, jurisdiction, rule_id)
        except RuleResolutionError as exc:
            raise ValueError(str(exc)) from exc

    def calculate(
        self,
        request: DeadlineCalculationRequest,
        db: Session | None = None,
    ) -> DeadlineCalculationResponse:

        rule = self._load_rule(
            disease=request.disease,
            jurisdiction=request.jurisdiction,
            rule_id=request.rule_id,
        )

        reporting = rule.get("reporting", {})

        timing = str(
            reporting.get("timing", "")
        ).upper()

        method = str(
            reporting.get("method", "")
        ).upper()

        if timing == "IMMEDIATE":
            deadline = request.event_time

            calculation_basis = (
                "Immediate reporting required by "
                f"rule {rule.get('rule_id')}."
            )

        elif timing == "MINUTES":
            value = reporting.get("value")

            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    "Reporting rule must contain a "
                    "positive integer 'value' for MINUTES."
                )

            deadline = (
                request.event_time
                + timedelta(minutes=value)
            )

            calculation_basis = (
                f"{value} minutes from event time "
                f"per rule {rule.get('rule_id')}."
            )

        elif timing == "HOURS":
            value = reporting.get("value")

            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    "Reporting rule must contain a "
                    "positive integer 'value' for HOURS."
                )

            deadline = (
                request.event_time
                + timedelta(hours=value)
            )

            calculation_basis = (
                f"{value} hours from event time "
                f"per rule {rule.get('rule_id')}."
            )

        elif timing == "DAYS":
            value = reporting.get("value")

            if not isinstance(value, int) or value <= 0:
                raise ValueError(
                    "Reporting rule must contain a "
                    "positive integer 'value' for DAYS."
                )

            deadline = (
                request.event_time
                + timedelta(days=value)
            )

            calculation_basis = (
                f"{value} days from event time "
                f"per rule {rule.get('rule_id')}."
            )

        elif timing == "WORK_DAYS":
            value = reporting.get("value")

            if type(value) is not int or value <= 0:
                raise ValueError(
                    "Reporting rule must contain a positive integer 'value' for WORK_DAYS."
                )

            deadline = self._add_work_days(request.event_time, value)
            calculation_basis = (
                f"{value} work day(s) from event time per rule {rule.get('rule_id')}; "
                "weekends are skipped, but public holidays are not modeled."
            )

        elif timing == "MONTHS":
            value = reporting.get("value")

            if type(value) is not int or value <= 0:
                raise ValueError(
                    "Reporting rule must contain a positive integer 'value' for MONTHS."
                )

            deadline = self._add_calendar_months(request.event_time, value)
            calculation_basis = (
                f"{value} calendar month(s) from event time "
                f"per rule {rule.get('rule_id')}."
            )

        elif timing == "SEE_RULES":
            instructions = reporting.get("destination") or reporting.get("timeline_text")
            raise ValueError(
                "The reporting catalog refers to condition-specific rules; "
                f"a numeric deadline is not configured ({instructions})."
            )

        else:
            raise ValueError(
                f"Unsupported reporting timing: {timing}"
            )

        minutes_remaining = int(
            (deadline - datetime.now(timezone.utc)).total_seconds() / 60
        )
        if minutes_remaining <= 4 * 60:
            urgency = "CRITICAL"
        elif minutes_remaining <= 24 * 60:
            urgency = "HIGH"
        elif minutes_remaining <= 72 * 60:
            urgency = "MEDIUM"
        else:
            urgency = "LOW"

        if db is not None and request.candidate_id:
            candidate = (
                db.query(Candidate)
                .filter(Candidate.candidate_id == request.candidate_id)
                .first()
            )
            if candidate is None:
                raise ValueError(f"Candidate not found: {request.candidate_id}")
            candidate.deadline = deadline
            candidate.severity = urgency

        if db is not None and request.case_id:
            try:
                case_uuid = UUID(request.case_id)
            except ValueError as exc:
                raise ValueError(f"Invalid case ID: {request.case_id}") from exc
            case = db.query(Case).filter(Case.case_id == case_uuid).first()
            if case is None:
                raise ValueError(f"Case not found: {request.case_id}")
            case.deadline = deadline
            case.severity = urgency

        if db is not None and (request.candidate_id or request.case_id):
            db.commit()

        return DeadlineCalculationResponse(
            deadline=deadline,
            calculation_basis=calculation_basis,
            status="CALCULATED",
            disease=request.disease,
            jurisdiction=request.jurisdiction,
            rule_id=rule.get("rule_id"),
            reporting_timing=timing,
            reporting_timeline=reporting.get("timeline_text"),
            reporting_method=method,
            urgency=urgency,
            minutes_remaining=minutes_remaining,
        )
