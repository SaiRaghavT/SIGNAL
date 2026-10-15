from datetime import datetime, timezone

import pytest

from backend.app.agents.deadline_calculation.schemas import DeadlineCalculationRequest
from backend.app.agents.deadline_calculation.service import DeadlineCalculationService


SERVICE = DeadlineCalculationService()
EVENT = datetime(2026, 10, 2, 15, 30, tzinfo=timezone.utc)  # Friday


def calculate(disease, *, reporting_scope="CASE_REPORT"):
    return SERVICE.calculate(
        DeadlineCalculationRequest(
            event_time=EVENT,
            disease=disease,
            jurisdiction="TX",
            reporting_scope=reporting_scope,
        )
    )


def test_measles_is_immediate_at_the_trigger_time_not_24_hours_later():
    result = calculate("http://snomed.info/sct|14189004")

    assert result.reporting_timing == "CALL_IMMEDIATELY"
    assert result.deadline == EVENT
    assert result.is_immediate is True
    assert result.effective_year == 2026
    assert result.source_url.endswith("notifiable-conditions-2026-color.pdf")


@pytest.mark.parametrize("disease", ["Mumps", "Hepatitis A"])
def test_one_work_day_skips_the_weekend(disease):
    result = calculate(disease)

    assert result.reporting_timing == "WITHIN_1_WORK_DAY"
    assert result.deadline == datetime(2026, 10, 5, 15, 30, tzinfo=timezone.utc)


def test_salmonellosis_uses_one_calendar_week_not_five_work_days():
    result = calculate("Salmonellosis, including typhoid fever")

    assert result.reporting_timing == "WITHIN_1_WEEK"
    assert result.deadline == datetime(2026, 10, 9, 15, 30, tzinfo=timezone.utc)


def test_contaminated_sharps_adds_one_calendar_month_and_keeps_applicability():
    event = datetime(2026, 1, 31, 15, 30, tzinfo=timezone.utc)
    result = SERVICE.calculate(
        DeadlineCalculationRequest(
            event_time=event,
            disease="Contaminated sharps injury",
            jurisdiction="TX",
        )
    )

    assert result.reporting_timing == "WITHIN_1_MONTH"
    assert result.deadline == datetime(2026, 2, 28, 15, 30, tzinfo=timezone.utc)
    assert "Governmental entities" in result.applicability


def test_traumatic_brain_injury_adds_ten_work_days():
    result = calculate("Traumatic brain injury")

    assert result.reporting_timing == "WITHIN_10_WORK_DAYS"
    assert result.deadline == datetime(2026, 10, 16, 15, 30, tzinfo=timezone.utc)


def test_cancer_returns_see_rules_without_a_generic_deadline():
    result = calculate("Cancer")

    assert result.status == "SEE_RULES"
    assert result.reporting_timing == "SEE_RULES"
    assert result.deadline is None
    assert "Cancer Registry" in result.calculation_basis


def test_unknown_or_null_condition_returns_no_deadline():
    result = calculate(None)

    assert result.status == "NO_RULE"
    assert result.deadline is None


def test_syphilis_lab_reporting_is_separate_from_case_reporting():
    case_result = calculate("Primary syphilis")
    lab_result = calculate("Primary syphilis", reporting_scope="LAB_RESULT")

    assert case_result.reporting_timing == "WITHIN_1_WORK_DAY"
    assert lab_result.reporting_timing == "WITHIN_3_WORK_DAYS"
    assert lab_result.deadline == datetime(2026, 10, 7, 15, 30, tzinfo=timezone.utc)
