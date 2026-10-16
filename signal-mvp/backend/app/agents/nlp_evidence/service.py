from __future__ import annotations

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from ...ai_detection_logging import get_ai_detection_logger
from ...config.settings import settings
from ...prompts.nlp_evidence import NLP_EVIDENCE_SYSTEM_PROMPT
from .cache import (
    cache_fingerprint,
    cache_key as _evidence_cache_key,
    get_cached as _get_cached_evidence,
    prune_patient_sources,
    source_content_hash,
    source_identity,
    store_cached as _store_cached_evidence,
    stable_schema_fingerprint,
)

logger = get_ai_detection_logger()


class DocumentAIUnavailableError(RuntimeError):
    """Raised when neither configured AI provider can process documents."""


DOCUMENT_AI_UNAVAILABLE_MESSAGE = (
    "AI processing could not be performed because no configured AI provider was available."
)

_GROQ_RATE_LIMIT_RETRIES = 2
_GROQ_MAX_RETRY_DELAY_SECONDS = 30.0


def _run_detection_groq_api_key() -> str | None:
    """Return the Run Detection key, falling back to the legacy shared key."""
    return getattr(settings, "groq_run_detection_api_key", None) or getattr(settings, "groq_api_key", None)


def _groq_retry_delay(exc: Exception, attempt: int) -> float:
    """Choose a bounded wait, honoring Groq's retry guidance when provided."""

    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", {}) or {}
    retry_after = headers.get("retry-after")
    if retry_after:
        try:
            return min(float(retry_after), _GROQ_MAX_RETRY_DELAY_SECONDS)
        except (TypeError, ValueError):
            pass

    reset = headers.get("x-ratelimit-reset-tokens")
    if reset:
        match = re.search(r"[0-9]+(?:\.[0-9]+)?", str(reset))
        if match:
            return min(float(match.group()), _GROQ_MAX_RETRY_DELAY_SECONDS)

    # Groq sometimes puts the wait time only in the 429 error message.
    match = re.search(r"try again in\s+([0-9]+(?:\.[0-9]+)?)\s*s", str(exc), re.IGNORECASE)
    if match:
        return min(float(match.group(1)), _GROQ_MAX_RETRY_DELAY_SECONDS)

    return min(2.0 ** attempt, _GROQ_MAX_RETRY_DELAY_SECONDS)


def _create_groq_completion(
    client: Any,
    request_options: dict[str, Any],
    *,
    run_id: str,
    source_id: str,
    model: str,
) -> Any:
    """Retry Groq rate-limit responses a small number of times."""

    for attempt in range(_GROQ_RATE_LIMIT_RETRIES + 1):
        try:
            return client.chat.completions.create(**request_options)
        except Exception as exc:
            if getattr(exc, "status_code", None) != 429 or attempt >= _GROQ_RATE_LIMIT_RETRIES:
                raise
            delay = _groq_retry_delay(exc, attempt)
            logger.warning(
                "AI timing run_id=%s stage=retry_wait provider=groq model=%s source_count=1 source_id=%s attempt=%d/%d wait_ms=%.0f",
                run_id,
                model,
                source_id,
                attempt + 1,
                _GROQ_RATE_LIMIT_RETRIES,
                delay * 1000,
            )
            time.sleep(delay)


def _provider_prompt(provider: str) -> str:
    if provider == "groq":
        return (
            NLP_EVIDENCE_SYSTEM_PROMPT
            + "\n\n"
            + "Return one JSON object with exactly one top-level field named "
            + "'evidence', containing an array. Each item must contain exactly "
            + "evidence_type, concept, evidence_text, assertion, temporality, "
            + "and confidence. Use only the six evidence types and the assertion "
            + "and temporality values defined above. Extract every explicitly "
            + "documented condition and finding, regardless of disease name. "
            + 'If none are present, return {"evidence": []}. Do not add '
            + "markdown or explanatory text."
        )
    if provider == "openrouter":
        return (
            NLP_EVIDENCE_SYSTEM_PROMPT
            + "\nReturn strictly valid JSON with one top-level 'evidence' array. "
            + "Each item must include evidence_type, concept, evidence_text, "
            + "assertion, temporality, and confidence. Extract only evidence "
            + "explicitly supported by the supplied source text."
        )
    return NLP_EVIDENCE_SYSTEM_PROMPT


def _cache_key_for_document(document: dict[str, Any], provider: str, model: str) -> tuple[str, ...]:
    api_key = {
        "gemini": getattr(settings, "gemini_api_key", None),
        "groq": _run_detection_groq_api_key(),
        "openrouter": getattr(settings, "openrouter_api_key", None),
    }.get(provider) or ""
    prompt_version = cache_fingerprint(
        _provider_prompt(provider)
        + ("\nOutput strictly valid JSON. Begin with { and end with }." if provider == "groq" else "")
        + stable_schema_fingerprint(_GEMINI_EVIDENCE_SCHEMA if provider == "gemini" else _EVIDENCE_SCHEMA)
    )
    return _evidence_cache_key(
        document,
        provider=provider,
        model=model,
        prompt_schema_version=prompt_version,
        credential_fingerprint=cache_fingerprint(api_key),
    )


def _cached_document_evidence(
    document: dict[str, Any], *, provider: str, model: str, run_id: str
) -> list[dict[str, Any]] | None:
    started = time.perf_counter()
    key = _cache_key_for_document(document, provider, model)
    cached_items = _get_cached_evidence(key)
    source_id = source_identity(document)
    if cached_items is None:
        logger.info(
            "AI timing run_id=%s stage=cache_miss provider=%s model=%s source_count=1 source_id=%s elapsed_ms=%.3f",
            run_id, provider, model, source_id, (time.perf_counter() - started) * 1000,
        )
        return None
    normalized = _normalize_evidence(cached_items, document)
    logger.info(
        "AI timing run_id=%s stage=cache_hit provider=%s model=%s source_count=1 source_id=%s evidence_count=%d elapsed_ms=%.3f",
        run_id, provider, model, source_id, len(normalized), (time.perf_counter() - started) * 1000,
    )
    return normalized


def _cache_complete_response(
    document: dict[str, Any], extracted: list[Any], normalized: list[dict[str, Any]],
    *, provider: str, model: str,
) -> None:
    # An empty list is a valid complete answer. Partially rejected model output
    # remains usable for this response, but is not reusable from the cache.
    if len(extracted) == len(normalized):
        _store_cached_evidence(_cache_key_for_document(document, provider, model), extracted)


def _safe_error_kind(exc: Exception) -> str:
    # Provider exception messages can echo request details; record only type.
    return type(exc).__name__


def _provider_model(provider: str) -> str:
    return {
        "gemini": getattr(settings, "gemini_model", "gemini-3.8-flash"),
        "groq": getattr(settings, "groq_model", "openai/gpt-oss-20b"),
        "openrouter": getattr(settings, "openrouter_model", "openai/gpt-oss-20b"),
    }.get(provider, "unknown")


def _log_provider_fallback(
    run_id: str,
    provider: str,
    fallback: str,
    documents: list[dict[str, Any]],
    started: float,
) -> None:
    logger.info(
        "AI timing run_id=%s stage=provider_fallback provider=%s model=%s fallback_provider=%s fallback_model=%s source_count=%d source_id=%s elapsed_ms=%.0f",
        run_id, provider, _provider_model(provider), fallback, _provider_model(fallback),
        len(documents), source_identity(documents[0]) if len(documents) == 1 else "batch",
        (time.perf_counter() - started) * 1000,
    )


def _run_provider_documents_concurrently(
    documents: list[dict[str, Any]],
    *,
    run_id: str,
    provider: str,
    model: str,
    worker: Callable[[dict[str, Any]], list[dict[str, Any]]],
) -> list[dict[str, Any]] | None:
    """Run independent sources with a small cap; ``None`` requests sequential mode."""
    concurrency = max(1, min(4, int(getattr(settings, "detection_ai_max_concurrency", 2) or 1)))
    if concurrency <= 1 or len(documents) <= 1:
        return None

    started = time.perf_counter()
    logger.info(
        "AI timing run_id=%s stage=concurrency_start provider=%s model=%s source_count=%d max_workers=%d",
        run_id, provider, model, len(documents), concurrency,
    )
    results: list[list[dict[str, Any]] | None] = [None] * len(documents)
    failures: list[Exception] = []
    with ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="signal-evidence") as executor:
        futures = {
            executor.submit(worker, document): index
            for index, document in enumerate(documents)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                failures.append(exc)
    logger.info(
        "AI timing run_id=%s stage=concurrency_complete provider=%s model=%s source_count=%d completed_sources=%d failed_sources=%d elapsed_ms=%.0f",
        run_id, provider, model, len(documents),
        sum(result is not None for result in results), len(failures),
        (time.perf_counter() - started) * 1000,
    )
    if failures:
        # Raising to the existing provider selection flow preserves whole-batch
        # fallback semantics if any source fails.
        raise failures[0]
    return [item for result in results if result is not None for item in result]


_EVIDENCE_TYPES = {
    "symptom",
    "diagnosis",
    "finding",
    "laboratory",
    "exposure",
    "epidemiology",
}

_ASSERTIONS = {
    "present",
    "absent",
    "uncertain",
}

_TEMPORALITIES = {
    "current",
    "historical",
    "unknown",
}


# Shared response schema for supported AI providers.
_EVIDENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "evidence_type": {
                        "type": "string",
                        "enum": [
                            "symptom",
                            "diagnosis",
                            "finding",
                            "laboratory",
                            "exposure",
                            "epidemiology",
                        ],
                    },
                    "concept": {
                        "type": "string",
                    },
                    "evidence_text": {
                        "type": "string",
                    },
                    "assertion": {
                        "type": "string",
                        "enum": [
                            "present",
                            "absent",
                            "uncertain",
                        ],
                    },
                    "temporality": {
                        "type": "string",
                        "enum": [
                            "current",
                            "historical",
                            "unknown",
                        ],
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                },
                "required": [
                    "evidence_type",
                    "concept",
                    "evidence_text",
                    "assertion",
                    "temporality",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "evidence",
    ],
    "additionalProperties": False,
}


def _gemini_compatible_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Copy the JSON schema while removing keywords Gemini's API rejects."""

    if isinstance(schema, dict):
        return {
            key: _gemini_compatible_schema(value)
            for key, value in schema.items()
            if key != "additionalProperties"
        }
    if isinstance(schema, list):
        return [_gemini_compatible_schema(value) for value in schema]
    return schema


_GEMINI_EVIDENCE_SCHEMA = _gemini_compatible_schema(_EVIDENCE_SCHEMA)


def extract_evidence(
    documents: list[dict[str, Any]],
    *,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """
    Extract clinical evidence from documents.

    Provider is selected using:

        LLM_PROVIDER=gemini

    or:

        LLM_PROVIDER=groq

    or:

    LLM_PROVIDER=openrouter
    """

    if not isinstance(documents, list):
        raise ValueError("documents must be a list.")

    run_id = run_id or "untracked"

    documents_with_text = [
        document
        for document in documents
        if (
            isinstance(document, dict)
            and isinstance(document.get("text"), str)
            and document["text"].strip()
        )
    ]

    if not documents_with_text:
        logger.warning("AI checkpoint run_id=%s stage=validate result=no_document_text", run_id)
        return []

    provider = (
        getattr(
            settings,
            "llm_provider",
            "gemini",
        )
        or "gemini"
    ).strip().casefold()

    patient_id = str(documents_with_text[0].get("patient_id") or "")
    prune_patient_sources(
        patient_id,
        {
            source_identity(document): source_content_hash(document)
            for document in documents_with_text
        },
    )
    selected_model = _provider_model(provider)
    logger.info(
        "AI timing run_id=%s stage=provider_selected provider=%s model=%s source_count=%d",
        run_id, provider, selected_model, len(documents_with_text),
    )

    provider_started = time.perf_counter()

    if provider == "gemini":
        try:
            return _extract_with_gemini(
                documents_with_text,
                run_id=run_id,
            )
        except Exception as exc:
            logger.warning("AI provider failed run_id=%s provider=gemini model=%s error_type=%s", run_id, selected_model, _safe_error_kind(exc))
            if _run_detection_groq_api_key():
                try:
                    _log_provider_fallback(run_id, "gemini", "groq", documents_with_text, provider_started)
                    return _extract_with_groq(
                        documents_with_text,
                        run_id=run_id,
                    )
                except Exception as fallback_exc:
                    logger.warning("AI provider failed run_id=%s provider=groq model=%s error_type=%s", run_id, _provider_model("groq"), _safe_error_kind(fallback_exc))
            if getattr(settings, "openrouter_api_key", None):
                try:
                    _log_provider_fallback(run_id, "gemini", "openrouter", documents_with_text, provider_started)
                    return _extract_with_openrouter(documents_with_text, run_id=run_id)
                except Exception as fallback_exc:
                    logger.warning("AI provider failed run_id=%s provider=openrouter model=%s error_type=%s", run_id, _provider_model("openrouter"), _safe_error_kind(fallback_exc))
            logger.error(
                "Document processing unavailable | run_id=%s | both AI providers failed.",
                run_id,
            )
            raise DocumentAIUnavailableError(DOCUMENT_AI_UNAVAILABLE_MESSAGE) from exc

    if provider == "groq":
        try:
            return _extract_with_groq(
                documents_with_text,
                run_id=run_id,
            )
        except Exception as exc:
            # If Groq is unavailable, try the configured alternate provider;
            # if that also fails, retain explicit note evidence locally.
            gemini_api_key = getattr(settings, "gemini_api_key", None)
            logger.warning("AI provider failed run_id=%s provider=groq model=%s error_type=%s", run_id, selected_model, _safe_error_kind(exc))
            if gemini_api_key:
                try:
                    _log_provider_fallback(run_id, "groq", "gemini", documents_with_text, provider_started)
                    return _extract_with_gemini(
                        documents_with_text,
                        run_id=run_id,
                    )
                except Exception as fallback_exc:
                    logger.warning("AI provider failed run_id=%s provider=gemini model=%s error_type=%s", run_id, _provider_model("gemini"), _safe_error_kind(fallback_exc))
            if getattr(settings, "openrouter_api_key", None):
                try:
                    _log_provider_fallback(run_id, "groq", "openrouter", documents_with_text, provider_started)
                    return _extract_with_openrouter(documents_with_text, run_id=run_id)
                except Exception as fallback_exc:
                    logger.warning("AI provider failed run_id=%s provider=openrouter model=%s error_type=%s", run_id, _provider_model("openrouter"), _safe_error_kind(fallback_exc))
            logger.error(
                "Document processing unavailable | run_id=%s | both AI providers failed.",
                run_id,
            )
            raise DocumentAIUnavailableError(DOCUMENT_AI_UNAVAILABLE_MESSAGE) from exc

    if provider == "openrouter":
        try:
            return _extract_with_openrouter(documents_with_text, run_id=run_id)
        except Exception as exc:
            logger.warning("AI provider failed run_id=%s provider=openrouter model=%s error_type=%s", run_id, selected_model, _safe_error_kind(exc))
            fallback_errors: list[Exception] = []
            for fallback_provider, api_key in (
                ("gemini", getattr(settings, "gemini_api_key", None)),
                ("groq", _run_detection_groq_api_key()),
            ):
                if not api_key:
                    continue
                try:
                    _log_provider_fallback(run_id, "openrouter", fallback_provider, documents_with_text, provider_started)
                    if fallback_provider == "gemini":
                        return _extract_with_gemini(documents_with_text, run_id=run_id)
                    return _extract_with_groq(documents_with_text, run_id=run_id)
                except Exception as fallback_exc:
                    fallback_errors.append(fallback_exc)
                    logger.warning("AI provider failed run_id=%s provider=%s model=%s error_type=%s", run_id, fallback_provider, _provider_model(fallback_provider), _safe_error_kind(fallback_exc))
            logger.error(
                "Document processing unavailable | run_id=%s | OpenRouter and configured fallback providers failed.",
                run_id,
            )
            raise DocumentAIUnavailableError(DOCUMENT_AI_UNAVAILABLE_MESSAGE) from (fallback_errors[-1] if fallback_errors else exc)

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: '{provider}'. "
        "Use 'gemini', 'groq', or 'openrouter'."
    )


def _build_user_prompt(
    document: dict[str, Any],
) -> str:
    """Build the prompt shared by Gemini and Groq."""

    return (
        f"Patient ID: {document.get('patient_id')}\n\n"
        f"Document ID: {document.get('document_id')}\n\n"
        f"Document Type: {document.get('document_type')}\n\n"
        f"Clinical source text:\n"
        f"{document.get('text', '').strip()}"
    )


def _extract_with_gemini(
    documents: list[dict[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    """Extract evidence using Gemini."""

    api_key = getattr(
        settings,
        "gemini_api_key",
        None,
    )

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured."
        )

    model = getattr(
        settings,
        "gemini_model",
        "gemini-3.8-flash",
    )
    concurrent_result = _run_provider_documents_concurrently(
        documents,
        run_id=run_id,
        provider="gemini",
        model=model,
        worker=lambda document: _extract_with_gemini([document], run_id=run_id),
    )
    if concurrent_result is not None:
        return concurrent_result

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "The Gemini SDK is not installed. "
            "Install it with: pip install google-genai"
        ) from exc

    client = genai.Client(
        api_key=api_key,
        http_options=genai.types.HttpOptions(timeout=30_000),
    )
    logger.info("AI checkpoint run_id=%s stage=client_ready provider=gemini model=%s", run_id, model)

    all_evidence: list[dict[str, Any]] = []
    for document in documents:
        cached = _cached_document_evidence(document, provider="gemini", model=model, run_id=run_id)
        if cached is not None:
            all_evidence.extend(cached)
            continue
        user_prompt = _build_user_prompt(document)
        started = time.monotonic()
        source_id = source_identity(document)
        logger.info(
            "AI timing run_id=%s stage=request_started provider=gemini model=%s source_count=1 source_id=%s text_chars=%d",
            run_id,
            model,
            source_id,
            len(document.get("text", "")),
        )

        try:
            response = client.models.generate_content(
                model=model,
                contents=[
                    NLP_EVIDENCE_SYSTEM_PROMPT,
                    user_prompt,
                ],
                config={
                    "temperature": 0,
                    "response_mime_type": "application/json",
                    "response_schema": _GEMINI_EVIDENCE_SCHEMA,
                },
            )

        except Exception as exc:
            logger.error(
                "AI timing run_id=%s stage=request_failed provider=gemini model=%s source_count=1 source_id=%s elapsed_ms=%.0f error_type=%s",
                run_id,
                model,
                source_id,
                (time.monotonic() - started) * 1000,
                _safe_error_kind(exc),
            )
            raise

        logger.info(
            "AI timing run_id=%s stage=request_succeeded provider=gemini model=%s source_count=1 source_id=%s elapsed_ms=%.0f response_chars=%d",
            run_id,
            model,
            source_id,
            (time.monotonic() - started) * 1000,
            len(getattr(response, "text", None) or ""),
        )

        content = getattr(
            response,
            "text",
            None,
        )

        if not content:
            raise ValueError("Gemini NLP Evidence agent returned an empty response.")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("AI checkpoint run_id=%s stage=response_parse_failed provider=gemini model=%s source_id=%s", run_id, model, source_id)
            raise ValueError(
                "Gemini NLP Evidence agent returned invalid JSON."
            ) from exc

        extracted_evidence = result.get(
            "evidence",
            [],
        )

        if not isinstance(
            extracted_evidence,
            list,
        ):
            raise ValueError("Gemini NLP Evidence agent returned JSON without an evidence array.")

        normalized = _normalize_evidence(extracted_evidence, document)
        all_evidence.extend(normalized)
        _cache_complete_response(
            document, extracted_evidence, normalized, provider="gemini", model=model,
        )

        logger.info(
            "AI checkpoint run_id=%s stage=document_complete provider=gemini model=%s source_id=%s extracted_items=%d",
            run_id,
            model,
            source_id,
            len(extracted_evidence),
        )

    logger.info(
        "AI analysis finished with Gemini: %d evidence item(s) extracted from %d document(s).",
        len(all_evidence),
        len(documents),
    )
    return all_evidence


def _extract_with_groq(
    documents: list[dict[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    """Extract evidence using Groq."""

    api_key = _run_detection_groq_api_key()

    if not api_key:
        raise RuntimeError(
            "GROQ_RUN_DETECTION_API_KEY (or legacy GROQ_API_KEY) is not configured."
        )

    model = getattr(
        settings,
        "groq_model",
        "openai/gpt-oss-20b",
    )
    concurrent_result = _run_provider_documents_concurrently(
        documents,
        run_id=run_id,
        provider="groq",
        model=model,
        worker=lambda document: _extract_with_groq([document], run_id=run_id),
    )
    if concurrent_result is not None:
        return concurrent_result

    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI Python SDK is not installed. "
            "Install it with: pip install openai"
        ) from exc

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,
        max_retries=0,
    )
    logger.info("AI checkpoint run_id=%s stage=client_ready provider=groq model=%s", run_id, model)

    all_evidence: list[dict[str, Any]] = []
    for document in documents:
        cached = _cached_document_evidence(document, provider="groq", model=model, run_id=run_id)
        if cached is not None:
            all_evidence.extend(cached)
            continue
        source_id = source_identity(document)
        user_prompt = _build_user_prompt(document)
        system_prompt = _provider_prompt("groq")
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        request_options: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0,
            "max_completion_tokens": 4096,
            "response_format": {"type": "json_object"},
        }
        # GPT-OSS can return its reasoning separately. Suppress that channel for
        # an extraction endpoint that requires a parseable JSON answer. This is
        # a Groq-specific field; pass it through the OpenAI SDK's extra_body
        # extension because include_reasoning is not a typed SDK argument.
        if model.casefold().startswith("openai/gpt-oss-"):
            request_options["extra_body"] = {"include_reasoning": False}

        started = time.monotonic()
        logger.info(
            "AI timing run_id=%s stage=request_started provider=groq model=%s source_count=1 source_id=%s text_chars=%d",
            run_id,
            model,
            source_id,
            len(document.get("text", "")),
        )

        try:
            response = _create_groq_completion(
                client,
                request_options,
                run_id=run_id,
                source_id=source_id,
                model=model,
            )

        except Exception as exc:
            if "json_validate_failed" in str(exc).casefold():
                logger.warning(
                    "AI checkpoint run_id=%s stage=json_mode_retry provider=groq model=%s source_id=%s",
                    run_id,
                    model,
                    source_id,
                )
                # Some model generations fail Groq's JSON-mode validator before
                # a response is returned. Retry once without response_format;
                # keep the same disease-agnostic output contract and validate
                # the JSON locally below.
                retry_options = {
                    **request_options,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                system_prompt
                                + "\nOutput strictly valid JSON. Begin with { and end with }."
                            ),
                        },
                        {"role": "user", "content": user_prompt},
                    ],
                }
                retry_options.pop("response_format", None)
                try:
                    retry_started = time.monotonic()
                    response = _create_groq_completion(
                        client,
                        retry_options,
                        run_id=run_id,
                        source_id=source_id,
                        model=model,
                    )
                    logger.info(
                        "AI timing run_id=%s stage=json_mode_retry_succeeded provider=groq model=%s source_count=1 source_id=%s elapsed_ms=%.0f",
                        run_id,
                        model,
                        source_id,
                        (time.monotonic() - retry_started) * 1000,
                    )
                except Exception as retry_exc:
                    logger.error(
                        "AI timing run_id=%s stage=json_mode_retry_failed provider=groq model=%s source_count=1 source_id=%s elapsed_ms=%.0f error_type=%s",
                        run_id,
                        model,
                        source_id,
                        (time.monotonic() - started) * 1000,
                        _safe_error_kind(retry_exc),
                    )
                    raise
            else:
                logger.error(
                    "AI timing run_id=%s stage=request_failed provider=groq model=%s source_count=1 source_id=%s elapsed_ms=%.0f error_type=%s",
                    run_id,
                    model,
                    source_id,
                    (time.monotonic() - started) * 1000,
                    _safe_error_kind(exc),
                )
                raise

        logger.info(
            "AI timing run_id=%s stage=request_succeeded provider=groq model=%s source_count=1 source_id=%s elapsed_ms=%.0f",
            run_id,
            model,
            source_id,
            (time.monotonic() - started) * 1000,
        )

        content = response.choices[0].message.content

        if not content:
            logger.error(
                "AI checkpoint run_id=%s stage=empty_response provider=groq model=%s source_id=%s",
                run_id,
                model,
                source_id,
            )
            raise ValueError("Groq NLP Evidence agent returned an empty response.")

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.error("AI checkpoint run_id=%s stage=response_parse_failed provider=groq model=%s source_id=%s", run_id, model, source_id)
            raise ValueError(
                "Groq NLP Evidence agent returned invalid JSON."
            ) from exc

        if not isinstance(result, dict) or not isinstance(result.get("evidence"), list):
            logger.error(
                "AI checkpoint run_id=%s stage=response_shape_invalid provider=groq model=%s source_id=%s",
                run_id,
                model,
                source_id,
            )
            raise ValueError(
                "Groq NLP Evidence agent returned JSON without an evidence array."
            )

        extracted_evidence = result["evidence"]
        normalized_evidence = _normalize_evidence(extracted_evidence, document)
        if extracted_evidence and not normalized_evidence:
            logger.error(
                "AI checkpoint run_id=%s stage=evidence_validation_failed provider=groq model=%s source_id=%s returned_items=%d",
                run_id,
                model,
                source_id,
                len(extracted_evidence),
            )
            raise ValueError(
                "Groq NLP Evidence agent returned evidence that did not match the expected fields."
            )
        if len(normalized_evidence) < len(extracted_evidence):
            logger.warning(
                "AI checkpoint run_id=%s stage=evidence_items_dropped provider=groq model=%s source_id=%s returned_items=%d accepted_items=%d",
                run_id,
                model,
                source_id,
                len(extracted_evidence),
                len(normalized_evidence),
            )
        all_evidence.extend(normalized_evidence)
        _cache_complete_response(
            document, extracted_evidence, normalized_evidence, provider="groq", model=model,
        )

        logger.info(
            "AI checkpoint run_id=%s stage=document_complete provider=groq model=%s source_id=%s extracted_items=%d accepted_items=%d",
            run_id,
            model,
            source_id,
            len(extracted_evidence),
            len(normalized_evidence),
        )

    logger.info(
        "AI analysis finished with Groq: %d evidence item(s) extracted from %d document(s).",
        len(all_evidence),
        len(documents),
    )
    return all_evidence


def _extract_with_openrouter(
    documents: list[dict[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    """Extract evidence using OpenRouter's OpenAI-compatible API."""
    api_key = getattr(settings, "openrouter_api_key", None)
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured.")

    model = getattr(settings, "openrouter_model", "openai/gpt-oss-20b")
    concurrent_result = _run_provider_documents_concurrently(
        documents,
        run_id=run_id,
        provider="openrouter",
        model=model,
        worker=lambda document: _extract_with_openrouter([document], run_id=run_id),
    )
    if concurrent_result is not None:
        return concurrent_result
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "The OpenAI Python SDK is not installed. Install it with: pip install openai"
        ) from exc

    client = OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        timeout=30.0,
        max_retries=0,
    )
    logger.info("AI checkpoint run_id=%s stage=client_ready provider=openrouter model=%s", run_id, model)
    all_evidence: list[dict[str, Any]] = []

    for document in documents:
        cached = _cached_document_evidence(document, provider="openrouter", model=model, run_id=run_id)
        if cached is not None:
            all_evidence.extend(cached)
            continue
        source_id = source_identity(document)
        system_prompt = _provider_prompt("openrouter")
        options: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": _build_user_prompt(document)},
            ],
            "temperature": 0,
            "max_completion_tokens": 4096,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "clinical_evidence",
                    "strict": True,
                    "schema": _EVIDENCE_SCHEMA,
                },
            },
        }
        if model.casefold().startswith("openai/gpt-oss-"):
            options["extra_body"] = {"include_reasoning": False}

        started = time.monotonic()
        logger.info(
            "AI timing run_id=%s stage=request_started provider=openrouter model=%s source_count=1 source_id=%s text_chars=%d",
            run_id,
            model,
            source_id,
            len(document.get("text", "")),
        )
        try:
            response = client.chat.completions.create(**options)
        except Exception as exc:
            logger.error(
                "AI timing run_id=%s stage=request_failed provider=openrouter model=%s source_count=1 source_id=%s elapsed_ms=%.0f error_type=%s",
                run_id, model, source_id, (time.monotonic() - started) * 1000, _safe_error_kind(exc),
            )
            raise
        logger.info(
            "AI timing run_id=%s stage=request_succeeded provider=openrouter model=%s source_count=1 source_id=%s elapsed_ms=%.0f",
            run_id, model, source_id, (time.monotonic() - started) * 1000,
        )
        content = response.choices[0].message.content if response.choices else None
        if not isinstance(content, str) or not content.strip():
            raise ValueError("OpenRouter NLP Evidence agent returned an empty response.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.warning(
                "AI checkpoint run_id=%s stage=response_json_invalid provider=openrouter model=%s source_id=%s response_chars=%d",
                run_id,
                model,
                source_id,
                len(content),
            )
            raise ValueError("OpenRouter NLP Evidence agent returned invalid JSON.") from exc
        if isinstance(parsed, list):
            # Some OpenRouter model responses ignore the requested wrapper and
            # return the evidence items as the JSON root array. Accept that
            # shape only when its contents pass the same local evidence
            # validation as the normal {"evidence": [...]} response.
            extracted_items = parsed
            logger.warning(
                "AI checkpoint run_id=%s stage=response_shape_recovered provider=openrouter model=%s source_id=%s root_type=list item_count=%d",
                run_id,
                model,
                source_id,
                len(extracted_items),
            )
        elif isinstance(parsed, dict) and isinstance(parsed.get("evidence"), list):
            extracted_items = parsed["evidence"]
        else:
            root_type = type(parsed).__name__
            evidence_value = parsed.get("evidence") if isinstance(parsed, dict) else None
            evidence_type = type(evidence_value).__name__ if isinstance(parsed, dict) and "evidence" in parsed else "missing"
            logger.warning(
                "AI checkpoint run_id=%s stage=response_shape_invalid provider=openrouter model=%s source_id=%s root_type=%s evidence_type=%s evidence_count=%s",
                run_id,
                model,
                source_id,
                root_type,
                evidence_type,
                len(evidence_value) if isinstance(evidence_value, list) else "n/a",
            )
            raise ValueError("OpenRouter NLP Evidence agent returned JSON without an evidence array.")

        normalized = _normalize_evidence(extracted_items, document)
        if extracted_items and not normalized:
            first_item = extracted_items[0]
            logger.warning(
                "AI checkpoint run_id=%s stage=evidence_shape_invalid provider=openrouter model=%s source_id=%s evidence_count=%d first_item_type=%s",
                run_id,
                model,
                source_id,
                len(extracted_items),
                type(first_item).__name__,
            )
            raise ValueError("OpenRouter NLP Evidence agent returned no valid evidence items.")
        all_evidence.extend(normalized)
        _cache_complete_response(
            document, extracted_items, normalized, provider="openrouter", model=model,
        )
        logger.info(
            "AI checkpoint run_id=%s stage=document_complete provider=openrouter model=%s source_id=%s extracted_items=%d accepted_items=%d elapsed_ms=%.0f",
            run_id,
            model,
            source_id,
            len(extracted_items),
            len(normalized),
            (time.monotonic() - started) * 1000,
        )

    logger.info(
        "AI analysis finished with OpenRouter: %d evidence item(s) extracted from %d source(s).",
        len(all_evidence),
        len(documents),
    )
    return all_evidence


def _normalize_evidence(
    extracted_evidence: list[Any],
    document: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Normalize evidence so Gemini and Groq return
    the same internal structure.
    """

    normalized: list[dict[str, Any]] = []

    for item in extracted_evidence:
        if not isinstance(
            item,
            dict,
        ):
            continue

        evidence_type = item.get(
            "evidence_type"
        )
        concept = item.get(
            "concept"
        )
        evidence_text = item.get(
            "evidence_text"
        )

        if (
            not isinstance(
                evidence_type,
                str,
            )
            or evidence_type.casefold()
            not in _EVIDENCE_TYPES
            or not isinstance(
                concept,
                str,
            )
            or not concept.strip()
            or not isinstance(
                evidence_text,
                str,
            )
            or not evidence_text.strip()
        ):
            continue

        assertion = str(
            item.get(
                "assertion",
                "uncertain",
            )
        ).casefold()

        if assertion not in _ASSERTIONS:
            assertion = "uncertain"

        temporality = str(
            item.get(
                "temporality",
                "unknown",
            )
        ).casefold()

        if temporality not in _TEMPORALITIES:
            temporality = "unknown"

        confidence = item.get(
            "confidence"
        )

        try:
            confidence = float(
                confidence
            )
        except (
            TypeError,
            ValueError,
        ):
            confidence = None

        if confidence is not None:
            confidence = max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            )

        normalized.append(
            {
                "document_id": document.get(
                    "document_id"
                ),
                "encounter_id": document.get(
                    "encounter_id"
                ),
                "patient_id": document.get(
                    "patient_id"
                ),
                "source_type": document.get(
                    "document_type"
                ),
                "source_title": document.get(
                    "title"
                ),
                "evidence_type": evidence_type.casefold(),
                "concept": concept.strip(),
                "evidence_text": evidence_text.strip(),
                "assertion": assertion,
                "temporality": temporality,
                "confidence": confidence,
            }
        )

    return normalized
