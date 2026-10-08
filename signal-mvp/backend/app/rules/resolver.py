import importlib
import json
from pathlib import Path
from typing import Any, Callable, Dict


CATALOG_PATH = Path(__file__).resolve().parent / "rule_catalog.json"


class RuleResolutionError(Exception):
    """Raised when an applicable reporting rule cannot be resolved."""


def _load_catalog() -> Dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def load_catalog() -> Dict[str, Any]:
    """Return the current reporting catalog for read-only condition matching."""
    return _load_catalog()


def normalize_jurisdiction(value: str, catalog: Dict[str, Any] | None = None) -> str:
    """Normalize a jurisdiction using aliases configured in the rule catalog."""
    catalog = catalog or load_catalog()
    canonical = str(catalog.get("jurisdiction") or "").strip()
    aliases = catalog.get("jurisdiction_aliases", [])
    for known in (canonical, *aliases):
        if str(known).strip().casefold() == value.strip().casefold():
            return canonical
    return value.strip().upper()


def _load_evaluator(path: str) -> Callable:
    """
    Dynamically load a rule evaluator from a configured import path.

    Expected format:
        package.module:function
    """

    try:
        module_path, function_name = path.split(":", 1)
    except ValueError as exc:
        raise RuleResolutionError(
            f"Invalid rule evaluator path: {path}"
        ) from exc

    try:
        module = importlib.import_module(module_path)
        evaluator = getattr(module, function_name)
    except (ImportError, AttributeError) as exc:
        raise RuleResolutionError(
            f"Unable to load configured rule evaluator: {path}"
        ) from exc

    if not callable(evaluator):
        raise RuleResolutionError(
            f"Configured rule evaluator is not callable: {path}"
        )

    return evaluator


def resolve_rule(
    disease: str,
    jurisdiction: str,
    rule_id: str | None = None,
) -> Dict[str, Any]:
    """
    Resolve the reporting rule applicable to a disease and jurisdiction.

    Returns the configured rule metadata and evaluator.

    No disease- or jurisdiction-specific logic is hardcoded here.
    """

    if not disease:
        raise RuleResolutionError(
            "Disease is required for rule resolution."
        )

    if not jurisdiction:
        raise RuleResolutionError(
            "Jurisdiction is required for rule resolution."
        )

    catalog = _load_catalog()

    disease_key = disease.strip().casefold()
    canonical_jurisdiction = normalize_jurisdiction(jurisdiction, catalog)

    for rule in catalog.get("rules", []):
        configured_diseases = [
            rule.get("disease", ""),
            *rule.get("aliases", []),
        ]

        configured_jurisdiction = str(
            rule.get("jurisdiction", "")
        ).strip().upper()

        if (
            any(
                str(configured_disease).strip().casefold() == disease_key
                for configured_disease in configured_diseases
            )
            and configured_jurisdiction == canonical_jurisdiction.upper()
            and (rule_id is None or rule.get("rule_id") == rule_id)
        ):
            evaluator_path = rule.get("evaluator")

            if not evaluator_path:
                raise RuleResolutionError(
                    "Applicable rule does not define an evaluator."
                )

            return {**rule, "evaluator": _load_evaluator(evaluator_path)}

    raise RuleResolutionError(
        f"No reporting rule configured for "
        f"disease='{disease}' and jurisdiction='{jurisdiction}'."
    )
