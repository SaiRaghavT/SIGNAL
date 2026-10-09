from __future__ import annotations

import json
from typing import Any

from ...config.settings import settings
from ...prompts.nlp_evidence import NLP_EVIDENCE_SYSTEM_PROMPT


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
            },
        },
    },
    "required": [
        "evidence",
    ],
}


def extract_evidence(
    documents: list[dict[str, Any]],
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
        return []

    provider = (
        getattr(
            settings,
            "llm_provider",
            "gemini",
        )
        or "gemini"
    ).strip().casefold()

    if provider == "gemini":
        return _extract_with_gemini(
            documents_with_text
        )

    if provider == "groq":
        return _extract_with_groq(
            documents_with_text
        )

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
    )

    all_evidence: list[dict[str, Any]] = []

    for document in documents:
        user_prompt = _build_user_prompt(document)

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
                },
            )

        except Exception as exc:
            print(
                f"❌ GEMINI ERROR: "
                f"{type(exc).__name__}: {exc}"
            )
            raise

        content = getattr(
            response,
            "text",
            None,
        )

        if not content:
            continue

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
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

    return all_evidence


def _extract_with_groq(
    documents: list[dict[str, Any]],
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
    )

    all_evidence: list[dict[str, Any]] = []

    for document in documents:
        user_prompt = _build_user_prompt(document)

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            NLP_EVIDENCE_SYSTEM_PROMPT
                            + "\n\n"
                            + "You MUST return a JSON object with exactly one "
                            "top-level field named 'evidence'. "
                            "The value of 'evidence' MUST be an array. "
                            "Each evidence item MUST contain exactly these fields: "
                            "evidence_type, concept, evidence_text, assertion, "
                            "temporality, confidence. "
                            "confidence MUST be a numeric value between 0.0 and 1.0 "
                            "representing how strongly the document supports that "
                            "specific evidence item. Use higher values for explicit "
                            "clinical statements and lower values for ambiguous or "
                            "uncertain statements. Do not use 0 unless the evidence "
                            "is essentially unsupported. "
                            "If there is no relevant evidence, return "
                            "{\"evidence\": []}. "
                            "Do not return an empty response. "
                            "Do not include markdown, explanations, or extra fields."
                        ),
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "clinical_evidence",
                        "strict": True,
                        "schema": _EVIDENCE_SCHEMA,
                    },
                },
            )

        except Exception as exc:
            print(
                f"❌ GROQ ERROR: "
                f"{type(exc).__name__}: {exc}"
            )
            raise

        content = response.choices[0].message.content

        if not content:
            continue

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Groq NLP Evidence agent returned invalid JSON."
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
