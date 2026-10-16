from __future__ import annotations

import json
import hashlib
import re
import threading
import time
from uuid import uuid4
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from copy import deepcopy
from typing import Any

from backend.app.ai_detection_logging import get_ai_detection_logger
from backend.app.config.settings import settings
from backend.app.anatomy.markers import (
    get_anatomy_marker,
    get_anatomy_marker_for_region,
    get_model_body_part_catalog,
)
from backend.app.prompts.anatomy import ANATOMY_SYSTEM_PROMPT

_LOGGER = get_ai_detection_logger()

_FINDING_TYPES = {
    "skin_change",
    "eye_finding",
    "respiratory_symptom",
    "fever",
    "pain_tenderness",
    "gastrointestinal_symptom",
    "other",
}
_ASSERTIONS = {"present", "absent", "uncertain", "historical"}
_LABELS = {
    "skin_change": "Rash or skin changes",
    "eye_finding": "Eye redness or irritation",
    "respiratory_symptom": "Cough or respiratory symptoms",
    "fever": "Fever",
    "pain_tenderness": "Pain or tenderness",
    "gastrointestinal_symptom": "Gastrointestinal symptoms",
}
_PROVIDER_COOLDOWNS: dict[str, float] = {}
_PROVIDER_COOLDOWNS_LOCK = threading.Lock()
_ANATOMY_PROVIDER_TIMEOUT_SECONDS = 12.0
_ANATOMY_PROMPT_SCHEMA_VERSION = "anatomy-evidence-v2"
_ANATOMY_CACHE_TTL_SECONDS = 24 * 60 * 60
_ANATOMY_CACHE_MAX_ENTRIES = 256
_ANATOMY_RESPONSE_CACHE: OrderedDict[tuple[str, ...], tuple[float, dict[str, Any]]] = OrderedDict()
_ANATOMY_RESPONSE_CACHE_LOCK = threading.RLock()
_SCHEMA = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_id": {"type": "string"},
                    "finding_type": {"type": "string", "enum": sorted(_FINDING_TYPES)},
                    "label": {"type": "string"},
                    "concept": {"type": "string"},
                    "assertion": {"type": "string", "enum": sorted(_ASSERTIONS)},
                    "body_regions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "body_part": {"type": "string"},
                                "marker_id": {"type": "string"},
                            },
                            "required": ["body_part", "marker_id"],
                        },
                    },
                    "laterality": {"type": "string", "enum": ["unspecified", "left", "right", "bilateral"]},
                    "evidence_text": {"type": "string"},
                },
                "required": ["source_id", "finding_type", "label", "concept", "assertion", "body_regions", "laterality", "evidence_text"],
            },
        },
    },
    "required": ["findings"],
}


def _groq_strict_schema() -> dict[str, Any]:
    """Return the strict JSON Schema form required by Groq structured output."""
    schema = deepcopy(_SCHEMA)

    def close_objects(node: dict[str, Any]) -> None:
        if node.get("type") == "object":
            node["additionalProperties"] = False
            for child in node.get("properties", {}).values():
                if isinstance(child, dict):
                    close_objects(child)
        items = node.get("items")
        if isinstance(items, dict):
            close_objects(items)

    close_objects(schema)
    return schema


def _anatomy_groq_api_key() -> str | None:
    """Return the anatomy-specific key, falling back to the legacy shared key."""
    return settings.groq_anatomy_api_key or settings.groq_api_key


def _configured_providers() -> list[tuple[str, str]]:
    configured = []
    selected = (settings.llm_provider or "gemini").strip().casefold()
    options = [selected] + [provider for provider in ("gemini", "groq", "openrouter") if provider != selected]
    for provider in options:
        if provider == "gemini" and settings.gemini_api_key:
            configured.append((provider, settings.gemini_model))
        elif provider == "groq" and _anatomy_groq_api_key():
            configured.append((provider, settings.groq_model))
        elif provider == "openrouter" and settings.openrouter_api_key:
            configured.append((provider, settings.openrouter_model))
    return configured


def _prompt_for_sources(
    sources: list[dict[str, str]],
    catalog: list[dict[str, str]] | None = None,
) -> str:
    # The model only needs anchor identity and its human-readable name to select
    # a location. Keep the large coordinate catalog on the server for validation.
    if catalog is None:
        catalog = [
            {"marker_id": part["id"], "body_part": part["body_part"]}
            for part in get_model_body_part_catalog()
        ]
    return json.dumps({
        "body_part_catalog": catalog,
        "sources": sources,
    }, ensure_ascii=False)


def _request_uncached(prompt_json: str, provider: str, model: str) -> str:
    if provider == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=int(_ANATOMY_PROVIDER_TIMEOUT_SECONDS * 1000)),
        )
        response = client.models.generate_content(
            model=model,
            contents=[ANATOMY_SYSTEM_PROMPT, prompt_json],
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                response_mime_type="application/json",
                response_schema=_SCHEMA,
            ),
        )
        content = getattr(response, "text", None)
    elif provider in {"groq", "openrouter"}:
        from openai import OpenAI

        client = OpenAI(
            api_key=_anatomy_groq_api_key() if provider == "groq" else settings.openrouter_api_key,
            base_url=(
                "https://api.groq.com/openai/v1"
                if provider == "groq"
                else "https://openrouter.ai/api/v1"
            ),
            timeout=_ANATOMY_PROVIDER_TIMEOUT_SECONDS,
            max_retries=0,
        )
        options: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": ANATOMY_SYSTEM_PROMPT},
                {"role": "user", "content": prompt_json},
            ],
            "temperature": 0,
            # Structured findings can be verbose because each item carries an
            # exact evidence quote and one or more validated body regions.
            # Leave enough room for the full JSON document rather than letting
            # the provider truncate it before a valid response is produced.
            "max_completion_tokens": 8192,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "anatomy_findings",
                    "strict": True,
                    "schema": _groq_strict_schema(),
                },
            },
        }
        if model.casefold().startswith("openai/gpt-oss-"):
            options["extra_body"] = {"include_reasoning": False}
        response = client.chat.completions.create(**options)
        content = response.choices[0].message.content if response.choices else None
    else:
        raise ValueError(f"Unsupported anatomy LLM provider: {provider}")

    if not isinstance(content, str) or not content.strip():
        raise ValueError("Anatomy LLM returned an empty response.")
    return content


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _provider_credential(provider: str) -> str:
    return {
        "gemini": settings.gemini_api_key or "",
        "groq": _anatomy_groq_api_key() or "",
        "openrouter": settings.openrouter_api_key or "",
    }.get(provider, "")


def _provider_error_diagnostics(exc: Exception) -> tuple[int | None, str | None, str | None, str | None]:
    """Extract bounded API error fields without logging full request/error payloads."""
    status_code = getattr(exc, "status_code", None)
    request_id = getattr(exc, "request_id", None)
    body = getattr(exc, "body", None)
    error = body.get("error", body) if isinstance(body, dict) else None
    if not isinstance(error, dict):
        error = {}

    code = error.get("code")
    message = error.get("message")
    # Keep diagnostic fields single-line and bounded. Never log the full body,
    # because upstream errors can include request details.
    safe_message = None
    if isinstance(message, str):
        safe_message = " ".join(message.split())[:240] or None
    safe_code = str(code)[:80] if isinstance(code, (str, int)) else None
    safe_request_id = str(request_id)[:100] if request_id else None
    return status_code, safe_code, safe_message, safe_request_id


def _response_cache_key(
    prompt_json: str,
    provider: str,
    model: str,
    cache_scope: str | None,
) -> tuple[str, ...]:
    prompt_version = _digest(
        _ANATOMY_PROMPT_SCHEMA_VERSION
        + ANATOMY_SYSTEM_PROMPT
        + json.dumps(_SCHEMA, sort_keys=True, separators=(",", ":"))
    )
    return (
        _digest(cache_scope or "global"),
        _digest(prompt_json),
        provider,
        model,
        prompt_version,
        _digest(_provider_credential(provider)),
    )


def _cached_validated_response(key: tuple[str, ...]) -> dict[str, Any] | None:
    now = time.monotonic()
    with _ANATOMY_RESPONSE_CACHE_LOCK:
        entry = _ANATOMY_RESPONSE_CACHE.get(key)
        if entry is None:
            return None
        expires_at, parsed = entry
        if expires_at <= now:
            _ANATOMY_RESPONSE_CACHE.pop(key, None)
            return None
        _ANATOMY_RESPONSE_CACHE.move_to_end(key)
        return deepcopy(parsed)


def _store_validated_response(key: tuple[str, ...], parsed: dict[str, Any]) -> None:
    with _ANATOMY_RESPONSE_CACHE_LOCK:
        _ANATOMY_RESPONSE_CACHE[key] = (
            time.monotonic() + _ANATOMY_CACHE_TTL_SECONDS,
            deepcopy(parsed),
        )
        _ANATOMY_RESPONSE_CACHE.move_to_end(key)
        while len(_ANATOMY_RESPONSE_CACHE) > _ANATOMY_CACHE_MAX_ENTRIES:
            _ANATOMY_RESPONSE_CACHE.popitem(last=False)


def _parse_complete_response(content: str) -> dict[str, Any]:
    try:
        parsed = json.loads(content)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("Anatomy LLM returned invalid JSON.") from exc
    if not isinstance(parsed, dict) or not isinstance(parsed.get("findings"), list):
        raise ValueError("Anatomy LLM response did not contain a findings list.")
    for item in parsed["findings"]:
        if not isinstance(item, dict):
            raise ValueError("Anatomy LLM response contained an invalid finding.")
        if (
            not isinstance(item.get("source_id"), str)
            or item.get("finding_type") not in _FINDING_TYPES
            or not isinstance(item.get("label"), str)
            or not isinstance(item.get("concept"), str)
            or item.get("assertion") not in _ASSERTIONS
            or not isinstance(item.get("body_regions"), list)
            or item.get("laterality") not in {"unspecified", "left", "right", "bilateral"}
            or not isinstance(item.get("evidence_text"), str)
        ):
            raise ValueError("Anatomy LLM response contained an incomplete finding.")
        if any(
            not isinstance(region, dict)
            or not isinstance(region.get("body_part"), str)
            or not isinstance(region.get("marker_id"), str)
            for region in item["body_regions"]
        ):
            raise ValueError("Anatomy LLM response contained an incomplete body region.")
    return parsed


def _batch_log_source_id(sources: list[dict[str, str]]) -> str:
    identifiers = "|".join(sorted(source["source_id"] for source in sources))
    return _digest(identifiers)[:16]


def _request_batch(
    prompt_json: str,
    sources: list[dict[str, str]],
    providers: list[tuple[str, str]],
    *,
    run_id: str,
    batch_index: int,
    batch_count: int,
    cache_scope: str | None,
    force_refresh: bool,
) -> tuple[dict[str, Any], str, str]:
    source_token = _batch_log_source_id(sources)
    cache_started = time.perf_counter()
    if not force_refresh:
        for provider, model in providers:
            key = _response_cache_key(prompt_json, provider, model, cache_scope)
            cached = _cached_validated_response(key)
            if cached is not None:
                _LOGGER.info(
                    "Anatomy timing run_id=%s stage=cache_hit provider=%s model=%s source_count=%d source_id=%s batch=%d/%d elapsed_ms=%.3f",
                    run_id, provider, model, len(sources), source_token, batch_index, batch_count,
                    (time.perf_counter() - cache_started) * 1000,
                )
                return cached, provider, model
    _LOGGER.info(
        "Anatomy timing run_id=%s stage=cache_miss source_count=%d source_id=%s batch=%d/%d elapsed_ms=%.3f",
        run_id, len(sources), source_token, batch_index, batch_count,
        (time.perf_counter() - cache_started) * 1000,
    )

    errors: list[str] = []
    last_error: Exception | None = None
    for provider_index, (provider, model) in enumerate(providers):
        with _PROVIDER_COOLDOWNS_LOCK:
            cooldown_until = _PROVIDER_COOLDOWNS.get(provider, 0.0)
        if cooldown_until > time.monotonic():
            _LOGGER.info(
                "Anatomy timing run_id=%s stage=provider_cooldown provider=%s model=%s source_count=%d source_id=%s remaining_ms=%.0f",
                run_id, provider, model, len(sources), source_token,
                (cooldown_until - time.monotonic()) * 1000,
            )
            continue
        if provider_index:
            _LOGGER.info(
                "Anatomy timing run_id=%s stage=provider_fallback provider=%s model=%s fallback_provider=%s fallback_model=%s source_count=%d source_id=%s",
                run_id, providers[provider_index - 1][0], providers[provider_index - 1][1],
                provider, model, len(sources), source_token,
            )
        started = time.perf_counter()
        for attempt in range(2):
            try:
                content = _request_uncached(prompt_json, provider, model)
                parsed = _parse_complete_response(content)
                _store_validated_response(
                    _response_cache_key(prompt_json, provider, model, cache_scope),
                    parsed,
                )
                _LOGGER.info(
                    "Anatomy timing run_id=%s stage=request_complete provider=%s model=%s source_count=%d source_id=%s batch=%d/%d elapsed_ms=%.0f",
                    run_id, provider, model, len(sources), source_token,
                    batch_index, batch_count, (time.perf_counter() - started) * 1000,
                )
                return parsed, provider, model
            except Exception as exc:
                last_error = exc
                errors.append(f"{provider}/{model}:{type(exc).__name__}")
                status_code, error_code, error_message, request_id = _provider_error_diagnostics(exc)
                # A short retry helps transient server errors. Rate limits move
                # directly to fallback providers to avoid waiting on Retry-After.
                if attempt == 0 and status_code in {500, 502, 503, 504}:
                    wait_seconds = 0.5
                    _LOGGER.warning(
                        "Anatomy timing run_id=%s stage=retry_wait provider=%s model=%s source_count=%d source_id=%s wait_ms=%.0f",
                        run_id, provider, model, len(sources), source_token, wait_seconds * 1000,
                    )
                    time.sleep(wait_seconds)
                    continue
                with _PROVIDER_COOLDOWNS_LOCK:
                    _PROVIDER_COOLDOWNS[provider] = time.monotonic() + (10.0 if status_code == 429 else 30.0)
                _LOGGER.warning(
                    "Anatomy timing run_id=%s stage=provider_failed provider=%s model=%s source_count=%d source_id=%s error_type=%s status_code=%s error_code=%s error_message=%r request_id=%s elapsed_ms=%.0f",
                    run_id, provider, model, len(sources), source_token,
                    type(exc).__name__, status_code, error_code, error_message, request_id,
                    (time.perf_counter() - started) * 1000,
                )
                break
    summary = ",".join(errors) or "no provider available"
    raise RuntimeError(f"Configured anatomy LLM providers failed: {summary}") from last_error


def _explicit_body_part(body_part: str, evidence_text: str) -> bool:
    normalized_part = " ".join(body_part.casefold().split())
    normalized_quote = " ".join(evidence_text.casefold().split())
    return bool(normalized_part and normalized_part in normalized_quote)


def _explicit_laterality(evidence_text: str) -> str:
    """Only report a side when the source quote states it explicitly."""
    normalized_quote = " ".join(evidence_text.casefold().split())
    if re.search(r"\b(?:bilateral|both sides|both eyes)\b", normalized_quote):
        return "bilateral"
    has_left = bool(re.search(r"\bleft\b", normalized_quote))
    has_right = bool(re.search(r"\bright\b", normalized_quote))
    if has_left and not has_right:
        return "left"
    if has_right and not has_left:
        return "right"
    return "unspecified"


def _group(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str | None], dict[str, Any]] = {}
    for finding in findings:
        key = (finding["finding_id"], finding["assertion"], finding["body_region"])
        group = grouped.get(key)
        if group is None:
            group = {**finding, "sources": [], "lateralities": []}
            group.pop("source", None)
            group.pop("evidence_text", None)
            grouped[key] = group
        laterality = finding.get("laterality")
        if laterality and laterality != "unspecified" and laterality not in group["lateralities"]:
            group["lateralities"].append(laterality)
        source = finding["source"]
        identity = source.get("document_id") or (source.get("title"), source.get("date"))
        existing = next(
            (item for item in group["sources"] if (item.get("document_id") or (item.get("title"), item.get("date"))) == identity),
            None,
        )
        if existing is None:
            group["sources"].append(source)
        else:
            excerpts = [existing.get("evidence_text"), source.get("evidence_text")]
            existing["evidence_text"] = " … ".join(dict.fromkeys(text for text in excerpts if text))
    entities = list(grouped.values())
    for entity in entities:
        entity["entity_id"] = ":".join((
            entity["finding_id"],
            entity["assertion"],
            entity["body_region"] or "unspecified",
        ))
    return entities


def derive_anatomy_findings_with_llm(
    documents: list[dict[str, Any]],
    *,
    force_refresh: bool = False,
    patient_id: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]] | None:
    """Use the configured clinical NLP provider; return None when unavailable.

    The LLM decides which findings are supported. Local validation still checks
    that each quote belongs to its stated source and that every model region is
    explicitly named in that quote before assigning a fixed mannequin marker.
    """
    started = time.perf_counter()
    run_id = run_id or str(uuid4())
    providers = _configured_providers()
    if not providers:
        return None

    source_map: dict[str, dict[str, Any]] = {}
    payload: list[dict[str, str]] = []
    for index, document in enumerate(documents):
        if not isinstance(document, dict):
            continue
        text_parts = [document.get(key) for key in ("extracted_text", "text", "content")]
        text = " ".join(part.strip() for part in text_parts if isinstance(part, str) and part.strip())
        if not text:
            continue
        source_id = str(document.get("source_document_id") or document.get("document_id") or f"source-{index}")
        # A duplicate source ID should not redirect an LLM result to a different record.
        if source_id in source_map:
            source_id = f"{source_id}-{index}"
        source_map[source_id] = document
        payload.append({
            "source_id": source_id,
            "title": str(document.get("title") or document.get("document_type") or "Clinical evidence"),
            "text": text[:6000],
        })

    if not payload:
        return []

    output_items: list[dict[str, Any]] = []
    batch: list[dict[str, str]] = []
    batch_chars = 0
    batches: list[list[dict[str, str]]] = []
    for source in payload:
        size = len(source["text"])
        if batch and (len(batch) >= 4 or batch_chars + size > 10000):
            batches.append(batch)
            batch = []
            batch_chars = 0
        batch.append(source)
        batch_chars += size
    if batch:
        batches.append(batch)

    source_token = _digest("|".join(sorted(source["source_id"] for source in payload)))[:16]
    catalog_started = time.perf_counter()
    model_catalog = [
        {"marker_id": part["id"], "body_part": part["body_part"]}
        for part in get_model_body_part_catalog()
    ]
    _LOGGER.info(
        "Anatomy timing run_id=%s stage=model_anchor_catalog anchor_count=%d elapsed_ms=%.0f",
        run_id, len(model_catalog), (time.perf_counter() - catalog_started) * 1000,
    )
    prompt_started = time.perf_counter()
    prompts = [_prompt_for_sources(sources, model_catalog) for sources in batches]
    _LOGGER.info(
        "Anatomy timing run_id=%s stage=prompts_prepared source_count=%d source_id=%s batch_count=%d elapsed_ms=%.0f",
        run_id, len(payload), source_token, len(batches),
        (time.perf_counter() - prompt_started) * 1000,
    )

    concurrency = max(1, min(4, int(getattr(settings, "anatomy_ai_max_concurrency", 2) or 1)))
    _LOGGER.info(
        "Anatomy timing run_id=%s stage=processing_start source_count=%d source_id=%s batch_count=%d max_concurrency=%d",
        run_id, len(payload), source_token, len(batches), concurrency,
    )
    batch_results: list[tuple[dict[str, Any], str, str] | None] = [None] * len(batches)
    batch_errors: list[Exception] = []
    if concurrency == 1 or len(batches) <= 1:
        for index, (sources, prompt_json) in enumerate(zip(batches, prompts)):
            batch_results[index] = _request_batch(
                prompt_json, sources, providers,
                run_id=run_id, batch_index=index + 1, batch_count=len(batches),
                cache_scope=patient_id, force_refresh=force_refresh,
            )
    else:
        concurrent_started = time.perf_counter()
        _LOGGER.info(
            "Anatomy timing run_id=%s stage=concurrency_start source_count=%d source_id=%s batches=%d max_workers=%d",
            run_id, len(payload), source_token, len(batches), concurrency,
        )
        with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="signal-anatomy") as executor:
            futures = {
                executor.submit(
                    _request_batch,
                    prompt_json,
                    sources,
                    providers,
                    run_id=run_id,
                    batch_index=index + 1,
                    batch_count=len(batches),
                    cache_scope=patient_id,
                    force_refresh=force_refresh,
                ): index
                for index, (sources, prompt_json) in enumerate(zip(batches, prompts))
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    batch_results[index] = future.result()
                except Exception as exc:
                    batch_errors.append(exc)
        _LOGGER.info(
            "Anatomy timing run_id=%s stage=concurrency_complete source_count=%d source_id=%s batches=%d failed_batches=%d elapsed_ms=%.0f",
            run_id, len(payload), source_token, len(batches), len(batch_errors),
            (time.perf_counter() - concurrent_started) * 1000,
        )
    if batch_errors:
        raise RuntimeError(
            f"Anatomy extraction failed for {len(batch_errors)} source batch(es)."
        ) from batch_errors[0]

    for batch_index, (sources, result) in enumerate(zip(batches, batch_results), start=1):
        if result is None:
            raise RuntimeError("Anatomy extraction did not return a complete batch result.")
        parsed, provider, model = result
        _LOGGER.info(
            "Anatomy timing run_id=%s stage=batch_validated provider=%s model=%s source_count=%d source_id=%s batch=%d/%d findings=%d",
            run_id, provider, model, len(sources), _batch_log_source_id(sources),
            batch_index, len(batches), len(parsed["findings"]),
        )
        for item in parsed["findings"]:
            if not isinstance(item, dict):
                continue
            source_id = item.get("source_id")
            if not isinstance(source_id, str):
                continue
            source_document = source_map.get(source_id)
            kind = item.get("finding_type")
            assertion = item.get("assertion")
            quote = item.get("evidence_text")
            concept = item.get("concept")
            if (
                source_document is None
                or not isinstance(kind, str)
                or kind not in _FINDING_TYPES
                or not isinstance(assertion, str)
                or assertion not in _ASSERTIONS
                or not isinstance(quote, str)
                or not quote.strip()
                or not isinstance(concept, str)
                or not concept.strip()
            ):
                continue
            normalized_source = " ".join(
                part.strip()
                for part in (source_document.get("extracted_text"), source_document.get("text"), source_document.get("content"))
                if isinstance(part, str) and part.strip()
            )
            if " ".join(quote.split()).casefold() not in " ".join(normalized_source.split()).casefold():
                continue

            raw_regions = item.get("body_regions") if isinstance(item.get("body_regions"), list) else []
            valid_regions: list[tuple[str, dict[str, str]]] = []
            seen_regions: set[tuple[str, str]] = set()
            for region in raw_regions:
                if not isinstance(region, dict):
                    continue
                body_part = region.get("body_part")
                marker_id = region.get("marker_id")
                if not isinstance(body_part, str) or not _explicit_body_part(body_part, quote):
                    continue
                marker = get_anatomy_marker(marker_id if isinstance(marker_id, str) else None)
                region_anchor = get_anatomy_marker_for_region(body_part)
                if marker is None or region_anchor is None or marker["id"] != region_anchor["id"]:
                    continue
                identity = (body_part.casefold(), marker["id"])
                if identity not in seen_regions:
                    valid_regions.append((body_part.strip(), marker))
                    seen_regions.add(identity)
            # Unlocated symptoms and findings are intentionally excluded from
            # the anatomy list, even when they are clinically important.
            if not valid_regions:
                continue
            # Treat laterality like body location: the model may normalize it,
            # but it cannot add a side that is absent from the quoted evidence.
            laterality = _explicit_laterality(quote)
            source_id_for_record = source_document.get("source_document_id") or source_document.get("document_id")
            source = {
                "document_id": str(source_id_for_record) if source_id_for_record else None,
                "title": source_document.get("title") or source_document.get("document_type") or "Clinical evidence",
                "date": source_document.get("document_date"),
                "source_type": (source_document.get("provenance") or {}).get("source_resource"),
                "evidence_kind": source_document.get("evidence_kind", "clinical_document"),
            }
            raw_label = item.get("label")
            label = _LABELS.get(kind) or (raw_label.strip() if isinstance(raw_label, str) and raw_label.strip() else concept.strip().capitalize())
            for body_part, anchor in valid_regions:
                marker = {
                    **anchor,
                    "model_anchor_id": anchor["id"],
                    "id": f"{kind}-{anchor['id']}",
                    "label": f"{label} · {body_part}",
                    "aria_label": f"Documented {concept.strip()} affecting {body_part}",
                }
                output_items.append({
                    "finding_id": kind,
                    "label": label,
                    "concept": concept.strip(),
                    "assertion": assertion,
                    "temporality": "historical" if assertion == "historical" else "current_or_unspecified",
                    "body_region": body_part,
                    "laterality": laterality,
                    "marker": marker if assertion == "present" else None,
                    "evidence_text": quote.strip()[:480],
                    "source": {**source, "evidence_text": quote.strip()[:480]},
                    "extraction_method": "llm_with_evidence_validation",
                })

    grouped = _group(output_items)
    _LOGGER.info(
        "Anatomy timing run_id=%s stage=extraction_complete source_count=%d source_id=%s findings=%d elapsed_ms=%.0f",
        run_id, len(payload), source_token, len(grouped),
        (time.perf_counter() - started) * 1000,
    )
    return grouped
