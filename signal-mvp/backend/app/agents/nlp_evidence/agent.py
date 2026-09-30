from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI

from app.prompts.nlp_evidence import NLP_EVIDENCE_SYSTEM_PROMPT


# ---------------------------------------------------------
# OpenAI Client
# ---------------------------------------------------------

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY")
)


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

    all_evidence: list[dict[str, Any]] = []

    for document in documents:

        if not isinstance(document, dict):
            continue

        text = document.get("text")

        if not isinstance(text, str) or not text.strip():
            continue

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
        # Call OpenAI
        # -------------------------------------------------

        response = client.chat.completions.create(
            model=os.getenv(
                "OPENAI_MODEL",
                "gpt-4.1-mini",
            ),
            temperature=0,
            response_format={
                "type": "json_object"
            },
            messages=[
                {
                    "role": "system",
                    "content": NLP_EVIDENCE_SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        # -------------------------------------------------
        # Parse LLM response
        # -------------------------------------------------

        content = response.choices[0].message.content

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