from pathlib import Path

from backend.app.agents.document_intelligence.agent import ocr_scanned_pdf_page


class DocumentExtractionError(ValueError):
    """Raised when document text or OCR extraction fails."""


def extract_text_from_file(
    file_path: str | Path,
    content_type: str | None = None,
) -> str:
    """
    Extract text from a supported clinical document.

    Supported formats:
        - PDF
        - DOCX
        - TXT

    Text-based formats are extracted locally. Scanned PDF page images are
    OCRed locally with Tesseract.
    """

    path = Path(file_path)

    if not path.exists():
        raise DocumentExtractionError(
            f"Document does not exist: {path}"
        )

    if not path.is_file():
        raise DocumentExtractionError(
            f"Document path is not a file: {path}"
        )

    extension = path.suffix.lower()

    if extension == ".pdf":
        return _extract_pdf(path)

    if extension == ".docx":
        return _extract_docx(path)

    if extension == ".txt":
        return _extract_txt(path)

    raise DocumentExtractionError(
        f"Unsupported document format: {extension}"
    )


def _extract_pdf(path: Path) -> str:
    """Extract embedded text, then OCR scanned page images locally."""

    try:
        from pypdf import PdfReader

        reader = PdfReader(str(path))

        pages: list[str] = []

        for page in reader.pages:
            text = page.extract_text()
            if not text or not text.strip():
                try:
                    text = ocr_scanned_pdf_page(page)
                except ValueError as exc:
                    raise DocumentExtractionError(str(exc)) from exc
            if text and text.strip():
                pages.append(text.strip())

    except DocumentExtractionError:
        raise
    except Exception as exc:
        raise DocumentExtractionError(
            f"Failed to extract PDF text: {path.name}"
        ) from exc

    return "\n".join(pages).strip()


def _extract_docx(path: Path) -> str:
    """Extract paragraph text from a DOCX document."""

    try:
        from docx import Document

        document = Document(str(path))

        paragraphs = [
            paragraph.text.strip()
            for paragraph in document.paragraphs
            if paragraph.text.strip()
        ]

        return "\n".join(paragraphs)

    except Exception as exc:
        raise DocumentExtractionError(
            f"Failed to extract DOCX text: {path.name}"
        ) from exc


def _extract_txt(path: Path) -> str:
    """Extract text from a plain-text document."""

    try:
        return path.read_text(
            encoding="utf-8"
        ).strip()

    except UnicodeDecodeError:
        try:
            return path.read_text(
                encoding="latin-1"
            ).strip()

        except Exception as exc:
            raise DocumentExtractionError(
                f"Failed to decode text document: {path.name}"
            ) from exc

    except Exception as exc:
        raise DocumentExtractionError(
            f"Failed to read text document: {path.name}"
        ) from exc
