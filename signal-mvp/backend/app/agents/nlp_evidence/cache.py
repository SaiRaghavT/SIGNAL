"""Small process-local cache for validated, per-source evidence responses."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections import OrderedDict
from copy import deepcopy
from typing import Any

_CACHE_MAX_ENTRIES = 2048
_CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE: OrderedDict[tuple[str, ...], tuple[float, list[dict[str, Any]]]] = OrderedDict()
_CACHE_LOCK = threading.RLock()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_identity(document: dict[str, Any]) -> str:
    """Return a non-reversible identifier for cache keys and safe logs."""
    identity = document.get("document_id")
    if identity is None or not str(identity).strip():
        identity = "|".join(str(document.get(field) or "") for field in ("patient_id", "document_type", "title"))
    return _digest(str(identity))


def source_content_hash(document: dict[str, Any]) -> str:
    return _digest(str(document.get("text") or ""))


def cache_key(
    document: dict[str, Any],
    *,
    provider: str,
    model: str,
    prompt_schema_version: str,
    credential_fingerprint: str,
) -> tuple[str, ...]:
    return (
        _digest(str(document.get("patient_id") or "")),
        source_identity(document),
        source_content_hash(document),
        provider,
        model,
        prompt_schema_version,
        credential_fingerprint,
    )


def get_cached(key: tuple[str, ...]) -> list[dict[str, Any]] | None:
    now = time.monotonic()
    with _CACHE_LOCK:
        entry = _CACHE.get(key)
        if entry is None:
            return None
        expires_at, evidence = entry
        if expires_at <= now:
            del _CACHE[key]
            return None
        _CACHE.move_to_end(key)
        return deepcopy(evidence)


def store_cached(key: tuple[str, ...], evidence: list[dict[str, Any]]) -> None:
    # Only callers with a complete, schema-validated response should store.
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic() + _CACHE_TTL_SECONDS, deepcopy(evidence))
        _CACHE.move_to_end(key)
        while len(_CACHE) > _CACHE_MAX_ENTRIES:
            _CACHE.popitem(last=False)


def prune_patient_sources(patient_id: str, active_sources: dict[str, str]) -> None:
    """Drop deleted or edited source entries for this patient's current context."""
    patient_hash = _digest(str(patient_id or ""))
    # Keys and values are pre-hashed source identities and content hashes.
    active_hashes = dict(active_sources)
    now = time.monotonic()
    with _CACHE_LOCK:
        stale = [
            key for key, (expires_at, _) in _CACHE.items()
            if expires_at <= now
            or (
                key[0] == patient_hash
                and (key[1] not in active_hashes or key[2] != active_hashes[key[1]])
            )
        ]
        for key in stale:
            _CACHE.pop(key, None)


def clear_cache() -> None:
    """Clear evidence cache; intended for isolated unit tests and operations."""
    with _CACHE_LOCK:
        _CACHE.clear()


def cache_size() -> int:
    with _CACHE_LOCK:
        return len(_CACHE)


def cache_fingerprint(value: str) -> str:
    """Hash prompt/schema/provider-key material without retaining its contents."""
    return _digest(value)


def stable_schema_fingerprint(schema: dict[str, Any]) -> str:
    return cache_fingerprint(json.dumps(schema, sort_keys=True, separators=(",", ":")))
