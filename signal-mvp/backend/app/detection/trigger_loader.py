from __future__ import annotations

import json
import os

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


# =========================================================
# Configuration
# =========================================================

DEFAULT_BUNDLE_PATH = (
    Path(__file__).resolve().parent
    / "data"
    / "eRSDv3_specification_bundle.json"
)


# Official eRSD v3.2 RCTC groups.
RCTC_GROUP_IDS = {
    "dxtc-3.2.0": "DIAGNOSIS_PROBLEM",
    "ostc-3.2.0": "ORGANISM_SUBSTANCE",
    "lotc-3.2.0": "LAB_ORDER",
    "lrtc-3.2.0": "LAB_RESULT",
    "mrtc-3.2.0": "MEDICATION",
    "sdtc-3.2.0": "SUSPECTED_DISORDER",
    "iztc-3.2.0": "IMMUNIZATION",
    "artc-3.2.0": "ALL_RESULTS",
    "eltc-3.2.0": "EXTENDED_TIMING",
}


# =========================================================
# Bundle Loading
# =========================================================

def _bundle_path() -> Path:
    configured = os.getenv(
        "SIGNAL_ERSD_BUNDLE_PATH"
    )

    if configured:
        return Path(
            configured
        ).expanduser().resolve()

    return DEFAULT_BUNDLE_PATH


def _require_bundle_path() -> Path:
    path = _bundle_path()

    if not path.exists():
        raise FileNotFoundError(
            f"eRSD bundle not found: {path}. "
            "Place eRSDv3_specification_bundle.json in "
            "backend/app/detection/data/."
        )

    return path


def _load_json(
    path: Path,
) -> Dict[str, Any]:

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        payload = json.load(handle)

    if not isinstance(payload, dict):
        raise ValueError(
            "eRSD bundle must contain a JSON object."
        )

    if payload.get("resourceType") != "Bundle":
        raise ValueError(
            "Invalid eRSD bundle: "
            "resourceType must be 'Bundle'."
        )

    if not isinstance(
        payload.get("entry"),
        list,
    ):
        raise ValueError(
            "Invalid eRSD bundle: "
            "Bundle.entry must be a list."
        )

    return payload


def _resources_by_type(
    bundle: Dict[str, Any],
    resource_type: str,
) -> List[Dict[str, Any]]:

    resources: List[Dict[str, Any]] = []

    for entry in bundle.get(
        "entry",
        [],
    ):

        if not isinstance(entry, dict):
            continue

        resource = entry.get(
            "resource"
        )

        if (
            isinstance(resource, dict)
            and resource.get(
                "resourceType"
            ) == resource_type
        ):
            resources.append(resource)

    return resources


def _canonical_key(
    url: str,
    version: Optional[str] = None,
) -> str:

    if version:
        return f"{url}|{version}"

    return url


# =========================================================
# ValueSet Helpers
# =========================================================

def _value_set_contains_code(
    value_set: Dict[str, Any],
    system: str,
    code: str,
) -> bool:

    expansion = value_set.get(
        "expansion",
        {}
    )

    contains = expansion.get(
        "contains",
        []
    )

    for item in contains:

        if not isinstance(item, dict):
            continue

        if (
            item.get("system") == system
            and str(item.get("code"))
            == str(code)
        ):
            return True

    return False


def _value_set_identity(
    value_set: Dict[str, Any],
) -> str:

    return (
        value_set.get("url")
        or value_set.get("id")
        or value_set.get("name")
        or str(id(value_set))
    )


def _value_set_summary(
    value_set: Dict[str, Any],
) -> Dict[str, Any]:

    return {
        "id": value_set.get("id"),
        "url": value_set.get("url"),
        "version": value_set.get("version"),
        "name": value_set.get("name"),
        "title": value_set.get("title"),
    }


# =========================================================
# Cached Bundle
# =========================================================

@lru_cache(maxsize=1)
def load_ersd_bundle() -> Dict[str, Any]:
    """
    Load the official eRSD specification bundle.

    The downloaded bundle is the source of truth.

    No disease-specific trigger codes are hardcoded.
    """

    path = _require_bundle_path()

    return _load_json(path)


@lru_cache(maxsize=1)
def get_ersd_metadata() -> Dict[str, Any]:

    bundle = load_ersd_bundle()

    libraries = _resources_by_type(
        bundle,
        "Library",
    )

    ersd_library = next(
        (
            library
            for library in libraries
            if str(
                library.get("id", "")
            ).startswith(
                "ersd-specification-"
            )
        ),
        None,
    )

    rctc_library = next(
        (
            library
            for library in libraries
            if str(
                library.get("id", "")
            ).startswith("rctc-")
        ),
        None,
    )

    release_label = None

    if rctc_library:

        for extension in rctc_library.get(
            "extension",
            [],
        ):

            if (
                extension.get("url")
                == (
                    "http://hl7.org/fhir/"
                    "StructureDefinition/"
                    "artifact-releaseLabel"
                )
            ):
                release_label = extension.get(
                    "valueString"
                )
                break

    return {
        "bundle_id": bundle.get(
            "id"
        ),

        "bundle_type": bundle.get(
            "type"
        ),

        "ersd_version": (
            ersd_library.get("version")
            if ersd_library
            else None
        ),

        "rctc_version": (
            rctc_library.get("version")
            if rctc_library
            else None
        ),

        "rctc_release_label": (
            release_label
        ),
    }


# =========================================================
# ValueSet Index
# =========================================================

@lru_cache(maxsize=1)
def get_value_sets() -> Dict[
    str,
    Dict[str, Any],
]:
    """
    Index every ValueSet in the eRSD bundle.

    Each ValueSet can be retrieved by:

        resource id
        canonical URL
        canonical URL + version
    """

    bundle = load_ersd_bundle()

    index: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for value_set in _resources_by_type(
        bundle,
        "ValueSet",
    ):

        resource_id = value_set.get(
            "id"
        )

        url = value_set.get(
            "url"
        )

        version = value_set.get(
            "version"
        )

        if resource_id:
            index[resource_id] = value_set

        if url:
            index[url] = value_set

            if version:
                index[
                    _canonical_key(
                        url,
                        version,
                    )
                ] = value_set

    return index


# =========================================================
# RCTC Groups
# =========================================================

@lru_cache(maxsize=1)
def get_rctc_groups() -> Dict[
    str,
    Dict[str, Any],
]:
    """
    Return the official RCTC grouping ValueSets.
    """

    value_sets = get_value_sets()

    groups: Dict[
        str,
        Dict[str, Any],
    ] = {}

    for group_id in RCTC_GROUP_IDS:

        value_set = value_sets.get(
            group_id
        )

        if value_set:
            groups[group_id] = value_set

    return groups


# =========================================================
# Code → RCTC Index
# =========================================================

@lru_cache(maxsize=1)
def build_trigger_code_index() -> Dict[
    str,
    List[Dict[str, Any]],
]:
    """
    Build:

        system|code
              ↓
        RCTC trigger groups

    All clinical codes come directly from
    the official eRSD bundle.
    """

    index: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    groups = get_rctc_groups()

    for group_id, value_set in groups.items():

        group_name = RCTC_GROUP_IDS.get(
            group_id,
            group_id,
        )

        contains = (
            value_set
            .get("expansion", {})
            .get("contains", [])
        )

        for item in contains:

            if not isinstance(
                item,
                dict,
            ):
                continue

            system = item.get(
                "system"
            )

            code = item.get(
                "code"
            )

            if not system or code is None:
                continue

            key = (
                f"{system}|{code}"
            )

            index.setdefault(
                key,
                [],
            ).append(
                {
                    "group_id": group_id,
                    "group": group_name,
                    "code_system": system,
                    "code": str(code),
                    "display": item.get(
                        "display"
                    ),
                    "version": item.get(
                        "version"
                    ),
                }
            )

    return index


# =========================================================
# RCTC Matching
# =========================================================

def match_trigger_code(
    system: str,
    code: str,
) -> List[Dict[str, Any]]:
    """
    Match a clinical code against the official
    RCTC trigger groups.

    Returns every matching RCTC group and the
    underlying official ValueSets containing the code.
    """

    if not system or code is None:
        return []

    key = f"{system}|{code}"

    matches = list(
        build_trigger_code_index().get(
            key,
            [],
        )
    )

    if not matches:
        return []

    value_sets = find_value_sets_containing_code(
        system=system,
        code=str(code),
    )

    enriched: List[
        Dict[str, Any]
    ] = []

    for match in matches:

        item = dict(match)

        item[
            "value_sets"
        ] = value_sets

        item[
            "value_set_ids"
        ] = [
            value_set.get("id")
            for value_set in value_sets
            if value_set.get("id")
        ]

        item[
            "value_set_urls"
        ] = [
            value_set.get("url")
            for value_set in value_sets
            if value_set.get("url")
        ]

        enriched.append(
            item
        )

    return enriched


# =========================================================
# Official Trigger Iteration
# =========================================================

def iter_trigger_codes(
    group_id: Optional[str] = None,
) -> Iterable[Dict[str, Any]]:
    """
    Iterate through official RCTC trigger codes.

    If group_id is provided, only that RCTC group
    is returned.
    """

    groups = get_rctc_groups()

    if group_id is not None:

        selected_groups = (
            {
                group_id: groups[group_id]
            }
            if group_id in groups
            else {}
        )

    else:

        selected_groups = groups

    for (
        current_group_id,
        value_set,
    ) in selected_groups.items():

        group_name = RCTC_GROUP_IDS.get(
            current_group_id,
            current_group_id,
        )

        contains = (
            value_set
            .get("expansion", {})
            .get("contains", [])
        )

        for item in contains:

            if not isinstance(
                item,
                dict,
            ):
                continue

            system = item.get(
                "system"
            )

            code = item.get(
                "code"
            )

            if not system or code is None:
                continue

            yield {
                "group_id": current_group_id,
                "group": group_name,
                "code_system": system,
                "code": str(code),
                "display": item.get(
                    "display"
                ),
                "version": item.get(
                    "version"
                ),
            }


# =========================================================
# ValueSet Provenance
# =========================================================

@lru_cache(maxsize=1)
def _value_set_code_index() -> Dict[
    str,
    List[Dict[str, Any]],
]:
    """
    Build a reverse index across all ValueSet expansions:

        system|code
             ↓
        ValueSets containing code

    This makes explainability fast without repeatedly
    scanning the complete eRSD bundle.
    """

    index: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    seen: set[str] = set()

    for value_set in get_value_sets().values():

        if not isinstance(
            value_set,
            dict,
        ):
            continue

        identity = _value_set_identity(
            value_set
        )

        if identity in seen:
            continue

        seen.add(identity)

        contains = (
            value_set
            .get("expansion", {})
            .get("contains", [])
        )

        for item in contains:

            if not isinstance(
                item,
                dict,
            ):
                continue

            system = item.get(
                "system"
            )

            code = item.get(
                "code"
            )

            if not system or code is None:
                continue

            key = (
                f"{system}|{code}"
            )

            index.setdefault(
                key,
                [],
            ).append(
                _value_set_summary(
                    value_set
                )
            )

    return index


def find_value_sets_containing_code(
    system: str,
    code: str,
) -> List[Dict[str, Any]]:
    """
    Find official eRSD ValueSets containing a
    particular clinical code.
    """

    if not system or code is None:
        return []

    key = f"{system}|{code}"

    return list(
        _value_set_code_index().get(
            key,
            [],
        )
    )


# =========================================================
# RCTC Concept Context
# =========================================================

def get_trigger_context(
    system: str,
    code: str,
) -> Dict[str, Any]:
    """
    Return complete explainability context for a
    clinical trigger.

    Useful for:
        - Candidate Detection
        - Candidate Fusion
        - audit
        - UI explanation
        - debugging
    """

    matches = match_trigger_code(
        system=system,
        code=code,
    )

    value_sets = find_value_sets_containing_code(
        system=system,
        code=code,
    )

    return {
        "trigger_key": (
            f"{system}|{code}"
            if system and code is not None
            else None
        ),

        "code_system": system,
        "code": code,

        "matched": bool(matches),

        "rctc_groups": matches,

        "value_sets": value_sets,

        "ersd_metadata": get_ersd_metadata(),
    }


# =========================================================
# Cache Management
# =========================================================

def clear_ersd_cache() -> None:
    """
    Clear all cached eRSD indexes.

    Call this after replacing the eRSD bundle
    during development/testing.
    """

    load_ersd_bundle.cache_clear()

    get_ersd_metadata.cache_clear()

    get_value_sets.cache_clear()

    get_rctc_groups.cache_clear()

    build_trigger_code_index.cache_clear()

    _value_set_code_index.cache_clear()