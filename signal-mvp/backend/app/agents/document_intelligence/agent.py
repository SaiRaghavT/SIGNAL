
from pathlib import Path
from typing import Any

from ...config.settings import settings


def ocr_scanned_pdf_page(page: Any) -> str:
    """OCR embedded scanned-page images locally with Tesseract."""
    try:
        import pytesseract
    except ImportError as exc:
        raise ValueError(
            "Python OCR dependencies are missing. Install project dependencies."
        ) from exc

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        images = list(page.images)
        if not images:
            raise ValueError(
                "This PDF page has no selectable text or extractable scan image."
            )

        page_text: list[str] = []

        for image_file in images:
            image = image_file.image.convert("RGB")
            text = pytesseract.image_to_string(image, lang="eng").strip()
            if text:
                page_text.append(text)

        if not page_text:
            raise ValueError("Tesseract did not recognize text on the scanned page.")

        return "\n".join(page_text)

    except Exception as exc:
        if isinstance(exc, pytesseract.TesseractNotFoundError):
            raise ValueError(
                "Tesseract OCR is not installed or not on PATH. "
                "Install Tesseract or configure TESSERACT_CMD."
            ) from exc

        if isinstance(exc, ValueError):
            raise

        raise ValueError("Local OCR failed for a scanned PDF page.") from exc


def _ocr_rendered_pdf_page(page: Any) -> str:
    """Render a PDF page and run Tesseract when the PDF has no text layer."""
    try:
        import pytesseract
    except ImportError as exc:
        raise ValueError(
            "Python OCR dependencies are missing. Install project dependencies."
        ) from exc

    if settings.tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    try:
        bitmap = page.render(scale=2)
        image = bitmap.to_pil().convert("RGB")
        return pytesseract.image_to_string(image, lang="eng").strip()

    except Exception as exc:
        if isinstance(exc, pytesseract.TesseractNotFoundError):
            raise ValueError(
                "Tesseract OCR is not installed or not on PATH. "
                "Install Tesseract or configure TESSERACT_CMD."
            ) from exc

        raise ValueError("Tesseract OCR failed for a PDF page.") from exc


def _extract_pdf_text_with_ocr(pdf_path: str) -> str:
    """
    Extract text from a PDF.

    Selectable text is preferred. If a page has no text layer, that page
    is rendered and sent through Tesseract OCR.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ValueError(
            "PDF OCR dependencies are missing. Install pypdfium2."
        ) from exc

    try:
        pdf = pdfium.PdfDocument(pdf_path)
        document_text: list[str] = []

        for page_index in range(len(pdf)):
            page = pdf[page_index]

            try:
                text_page = page.get_textpage()
                page_text = text_page.get_text_range().strip()
            except Exception:
                page_text = ""

            if page_text:
                document_text.append(page_text)
            else:
                ocr_text = _ocr_rendered_pdf_page(page)
                if ocr_text:
                    document_text.append(ocr_text)

        return "\n\n".join(document_text).strip()

    except Exception as exc:
        if isinstance(exc, ValueError):
            raise

        raise ValueError(
            f"Failed to extract/OCR PDF: {pdf_path}"
        ) from exc


def process_documents(
    documents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Process clinical documents for downstream NLP analysis.

    Existing extracted text is used first. If a PDF has no extracted text,
    the PDF is automatically processed page-by-page and scanned pages are
    OCR'd locally with Tesseract.

    Input:
        List of clinical documents from the canonical patient context.

    Output:
        List of documents prepared for the NLP evidence agent.
    """

    processed_documents = []

    for document in documents:
        text = (
            document.get("extracted_text")
            or document.get("text")
            or ""
        ).strip()

        # OCR fallback only when there is no existing text.
        if not text:
            content_location = document.get("content_location")
            document_type = str(
                document.get("document_type") or ""
            ).casefold()

            if isinstance(content_location, str) and content_location.strip():
                pdf_path = Path(content_location)

                if (
                    pdf_path.suffix.casefold() == ".pdf"
                    or "pdf" in document_type
                ):
                    if pdf_path.exists() and pdf_path.is_file():
                        text = _extract_pdf_text_with_ocr(
                            str(pdf_path)
                        )

        processed_documents.append(
            {
                "document_id": document.get("document_id"),
                "patient_id": document.get("patient_id"),
                "encounter_id": document.get("encounter_id"),
                "document_type": document.get("document_type"),
                "title": document.get("title"),
                "document_date": document.get("document_date"),
                "text": text,
            }
        )

    return processed_documents
