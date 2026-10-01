from typing import Any


def process_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Process clinical documents for downstream NLP analysis.

    Input:
        List of clinical documents from the canonical patient context.

    Output:
        List of documents prepared for the NLP evidence agent.
    """

    processed_documents = []

    for document in documents:
        processed_documents.append(
            {
                "document_id": document.get("document_id"),
                "patient_id": document.get("patient_id"),
                "document_type": document.get("document_type"),
                "title": document.get("title"),
                "document_date": document.get("document_date"),
                "text": document.get("extracted_text")
                or document.get("text"),
            }
        )

    return processed_documents
