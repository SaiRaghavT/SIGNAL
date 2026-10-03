from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM
from backend.app.smart_field_population.models import SmartFieldResult


# ============================================================
# Generic helpers
# ============================================================

def _is_empty(value: Any) -> bool:
    """
    Treat None, empty strings, and empty containers as missing.
    False and 0 are valid values.
    """
    if value is None:
        return True

    if isinstance(value, str):
        return not value.strip()

    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0

    return False


def _get_nested_value(data: Any, path: str) -> Any:
    """
    Resolve dotted paths such as:

        patient.name
        facility.name
        clinical.onset_date

    from nested dictionaries.
    """
    if not path:
        return None

    current = data

    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None

        if current is None:
            return None

    return current


def _set_nested_value(
    data: Dict[str, Any],
    path: str,
    value: Any,
) -> None:
    """
    Set a dotted path in a nested dictionary.
    """
    parts = path.split(".")

    current = data

    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            current[part] = {}

        current = current[part]

    current[parts[-1]] = value


# ============================================================
# Laboratory helpers
# ============================================================

def _normalize_laboratory_evidence(
    laboratory_evidence: Any,
) -> list[Dict[str, Any]]:
    """
    Normalize laboratory evidence into a list of dictionaries.

    Supports:
        - list[dict]
        - tuple[dict]
        - a single dict
        - None
    """

    if laboratory_evidence is None:
        return []

    if isinstance(laboratory_evidence, dict):
        return [laboratory_evidence]

    if isinstance(laboratory_evidence, (list, tuple)):
        return [
            item
            for item in laboratory_evidence
            if isinstance(item, dict)
        ]

    return []


def _get_lab_code(lab: Dict[str, Any]) -> Optional[str]:
    """
    Extract a laboratory code.

    Supports both flat and nested representations.
    """

    code = lab.get("code")

    if isinstance(code, dict):
        return (
            code.get("code")
            or code.get("value")
            or code.get("id")
        )

    if code:
        return str(code)

    return (
        lab.get("loinc_code")
        or lab.get("test_code")
        or lab.get("code_value")
    )


def _get_lab_display(lab: Dict[str, Any]) -> Optional[str]:
    """
    Extract the laboratory test/display name.
    """

    code = lab.get("code")

    if isinstance(code, dict):
        display = (
            code.get("display")
            or code.get("name")
            or code.get("text")
        )

        if display:
            return str(display)

    return (
        lab.get("display")
        or lab.get("test_name")
        or lab.get("name")
        or lab.get("test")
    )


def _get_lab_conclusion(lab: Dict[str, Any]) -> Optional[str]:
    """
    Extract laboratory result/conclusion.
    """

    conclusion = (
        lab.get("conclusion")
        or lab.get("result")
        or lab.get("interpretation")
        or lab.get("value")
    )

    if isinstance(conclusion, dict):
        return (
            conclusion.get("text")
            or conclusion.get("display")
            or conclusion.get("value")
        )

    if conclusion is None:
        return None

    return str(conclusion)


def _is_positive_lab(lab: Dict[str, Any]) -> bool:
    """
    Determine whether a laboratory result is positive.
    """

    conclusion = _get_lab_conclusion(lab)

    if conclusion:
        normalized = conclusion.strip().lower()

        positive_values = {
            "positive",
            "detected",
            "reactive",
            "present",
            "abnormal",
            "pos",
        }

        if normalized in positive_values:
            return True

        if "positive" in normalized:
            return True

    return False


def _is_negative_lab(lab: Dict[str, Any]) -> bool:
    """
    Determine whether a laboratory result is negative.
    """

    conclusion = _get_lab_conclusion(lab)

    if conclusion:
        normalized = conclusion.strip().lower()

        negative_values = {
            "negative",
            "not detected",
            "non-reactive",
            "nonreactive",
            "absent",
            "normal",
            "neg",
        }

        if normalized in negative_values:
            return True

        if "negative" in normalized:
            return True

    return False


def _find_lab_result(
    laboratory_evidence: Iterable[Dict[str, Any]],
    *,
    code: Optional[str] = None,
    display_contains: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Find a laboratory result by code or display name.
    """

    code = str(code) if code else None
    display_contains = (
        display_contains.lower()
        if display_contains
        else None
    )

    for lab in laboratory_evidence:
        lab_code = _get_lab_code(lab)
        lab_display = _get_lab_display(lab)

        if code and lab_code and str(lab_code) == code:
            return lab

        if (
            display_contains
            and lab_display
            and display_contains in lab_display.lower()
        ):
            return lab

    return None


# ============================================================
# SIGNAL-specific derived fields
# ============================================================

def _build_derived_fields(
    candidate_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build fields that cannot be populated directly from the
    candidate structure.

    Current Texas Measles mapping:

        LOINC 5195-3
        Measles virus IgM Ab
        -> laboratory.igm

    IMPORTANT:
    We only populate fields when the evidence actually supports
    the value. We do not invent missing clinical information.
    """

    derived: Dict[str, Any] = {}

    laboratory_evidence = candidate_data.get(
        "laboratory_evidence"
    )

    if laboratory_evidence is None:
        laboratory_evidence = candidate_data.get(
            "lab_evidence"
        )

    labs = _normalize_laboratory_evidence(
        laboratory_evidence
    )

    # --------------------------------------------------------
    # Measles IgM
    # LOINC 5195-3
    # --------------------------------------------------------

    igm_lab = _find_lab_result(
        labs,
        code="5195-3",
        display_contains="measles virus igm",
    )

    if igm_lab:
        if _is_positive_lab(igm_lab):
            derived["laboratory.igm"] = "Positive"

        elif _is_negative_lab(igm_lab):
            derived["laboratory.igm"] = "Negative"

        else:
            conclusion = _get_lab_conclusion(igm_lab)

            if conclusion:
                derived["laboratory.igm"] = conclusion

    # --------------------------------------------------------
    # Optional future mappings
    # --------------------------------------------------------
    #
    # PCR / culture / IgG can be added here when corresponding
    # evidence exists.
    #
    # Do NOT populate them with invented values.
    #
    # Example:
    #
    # pcr_lab = _find_lab_result(
    #     labs,
    #     code="<PCR LOINC>"
    # )
    #
    # if pcr_lab:
    #     derived["laboratory.pcr"] = ...
    #

    return derived


# ============================================================
# Main mapper
# ============================================================

def populate_report_fields(
    candidate_data: Dict[str, Any],
) -> SmartFieldResult:
    """
    Populate Texas Measles reporting-form fields.

    Returns:

    {
        "fields": {...},
        "populated_fields": [...],
        "missing_fields": [...],
        "sources": {...},
        "confidence": {...},
        "warnings": [...]
    }
    """

    populated_fields: Dict[str, Any] = {}
    sources: Dict[str, str] = {}
    confidence: Dict[str, float] = {}

    missing_fields: list[str] = []
    required_missing_fields: list[str] = []
    warnings: list[str] = []

    # --------------------------------------------------------
    # Build derived values first
    # --------------------------------------------------------

    derived_fields = _build_derived_fields(candidate_data)

    # --------------------------------------------------------
    # Process configured form fields
    # --------------------------------------------------------

    for field_config in TEXAS_MEASLES_FORM["fields"]:

        field_name = field_config["field"]
        source_path = field_config["source"]
        required = field_config.get("required", False)

        # ----------------------------------------------------
        # 1. Derived field
        # ----------------------------------------------------

        if field_name in derived_fields:

            value = derived_fields[field_name]

            if not _is_empty(value):

                populated_fields[field_name] = value

                sources[field_name] = (
                    "derived:laboratory_evidence"
                )

                confidence[field_name] = 1.0

                continue

        # ----------------------------------------------------
        # 2. Direct source mapping
        # ----------------------------------------------------

        value = _get_nested_value(
            candidate_data,
            source_path,
        )

        if not _is_empty(value):

            populated_fields[field_name] = value

            sources[field_name] = source_path

            confidence[field_name] = 1.0

            continue

        # ----------------------------------------------------
        # 3. Missing field
        # ----------------------------------------------------

        missing_fields.append(field_name)
        if required:
            required_missing_fields.append(field_name)
        else:

            warnings.append(
                f"Optional field '{field_name}' "
                f"could not be populated from '{source_path}'."
            )

    # --------------------------------------------------------
    # Return
    # --------------------------------------------------------

    return SmartFieldResult(
        fields=populated_fields,
        populated_fields=list(populated_fields.keys()),
        missing_fields=missing_fields,
        required_missing_fields=required_missing_fields,
        sources=sources,
        confidence=confidence,
        warnings=warnings,
    )
