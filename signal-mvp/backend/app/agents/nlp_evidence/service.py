from __future__ import annotations

import json
import re
import time
from typing import Any

from ...ai_detection_logging import get_ai_detection_logger
from ...config.settings import settings
from ...prompts.nlp_evidence import NLP_EVIDENCE_SYSTEM_PROMPT

logger = get_ai_detection_logger()


class DocumentAIUnavailableError(RuntimeError):
    """Raised when neither configured AI provider can process documents."""


DOCUMENT_AI_UNAVAILABLE_MESSAGE = (
    "AI processing could not be performed because both models are unavailable."
)

_GROQ_RATE_LIMIT_RETRIES = 2
_GROQ_MAX_RETRY_DELAY_SECONDS = 30.0


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


def _create_groq_completion(client: Any, request_options: dict[str, Any], *, run_id: str, document_id: Any) -> Any:
    """Retry Groq rate-limit responses a small number of times."""

    for attempt in range(_GROQ_RATE_LIMIT_RETRIES + 1):
        try:
            return client.chat.completions.create(**request_options)
        except Exception as exc:
            if getattr(exc, "status_code", None) != 429 or attempt >= _GROQ_RATE_LIMIT_RETRIES:
                raise
            delay = _groq_retry_delay(exc, attempt)
            logger.warning(
                "AI checkpoint run_id=%s stage=rate_limit_retry provider=groq document_id=%s attempt=%d/%d wait_seconds=%.2f",
                run_id,
                document_id,
                attempt + 1,
                _GROQ_RATE_LIMIT_RETRIES,
                delay,
            )
            time.sleep(delay)


def _short_error(exc: Exception, limit: int = 500) -> str:
    """Format provider errors as one readable log line without a traceback."""

    message = " ".join(str(exc).split())
    return message[:limit] + ("…" if len(message) > limit else "")


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


# Shared response schema for Gemini and Groq.
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

    logger.info(
        "AI checkpoint run_id=%s stage=provider_selected provider=%s documents=%d",
        run_id,
        provider,
        len(documents_with_text),
    )

    if provider == "gemini":
        try:
            return _extract_with_gemini(
                documents_with_text,
                run_id=run_id,
            )
        except Exception as exc:
            logger.warning(
                "Gemini analysis failed (%s: %s). Trying Groq if configured.",
                type(exc).__name__,
                _short_error(exc),
            )
            if getattr(settings, "groq_api_key", None):
                try:
                    return _extract_with_groq(
                        documents_with_text,
                        run_id=run_id,
                    )
                except Exception as fallback_exc:
                    logger.warning(
                        "Groq fallback also failed (%s: %s).",
                        type(fallback_exc).__name__,
                        _short_error(fallback_exc),
                    )
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
            logger.warning(
                "Groq analysis failed (%s: %s). Trying Gemini if configured.",
                type(exc).__name__,
                _short_error(exc),
            )
            if gemini_api_key:
                try:
                    logger.info(
                        "AI checkpoint run_id=%s stage=provider_fallback provider=groq fallback_provider=gemini documents=%d",
                        run_id,
                        len(documents_with_text),
                    )
                    return _extract_with_gemini(
                        documents_with_text,
                        run_id=run_id,
                    )
                except Exception as fallback_exc:
                    logger.warning(
                        "Gemini fallback also failed (%s: %s).",
                        type(fallback_exc).__name__,
                        _short_error(fallback_exc),
                    )
            logger.error(
                "Document processing unavailable | run_id=%s | both AI providers failed.",
                run_id,
            )
            raise DocumentAIUnavailableError(DOCUMENT_AI_UNAVAILABLE_MESSAGE) from exc

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: '{provider}'. "
        "Use 'gemini' or 'groq'."
    )


def _build_user_prompt(
    document: dict[str, Any],
) -> str:
    """Build the prompt shared by Gemini and Groq."""

    return (
        f"Patient ID: {document.get('patient_id')}\n\n"
        f"Document ID: {document.get('document_id')}\n\n"
        f"Document Type: {document.get('document_type')}\n\n"
        f"Clinical Document:\n"
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
    model_responses: list[tuple[str, str]] = []

    for document in documents:
        user_prompt = _build_user_prompt(document)
        started = time.monotonic()
        logger.info(
            "AI checkpoint run_id=%s stage=request_started provider=gemini document_id=%s text_chars=%d",
            run_id,
            document.get("document_id"),
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
                "Gemini request failed | run_id=%s | model=%s | document_id=%s | elapsed=%.2fs | error=%s: %s",
                run_id,
                model,
                document.get("document_id"),
                time.monotonic() - started,
                type(exc).__name__,
                _short_error(exc),
            )
            raise

        logger.info(
            "AI checkpoint run_id=%s stage=request_succeeded provider=gemini document_id=%s elapsed_seconds=%.2f response_chars=%d",
            run_id,
            document.get("document_id"),
            time.monotonic() - started,
            len(getattr(response, "text", None) or ""),
        )

        content = getattr(
            response,
            "text",
            None,
        )

        if not content:
            continue

        model_responses.append((str(document.get("document_id") or "unknown"), content))

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.exception("AI checkpoint run_id=%s stage=response_parse_failed provider=gemini document_id=%s", run_id, document.get("document_id"))
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
            continue

        all_evidence.extend(
            _normalize_evidence(
                extracted_evidence,
                document,
            )
        )

        logger.info(
            "AI checkpoint run_id=%s stage=document_complete provider=gemini document_id=%s extracted_items=%d",
            run_id,
            document.get("document_id"),
            len(extracted_evidence),
        )

    logger.info(
        "AI analysis finished with Gemini: %d evidence item(s) extracted from %d document(s).",
        len(all_evidence),
        len(documents),
    )
    logger.info(
        "ACTUAL MODEL RESPONSE | run_id=%s | provider=gemini\n%s",
        run_id,
        "\n\n".join(
            f"--- Document {document_id} ---\n{content}"
            for document_id, content in model_responses
        ) or "<The model returned no text response.>",
    )
    return all_evidence


def _extract_with_groq(
    documents: list[dict[str, Any]],
    *,
    run_id: str,
) -> list[dict[str, Any]]:
    """Extract evidence using Groq."""

    api_key = getattr(
        settings,
        "groq_api_key",
        None,
    )

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured."
        )

    model = getattr(
        settings,
        "groq_model",
        "openai/gpt-oss-20b",
    )

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
    model_responses: list[tuple[str, str]] = []

    for document in documents:
        user_prompt = _build_user_prompt(document)
        system_prompt = (
            NLP_EVIDENCE_SYSTEM_PROMPT
            + "\n\n"
            + "Return one JSON object with exactly one top-level field named "
            + "'evidence', containing an array. Each item must contain exactly "
            + "evidence_type, concept, evidence_text, assertion, temporality, "
            + "and confidence. Use only the six evidence types and the assertion "
            + "and temporality values defined above. Extract every explicitly "
            + "documented condition and finding, regardless of disease name. "
            + "If none are present, return {\"evidence\": []}. Do not add "
            + "markdown or explanatory text."
        )
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
            "AI checkpoint run_id=%s stage=request_started provider=groq document_id=%s text_chars=%d",
            run_id,
            document.get("document_id"),
            len(document.get("text", "")),
        )

        try:
            response = _create_groq_completion(
                client,
                request_options,
                run_id=run_id,
                document_id=document.get("document_id"),
            )

        except Exception as exc:
            if "json_validate_failed" in str(exc).casefold():
                logger.warning(
                    "AI checkpoint run_id=%s stage=json_mode_retry provider=groq model=%s document_id=%s",
                    run_id,
                    model,
                    document.get("document_id"),
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
                        document_id=document.get("document_id"),
                    )
                    logger.info(
                        "AI checkpoint run_id=%s stage=json_mode_retry_succeeded provider=groq model=%s document_id=%s elapsed_seconds=%.2f",
                        run_id,
                        model,
                        document.get("document_id"),
                        time.monotonic() - retry_started,
                    )
                except Exception as retry_exc:
                    logger.error(
                        "Groq JSON retry failed | run_id=%s | model=%s | document_id=%s | elapsed=%.2fs | error=%s: %s",
                        run_id,
                        model,
                        document.get("document_id"),
                        time.monotonic() - started,
                        type(retry_exc).__name__,
                        _short_error(retry_exc),
                    )
                    raise
            else:
                logger.error(
                    "Groq request failed | run_id=%s | model=%s | document_id=%s | elapsed=%.2fs | error=%s: %s",
                    run_id,
                    model,
                    document.get("document_id"),
                    time.monotonic() - started,
                    type(exc).__name__,
                    _short_error(exc),
                )
                raise

        logger.info(
            "AI checkpoint run_id=%s stage=request_succeeded provider=groq document_id=%s elapsed_seconds=%.2f",
            run_id,
            document.get("document_id"),
            time.monotonic() - started,
        )

        content = response.choices[0].message.content

        if not content:
            logger.error(
                "AI checkpoint run_id=%s stage=empty_response provider=groq document_id=%s",
                run_id,
                document.get("document_id"),
            )
            raise ValueError("Groq NLP Evidence agent returned an empty response.")

        model_responses.append((str(document.get("document_id") or "unknown"), content))

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            logger.exception("AI checkpoint run_id=%s stage=response_parse_failed provider=groq document_id=%s", run_id, document.get("document_id"))
            raise ValueError(
                "Groq NLP Evidence agent returned invalid JSON."
            ) from exc

        if not isinstance(result, dict) or not isinstance(result.get("evidence"), list):
            logger.error(
                "AI checkpoint run_id=%s stage=response_shape_invalid provider=groq document_id=%s",
                run_id,
                document.get("document_id"),
            )
            raise ValueError(
                "Groq NLP Evidence agent returned JSON without an evidence array."
            )

        extracted_evidence = result["evidence"]
        normalized_evidence = _normalize_evidence(extracted_evidence, document)
        if extracted_evidence and not normalized_evidence:
            logger.error(
                "AI checkpoint run_id=%s stage=evidence_validation_failed provider=groq document_id=%s returned_items=%d",
                run_id,
                document.get("document_id"),
                len(extracted_evidence),
            )
            raise ValueError(
                "Groq NLP Evidence agent returned evidence that did not match the expected fields."
            )
        if len(normalized_evidence) < len(extracted_evidence):
            logger.warning(
                "AI checkpoint run_id=%s stage=evidence_items_dropped provider=groq document_id=%s returned_items=%d accepted_items=%d",
                run_id,
                document.get("document_id"),
                len(extracted_evidence),
                len(normalized_evidence),
            )
        all_evidence.extend(normalized_evidence)

        logger.info(
            "AI checkpoint run_id=%s stage=document_complete provider=groq document_id=%s extracted_items=%d accepted_items=%d",
            run_id,
            document.get("document_id"),
            len(extracted_evidence),
            len(normalized_evidence),
        )

    logger.info(
        "AI analysis finished with Groq: %d evidence item(s) extracted from %d document(s).",
        len(all_evidence),
        len(documents),
    )
    logger.info(
        "ACTUAL MODEL RESPONSE | run_id=%s | provider=groq\n%s",
        run_id,
        "\n\n".join(
            f"--- Document {document_id} ---\n{content}"
            for document_id, content in model_responses
        ) or "<The model returned no text response.>",
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
