from datetime import datetime, timedelta, timezone

import pytest

from backend.app.agents.deadline_escalation.service import DeadlineEscalationService


@pytest.mark.parametrize(
    ("minutes_remaining", "expected"),
    [
        (-1, "CRITICAL"),
        (240, "CRITICAL"),
        (241, "HIGH"),
        (1440, "HIGH"),
        (1441, "MEDIUM"),
        (4320, "MEDIUM"),
        (4321, "LOW"),
    ],
)
def test_escalation_urgency_uses_reporting_priority_thresholds(minutes_remaining, expected):
    current_time = datetime(2026, 10, 6, tzinfo=timezone.utc)
    result = DeadlineEscalationService().evaluate_current_state(
        current_time + timedelta(minutes=minutes_remaining),
        {"reporting": {"timing": "HOURS", "value": 24}},
        current_time=current_time,
    )

    assert result["urgency"] == expected
