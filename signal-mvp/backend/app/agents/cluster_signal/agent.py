from datetime import date
from typing import Any

from backend.app.agents.cluster_signal.service import analyze_clusters


def run_cluster_signal(
    cases: list[dict[str, Any]],
    *,
    as_of_date: date,
    window_days: int = 7,
    baseline_days: int = 90,
    minimum_cases: int = 5,
    anomaly_threshold: float = 3.0,
) -> dict[str, Any]:
    """Run the population-level Cluster SIGNAL agent.

    This agent analyzes cases across patients, returns aggregate potential
    cluster alerts, and leaves outbreak determination to human reviewers.
    """

    return analyze_clusters(
        cases,
        as_of_date=as_of_date,
        window_days=window_days,
        baseline_days=baseline_days,
        minimum_cases=minimum_cases,
        anomaly_threshold=anomaly_threshold,
    )
