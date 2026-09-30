from collections import defaultdict
from datetime import date, timedelta
from math import sqrt
from typing import Any


def _location_groups(case: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    """Return coarse, non-address groupings for a case."""

    groups: list[tuple[str, str, str | None]] = []

    for prefix, location in (
        ("patient", case.get("patient_location")),
        ("facility", case.get("facility_location")),
    ):
        if not isinstance(location, dict):
            continue

        state = location.get("state")
        if location.get("postal_code"):
            groups.append(
                (
                    f"{prefix}_postal_code",
                    str(location["postal_code"]).strip(),
                    state,
                )
            )
        elif location.get("county"):
            groups.append(
                (
                    f"{prefix}_county",
                    str(location["county"]).strip(),
                    state,
                )
            )
        elif location.get("city"):
            groups.append(
                (
                    f"{prefix}_city",
                    str(location["city"]).strip(),
                    state,
                )
            )
        elif location.get("latitude") is not None and location.get("longitude") is not None:
            # Coarse ~11 km cells provide a fallback when administrative
            # geography is absent; this is not a precise distance cluster.
            latitude_cell = round(float(location["latitude"]), 1)
            longitude_cell = round(float(location["longitude"]), 1)
            groups.append(
                (
                    f"{prefix}_coordinate_cell",
                    f"{latitude_cell:.1f},{longitude_cell:.1f}",
                    state,
                )
            )

    if case.get("facility_id"):
        groups.append(("facility", str(case["facility_id"]).strip(), None))

    if case.get("setting_id"):
        groups.append(("setting", str(case["setting_id"]).strip(), None))

    return [group for group in groups if group[1]]


def _demographic_summary(cases: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    age_bands: defaultdict[str, int] = defaultdict(int)
    sexes: defaultdict[str, int] = defaultdict(int)

    for case in cases:
        age = case.get("age_years")
        if isinstance(age, int) and age >= 0:
            if age < 18:
                age_bands["under_18"] += 1
            elif age < 45:
                age_bands["18_44"] += 1
            elif age < 65:
                age_bands["45_64"] += 1
            else:
                age_bands["65_plus"] += 1

        sex = case.get("sex")
        if isinstance(sex, str) and sex.strip():
            sexes[sex.strip().lower()] += 1

    return {
        "age_bands": dict(age_bands),
        "sex": dict(sexes),
    }


def analyze_clusters(
    cases: list[dict[str, Any]],
    *,
    as_of_date: date,
    window_days: int = 7,
    baseline_days: int = 90,
    minimum_cases: int = 5,
    anomaly_threshold: float = 3.0,
) -> dict[str, Any]:
    """Flag potential disease concentrations against a recent baseline.

    Cases are grouped by disease and coarse patient/facility geography,
    facility, or shared setting. The score is an approximate Poisson
    deviation score, not a probability that an outbreak is occurring.
    """

    analysis_start = as_of_date - timedelta(days=window_days - 1)
    baseline_end = analysis_start - timedelta(days=1)
    baseline_start = baseline_end - timedelta(days=baseline_days - 1)

    grouped_cases: dict[
        tuple[str, str, str, str],
        dict[str, Any],
    ] = {}
    excluded_cases = 0

    for case in cases:
        disease_id = case.get("disease_id")
        case_id = case.get("case_id")
        onset_date = case.get("onset_date")

        if not disease_id or not case_id or not isinstance(onset_date, date):
            excluded_cases += 1
            continue

        location_groups = _location_groups(case)
        if not location_groups:
            excluded_cases += 1
            continue

        for level, value, state in location_groups:
            normalized_value = value.casefold()
            normalized_state = state.casefold() if state else ""
            key = (str(disease_id), level, normalized_state, normalized_value)
            group = grouped_cases.setdefault(
                key,
                {
                    "disease_id": str(disease_id),
                    "level": level,
                    "value": value,
                    "state": state,
                    "cases": {},
                },
            )
            group["cases"][str(case_id)] = case

    alerts = []
    for group in grouped_cases.values():
        group_cases = list(group["cases"].values())
        recent_cases = [
            case
            for case in group_cases
            if analysis_start <= case["onset_date"] <= as_of_date
        ]
        baseline_case_count = sum(
            baseline_start <= case["onset_date"] <= baseline_end
            for case in group_cases
        )

        observed = len(recent_cases)
        if observed < minimum_cases:
            continue

        expected = baseline_case_count * window_days / baseline_days
        score = (observed - expected) / sqrt(expected + 0.5)
        if score < anomaly_threshold:
            continue

        signal_strength = "high" if score >= anomaly_threshold * 1.5 else "elevated"
        alerts.append(
            {
                "alert_type": "potential_cluster",
                "disease_id": group["disease_id"],
                "location": {
                    "level": group["level"],
                    "value": group["value"],
                    "state": group["state"],
                },
                "observed_cases": observed,
                "baseline_cases": baseline_case_count,
                "baseline_days": baseline_days,
                "expected_cases": round(expected, 2),
                "window_start": analysis_start.isoformat(),
                "window_end": as_of_date.isoformat(),
                "signal_score": round(score, 2),
                "signal_strength": signal_strength,
                "demographics": _demographic_summary(recent_cases),
                "requires_human_review": True,
            }
        )

    alerts.sort(
        key=lambda alert: (
            -alert["signal_score"],
            alert["disease_id"],
            alert["location"]["level"],
            alert["location"]["value"],
        )
    )

    return {
        "as_of_date": as_of_date.isoformat(),
        "window_days": window_days,
        "baseline_days": baseline_days,
        "cases_received": len(cases),
        "cases_excluded": excluded_cases,
        "alert_count": len(alerts),
        "alerts": alerts,
    }
