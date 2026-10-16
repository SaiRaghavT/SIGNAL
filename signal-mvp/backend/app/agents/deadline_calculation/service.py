import json
import calendar
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from .schemas import (
    DeadlineCalculationRequest,
    DeadlineCalculationResponse,
)


class NoReportingRuleError(ValueError):
    """Raised when the catalog has no rule for a condition and scope."""


class DeadlineCalculationService:

    def __init__(self) -> None:
        self.catalog_path = (
            Path(__file__).resolve().parents[2]
            / "rules"
            / "rule_catalog.json"
        )

    def _load_rule(
        self,
        disease: str | None,
        jurisdiction: str,
        rule_id: str | None,
        reporting_scope: str = "CASE_REPORT",
    ) -> dict:
        with self.catalog_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            catalog = json.load(file)

        def normalize(value: str | None) -> str:
            normalized = re.sub(r"\((?:disorder|finding|situation)\)$", "", str(value or "").strip(), flags=re.IGNORECASE)
            return re.sub(r"[^a-z0-9]+", " ", normalized.casefold()).strip()

        disease_key = normalize(disease)
        scope_key = str(reporting_scope or "CASE_REPORT").strip().upper()
        # Keep legacy evaluator-backed rules authoritative when they are a
        # specific match (for example MEASLES-TX); the deadline catalog fills
        # in the remaining notifiable conditions.
        rules = list(catalog.get("rules", [])) + list(catalog.get("deadline_rules", []))
        for rule in rules:
            if str(rule.get("jurisdiction", "")).upper() != jurisdiction.upper():
                continue
            if str(rule.get("reporting_scope", "CASE_REPORT")).upper() != scope_key:
                continue
            if rule_id and rule.get("rule_id") != rule_id:
                continue

            names = [rule.get("disease"), rule.get("canonical_disease")]
            names.extend(rule.get("aliases", []))
            names.extend(rule.get("conditions", []))
            if disease_key and disease_key in {normalize(name) for name in names if name}:
                return rule

        raise NoReportingRuleError(
            "No reporting rule found for "
            f"disease={disease or 'unknown'}, "
            f"jurisdiction={jurisdiction}, "
            f"reporting_scope={scope_key}, "
            f"rule_id={rule_id}."
        )

    @staticmethod
    def _add_working_days(event_time: datetime, days: int) -> datetime:
        deadline = event_time
        elapsed_workdays = 0
        while elapsed_workdays < days:
            deadline += timedelta(days=1)
            if deadline.weekday() < 5:
                elapsed_workdays += 1
        return deadline

    @staticmethod
    def _add_calendar_month(event_time: datetime) -> datetime:
        month_index = event_time.month - 1 + 1
        year = event_time.year + month_index // 12
        month = month_index % 12 + 1
        day = min(event_time.day, calendar.monthrange(year, month)[1])
        return event_time.replace(year=year, month=month, day=day)

    def calculate(
        self,
        request: DeadlineCalculationRequest,
        db: Session | None = None,
    ) -> DeadlineCalculationResponse:

        try:
            rule = self._load_rule(
                disease=request.disease,
                jurisdiction=request.jurisdiction,
                rule_id=request.rule_id,
                reporting_scope=request.reporting_scope,
            )
        except NoReportingRuleError as exc:
            return DeadlineCalculationResponse(
                deadline=None,
                calculation_basis=str(exc),
                status="NO_RULE",
                disease=request.disease,
                jurisdiction=request.jurisdiction,
                reporting_timing=None,
                reporting_method=None,
                urgency=None,
                minutes_remaining=None,
                is_immediate=False,
            )

        reporting = rule.get("reporting", {})

        timing = str(
            reporting.get("timing", "")
        ).upper()

        method = str(
            reporting.get("method", "")
        ).upper()

        is_immediate = timing in {
            "CALL_IMMEDIATELY",
            "REPORT_IMMEDIATELY",
            "CALL_FAX_IMMEDIATELY",
            "IMMEDIATE",
        }
        if timing == "SEE_RULES":
            return DeadlineCalculationResponse(
                deadline=None,
                calculation_basis=rule.get("instructions") or "Follow the condition-specific reporting rules.",
                status="SEE_RULES",
                disease=request.disease,
                jurisdiction=request.jurisdiction,
                rule_id=rule.get("rule_id"),
                reporting_timing=timing,
                reporting_method=method,
                urgency=None,
                minutes_remaining=None,
                is_immediate=False,
                effective_year=rule.get("effective_year"),
                source_url=rule.get("source_url"),
                applicability=rule.get("applicability"),
            )
        if is_immediate:
            deadline = request.event_time
            calculation_basis = (
                f"{timing.replace('_', ' ').title()} per "
                f"rule {rule.get('rule_id')}."
            )
        elif timing == "WITHIN_1_WORK_DAY":
            deadline = self._add_working_days(request.event_time, 1)
            calculation_basis = f"Within 1 working day per rule {rule.get('rule_id')}."
        elif timing == "WITHIN_3_WORK_DAYS":
            deadline = self._add_working_days(request.event_time, 3)
            calculation_basis = f"Within 3 working days per rule {rule.get('rule_id')}."
        elif timing == "WITHIN_10_WORK_DAYS":
            deadline = self._add_working_days(request.event_time, 10)
            calculation_basis = f"Within 10 working days per rule {rule.get('rule_id')}."
        elif timing == "WITHIN_1_WEEK":
            deadline = request.event_time + timedelta(days=7)
            calculation_basis = f"Within 1 calendar week per rule {rule.get('rule_id')}."
        elif timing == "WITHIN_1_MONTH":
            deadline = self._add_calendar_month(request.event_time)
            calculation_basis = f"Within 1 calendar month per rule {rule.get('rule_id')}."
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
            reporting_method=method,
            urgency=urgency,
            minutes_remaining=minutes_remaining,
            is_immediate=is_immediate,
            effective_year=rule.get("effective_year"),
            source_url=rule.get("source_url") or "https://www.dshs.texas.gov/sites/default/files/IDCU/investigation/Reporting-forms/notifiable-conditions-2026-color.pdf",
            applicability=rule.get("applicability"),
        )
