import json
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


class DeadlineCalculationService:

    def __init__(self) -> None:
        self.catalog_path = (
            Path(__file__).resolve().parents[2]
            / "rules"
            / "rule_catalog.json"
        )

    def _load_rule(
        self,
        disease: str,
        jurisdiction: str,
        rule_id: str | None,
    ) -> dict:

        with self.catalog_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            catalog = json.load(file)

        for rule in catalog.get("rules", []):
            if (
                rule.get("disease", "").lower()
                == disease.lower()
                and rule.get("jurisdiction", "").upper()
                == jurisdiction.upper()
                and (
                    rule_id is None
                    or rule.get("rule_id") == rule_id
                )
            ):
                return rule

        raise ValueError(
            "No reporting rule found for "
            f"disease={disease}, "
            f"jurisdiction={jurisdiction}, "
            f"rule_id={rule_id}."
        )

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

        else:
            raise ValueError(
                f"Unsupported reporting timing: {timing}"
            )

        minutes_remaining = int(
            (deadline - datetime.now(timezone.utc)).total_seconds() / 60
        )
        rule_window_minutes = int(
            (deadline - request.event_time).total_seconds() / 60
        )
        warning_window_minutes = int(rule.get("severity_warning_minutes", 60))
        if minutes_remaining < 0:
            urgency = "CRITICAL"
        elif minutes_remaining <= warning_window_minutes:
            urgency = "HIGH"
        elif minutes_remaining <= rule_window_minutes:
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
        )