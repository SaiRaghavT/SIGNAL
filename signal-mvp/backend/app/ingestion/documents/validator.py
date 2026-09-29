from pathlib import Path


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}

SUPPORTED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

MAX_DOCUMENT_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class DocumentValidationError(ValueError):
    """Raised when an uploaded document fails validation."""


def validate_document(
    file_path: str | Path,
    content_type: str | None = None,
) -> None:
    """
    Validate a document before extraction.

    Checks:
        - File exists
        - File is actually a file
        - File extension is supported
        - Optional content type is supported
        - File size does not exceed the limit
    """

    path = Path(file_path)

    if not path.exists():
        raise DocumentValidationError(
            f"Document does not exist: {path}"
        )

    if not path.is_file():
        raise DocumentValidationError(
            f"Document path is not a file: {path}"
        )

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise DocumentValidationError(
            f"Unsupported document format: {extension}"
        )

    if content_type is not None:
        if content_type not in SUPPORTED_CONTENT_TYPES:
            raise DocumentValidationError(
                f"Unsupported content type: {content_type}"
            )

    file_size = path.stat().st_size

    if file_size == 0:
        raise DocumentValidationError(
            "Document cannot be empty."
        )

    if file_size > MAX_DOCUMENT_SIZE_BYTES:
        raise DocumentValidationError(
            "Document exceeds the maximum allowed size "
            "of 10 MB."
        )