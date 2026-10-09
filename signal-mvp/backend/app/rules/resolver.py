import importlib
import json
from pathlib import Path
from typing import Any, Callable, Dict

from backend.app.detection.disease_concepts import canonical_disease_id


CATALOG_PATH = Path(__file__).resolve().parent / "rule_catalog.json"


class RuleResolutionError(Exception):
    """Raised when an applicable reporting rule cannot be resolved."""


def _load_catalog() -> Dict[str, Any]:
    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def normalize_disease_name(disease: str | None) -> str | None:
    """Return the catalog's canonical disease name for a known disease identity."""
    if disease is None or not disease.strip():
        return None
    identity = canonical_disease_id(disease)
    for rule in _load_catalog().get("rules", []):
        configured_disease = rule.get("disease")
        if canonical_disease_id(configured_disease) == identity:
            return str(configured_disease)
    return disease.strip()


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

    disease_key = canonical_disease_id(disease)
    jurisdiction_key = jurisdiction.strip().upper()

    for rule in catalog.get("rules", []):
        configured_disease = str(
            rule.get("disease", "")
        ).strip().casefold()
        configured_disease_key = canonical_disease_id(configured_disease)

        configured_jurisdiction = str(
            rule.get("jurisdiction", "")
        ).strip().upper()

        if (
            configured_disease_key == disease_key
            and configured_jurisdiction == jurisdiction_key
        ):
            evaluator_path = rule.get("evaluator")

            if not evaluator_path:
                raise RuleResolutionError(
                    "Applicable rule does not define an evaluator."
                )

            return {
                "rule_id": rule.get("rule_id"),
                "rule_version": rule.get("rule_version"),
                "disease": rule.get("disease"),
                "jurisdiction": rule.get("jurisdiction"),
                "evaluator": _load_evaluator(evaluator_path),
            }

    raise RuleResolutionError(
        f"No reporting rule configured for "
        f"disease='{disease}' and jurisdiction='{jurisdiction}'."
    )
