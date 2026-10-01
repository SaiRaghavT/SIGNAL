from typing import Any

from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM
from backend.app.smart_field_population.models import SmartFieldResult


def _get_nested_value(data: dict[str, Any], path: str) -> Any:
    """Read a value using a dotted path such as patient.date_of_birth."""
    current: Any = data

    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None

        current = current[part]

    return current


def populate_report_fields(candidate: dict[str, Any]) -> SmartFieldResult:
    """
    Populate configured Texas Measles CRF fields from candidate data.

    Directly mapped values receive deterministic source and confidence
    metadata. Missing values are never invented.
    """

    fields: dict[str, Any] = {}
    populated_fields: list[str] = []
    missing_fields: list[str] = []
    required_missing_fields: list[str] = []
    sources: dict[str, str] = {}
    confidence: dict[str, float] = {}
    warnings: list[str] = []

    for field_config in TEXAS_MEASLES_FORM["fields"]:
        field_name = field_config["field"]
        source_path = field_config["source"]
        required = field_config.get("required", False)

        value = _get_nested_value(candidate, source_path)

        if value is not None and value != "":
            fields[field_name] = value
            populated_fields.append(field_name)

            # Direct deterministic mapping from the configured source.
            sources[field_name] = source_path
            confidence[field_name] = 1.0

        else:
            missing_fields.append(field_name)

            if required:
                required_missing_fields.append(field_name)

                warnings.append(
                    f"Required field could not be populated: {field_name}"
                )

    if missing_fields:
        warnings.append(
            f"{len(missing_fields)} configured report fields "
            f"could not be populated."
        )

    return SmartFieldResult(
        fields=fields,
        populated_fields=populated_fields,
        missing_fields=missing_fields,
        required_missing_fields=required_missing_fields,
        sources=sources,
        confidence=confidence,
        warnings=warnings,
    )