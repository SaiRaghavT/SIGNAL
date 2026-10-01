from __future__ import annotations

import json
from typing import Any

from ...config.settings import settings
from ...prompts.nlp_evidence import NLP_EVIDENCE_SYSTEM_PROMPT


# ---------------------------------------------------------
# NLP Evidence Extraction
# ---------------------------------------------------------

def extract_evidence(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Extract clinical evidence from clinical documents using
    an LLM.

    Input:
        Processed clinical documents.

    Output:
        Structured clinical evidence.

    This agent does NOT determine:
        - jurisdiction
        - reportability
        - case confirmation
        - submission
    """

    if not isinstance(documents, list):
        raise ValueError("documents must be a list.")

    documents_with_text = [
        document
        for document in documents
        if isinstance(document, dict)
        and isinstance(document.get("text"), str)
        and document["text"].strip()
    ]

    if not documents_with_text:
        return []

    api_key = settings.gemini_api_key
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured.")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    all_evidence: list[dict[str, Any]] = []

    for document in documents_with_text:
        text = document.get("text")

        # -------------------------------------------------
        # Build LLM request
        # -------------------------------------------------

        user_prompt = (
            f"Patient ID: {document.get('patient_id')}\n\n"
            f"Document ID: {document.get('document_id')}\n\n"
            f"Document Type: {document.get('document_type')}\n\n"
            f"Clinical Document:\n"
            f"{text.strip()}"
        )

        # -------------------------------------------------
        # Call Gemini
        # -------------------------------------------------

        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=(
                f"{NLP_EVIDENCE_SYSTEM_PROMPT}\n\n"
                f"{user_prompt}"
            ),
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
            ),
        )

        # -------------------------------------------------
        # Parse LLM response
        # -------------------------------------------------

        content = response.text

        if not content:
            continue

        try:
            result = json.loads(content)

        except json.JSONDecodeError as exc:
            raise ValueError(
                "NLP Evidence agent returned invalid JSON."
            ) from exc

        # -------------------------------------------------
        # Extract evidence
        # -------------------------------------------------

        extracted_evidence = result.get(
            "evidence",
            []
        )

        if not isinstance(extracted_evidence, list):
            continue

        for item in extracted_evidence:

            if not isinstance(item, dict):
                continue

            all_evidence.append(
                {
                    "document_id": document.get(
                        "document_id"
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
                    "evidence_type": item.get(
                        "evidence_type"
                    ),
                    "concept": item.get(
                        "concept"
                    ),
                    "evidence_text": item.get(
                        "evidence_text"
                    ),
                    "confidence": item.get(
                        "confidence"
                    ),
                }
            )

    return all_evidence
