from typing import Any


MEASLES_KEYWORDS = {
    "measles",
    "rubeola",
    "measles infection",
}


MEASLES_LAB_KEYWORDS = {
    "measles igm",
    "measles igg",
    "measles pcr",
    "rubeola igm",
    "rubeola igg",
    "rubeola pcr",
}


def _normalize(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip().lower()


def detect_candidates(
    normalized_patient: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Detect potential reportable-disease candidates
    from canonical patient data.

    This layer is intentionally deterministic.

    AI evidence extraction and reasoning will be added
    after candidate detection is working.
    """

    candidates: list[dict[str, Any]] = []

    patient = normalized_patient.get(
        "patient",
        {},
    )

    patient_id = patient.get("id")

    # --------------------------------------------------
    # Condition-based detection
    # --------------------------------------------------

    for condition in normalized_patient.get(
        "conditions",
        [],
    ):
        condition_display = _normalize(
            condition.get("display")
            or condition.get("condition_display")
        )

        condition_code = _normalize(
            condition.get("code")
            or condition.get("condition_code")
        )

        matched_term = next(
            (
                keyword
                for keyword in MEASLES_KEYWORDS
                if keyword in condition_display
                or keyword in condition_code
            ),
            None,
        )

        if matched_term:
            candidates.append(
                {
                    "patient_id": patient_id,
                    "disease": "measles",
                    "candidate_type": "condition",
                    "trigger": matched_term,
                    "source": "canonical_condition",
                    "status": "detected",
                }
            )

    # --------------------------------------------------
    # Lab-result detection
    # --------------------------------------------------

    for lab_result in normalized_patient.get(
        "lab_results",
        [],
    ):
        test_display = _normalize(
            lab_result.get("test_display")
        )

        test_code = _normalize(
            lab_result.get("test_code")
        )

        conclusion = _normalize(
            lab_result.get("conclusion")
        )

        searchable_text = " ".join(
            [
                test_display,
                test_code,
                conclusion,
            ]
        )

        matched_lab = next(
            (
                keyword
                for keyword in MEASLES_LAB_KEYWORDS
                if keyword in searchable_text
            ),
            None,
        )

        if matched_lab:
            candidates.append(
                {
                    "patient_id": patient_id,
                    "disease": "measles",
                    "candidate_type": "laboratory",
                    "trigger": matched_lab,
                    "source": "canonical_lab_result",
                    "status": "detected",
                }
            )

    return candidates