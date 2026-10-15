"""Canonical disease identities used to join evidence across trigger types."""

from __future__ import annotations

from typing import Any


_MEASLES = "measles"
_ALIASES = {
    # eRSD laboratory value sets may focus on the causative organism while
    # diagnosis triggers focus on the disease. Both belong to the measles case.
    "http://snomed.info/sct|14189004": _MEASLES,
    "http://snomed.info/sct|14168008": _MEASLES,
    "http://snomed.info/sct|7180009": _MEASLES,
    "http://snomed.info/sct|40468003": _MEASLES,
    "measles": _MEASLES,
    "rubeola": _MEASLES,
}


def canonical_disease_id(value: Any) -> str | None:
    if value is None:
        return None
    identity = str(value).strip()
    if not identity:
        return None
    key = identity.casefold()
    return _ALIASES.get(key, identity if identity.casefold() != "measles" else _MEASLES)
