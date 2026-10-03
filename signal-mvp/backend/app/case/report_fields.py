from typing import Any

from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM


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
