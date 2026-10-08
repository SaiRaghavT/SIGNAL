from typing import Any

from backend.app.smart_field_population.form_config import (
    REPORTING_MISSING_INFO_FIELDS,
    TEXAS_MEASLES_FORM,
)


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    return False


def missing_report_fields(values: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    required_missing: list[str] = []
    for config in TEXAS_MEASLES_FORM["fields"]:
        name = config["field"]
        if is_missing(values.get(name)):
            missing.append(name)
            if config.get("required", False):
                required_missing.append(name)
    return missing, required_missing


def available_case_report_fields(case: Any) -> dict[str, Any]:
    """Combine explicitly saved form edits with real values on the case record."""
    transient_fields = set(REPORTING_MISSING_INFO_FIELDS)
    values = {
        key: value
        for key, value in (getattr(case, "report_fields", None) or {}).items()
        if key not in transient_fields
    }
    sources = {
        "patient": getattr(case, "patient", None) or {},
        "facility": getattr(case, "facility", None) or {},
        "provider": getattr(case, "provider", None) or {},
        "clinical": getattr(case, "clinical_evidence", None) or {},
        "laboratory": getattr(case, "laboratory_evidence", None) or {},
    }

    def read_source(path: str) -> Any:
        if path == "disease":
            return getattr(case, "disease", None)
        root, *parts = path.split(".")
        current: Any = sources.get(root)
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        if root == "patient" and parts == ["name"] and not current:
            patient = sources["patient"]
            current = " ".join(str(patient.get(key, "")).strip() for key in ("first_name", "last_name") if patient.get(key))
        if root == "patient" and parts == ["address"] and isinstance(current, dict):
            current = current.get("line") or current.get("address_line") or current.get("street")
        if root == "patient" and parts == ["zip"] and not current:
            current = sources["patient"].get("postal_code")
        return current

    for config in TEXAS_MEASLES_FORM["fields"]:
        field = config["field"]
        value = read_source(config.get("source", ""))
        if field not in values and not is_missing(value):
            values[field] = value
    return values
