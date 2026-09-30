from io import BytesIO
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from backend.app.forms.mappings.texas_measles import PDF_FIELD_MAP

from .schemas import (
    FormRenderingRequest,
    FormRenderingResponse,
    RenderedField,
)


PROJECT_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_PATH = (
    PROJECT_ROOT
    / "backend"
    / "app"
    / "forms"
    / "templates"
    / "TX_MEASLES_OUTBREAK_CRF_2025.pdf"
)
OUTPUT_DIR = (
    PROJECT_ROOT
    / "backend"
    / "app"
    / "forms"
    / "generated"
)


# Demo values cover every text field on page one of the current Texas
# measles CRF. These are test values, not real patient/reporting data.
DEMO_DATA: dict[str, Any] = {
    "DEATH_CAUSE": "N/A",
    "DEATH_DATE": "N/A",
    "NBS Patient ID": "NEDSS-DEMO-001",
    "NBS Investigation ID": "NEDSS-INV-DEMO-001",
    "Last Name": "Doe",
    "First Name": "John",
    "Patient Current Street Address": "123 Main Street",
    "Patient Current City": "Austin",
    "Patient Current County": "Travis",
    "Patient Current Zip Code": "78701",
    "Region": "7",
    "Patient Home Phone": "512-555-0100",
    "Patient Cell Phone": "512-555-0101",
    "Physician": "Dr. Sarah Smith",
    "Physician Phone": "512-555-0200",
    "Physician Address": "500 Medical Center Drive, Austin, TX",
    "Parent or Guardian": "N/A",
    "Patient Permanent Street Address": "123 Main Street",
    "Patient Permanent City": "Austin",
    "Patient Permanent County": "Travis",
    "Patient Permanent Zip Code": "78701",
    "Patient DOB_af_date": "01/15/1990",
    "Patient Age": "36",
    "ESTIMATED_CASE_DUE_DATE": "N/A",
    "Case delivery hospital": "N/A",
    "Occupation": "Software Engineer",
    "Other place of birth": "N/A",
    "Other country of residence": "N/A",
    "Other race": "N/A",
    "Reported by": "Jane Nurse",
    "Reporting Agency email": "jane.nurse@example.com",
    "Reporting Agency Phone": "512-555-0300",
    "Reporting Agency": "Demo Hospital",
    "Earliest date reported to county_af_date": "09/30/2026",
    "Investigated by": "John Investigator",
    "Investigating agency email": "investigator@example.com",
    "Investigating Agency Phone": "512-555-0400",
    "Investigating Agency": "Austin Public Health",
    "Investigation start date_af_date": "09/30/2026",
    "Investigation completed date_af_date": "10/01/2026",
    "Hospital": "Demo General Hospital",
    "Hospital unit": "Infectious Disease",
    "Illness onset date_af_date": "09/25/2026",
    "Diagnosis": "Measles",
    "Diagnosis date_af_date": "09/30/2026",
    "Hospital admit date_af_date": "09/28/2026",
    "Hospital discharge date_af_date": "09/30/2026",
    "Duration of stay": "2",
}


# Values are the on-state names embedded in the PDF's checkbox/radio widgets.
# None means intentionally leave that checkbox group unselected.
DEMO_CHECKBOX_SELECTIONS: dict[str, str | None] = {
    "CASE_STATUS": "Y",
    "OUTCOME": "Survived",
    "UPDATE_TO_EXISTING": "N",
    "MINOR": None,
    "IS_PERMANENT_ADDRESS": "1",
    "HOMELESSNESS": None,
    "INFANT": "N",
    "SEX": "M",
    "PREGNANT": "N/A",
    "Check Box10": None,
    "BIRTHPLACE": "USA",
    "COUNTRY_OF_RESIDENCE": "USA",
    "HISPANIC": "N",
    "RACE_WHITE": None,
    "RACE_BLACK": None,
    "RACE_ASIAN": None,
    "RACE_AI_AN": None,
    "RACE_HAWAIIAN_PAC_ISLAND": None,
    "RACE_UNKNOWN": "1",
    "RACE_OTHER": None,
    "INPT_ADMIT": "Yes",
    "ICU_ADMIT": "No",
    "STILL_INPT": None,
    "CONFIRMATION": "Lab Confirmed",
}


def _object(value: Any) -> Any:
    """Dereference a PDF indirect object when necessary."""
    return value.get_object() if hasattr(value, "get_object") else value


def _field_name(widget: Any) -> str | None:
    name = widget.get("/T")
    parent_ref = widget.get("/Parent")
    parent = _object(parent_ref) if parent_ref else None
    if not name and parent:
        name = parent.get("/T")
    return str(name) if name else None


def _field_type(widget: Any) -> Any:
    if widget.get("/FT"):
        return widget.get("/FT")
    parent_ref = widget.get("/Parent")
    parent = _object(parent_ref) if parent_ref else None
    return parent.get("/FT") if parent else None


def _on_states(widget: Any) -> set[str]:
    appearance = _object(widget.get("/AP"))
    if not appearance:
        return set()
    normal = _object(appearance.get("/N"))
    if not hasattr(normal, "keys"):
        return set()
    return {
        str(state).lstrip("/")
        for state in normal.keys()
        if str(state) != "/Off"
    }


def _selected_value(widget: Any) -> Any:
    parent_ref = widget.get("/Parent")
    parent = _object(parent_ref) if parent_ref else None
    return (parent or widget).get("/V")


class FormRenderingService:
    def render_form(
        self,
        request: FormRenderingRequest,
    ) -> FormRenderingResponse:
        if not TEMPLATE_PATH.exists():
            raise ValueError(f"Template not found: {TEMPLATE_PATH}")

        reader = PdfReader(str(TEMPLATE_PATH))
        if not reader.pages:
            raise ValueError("PDF template contains no pages.")

        page = reader.pages[0]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)

        annotations = _object(page.get("/Annots")) or []
        page_fields: dict[str, list[dict[str, Any]]] = {}
        for annotation in annotations:
            widget = _object(annotation)
            name = _field_name(widget)
            rect = widget.get("/Rect")
            if not name or not rect:
                continue
            page_fields.setdefault(name, []).append(
                {
                    "rect": [float(value) for value in rect],
                    "type": _field_type(widget),
                    "widget": widget,
                    "on_states": _on_states(widget),
                }
            )

        # Demo data is the default. The request may override values by PDF
        # field name or by the canonical keys in PDF_FIELD_MAP.
        values = DEMO_DATA.copy()
        request_value_fields: set[str] = set()
        for canonical_name, pdf_name in PDF_FIELD_MAP.items():
            if canonical_name in request.report_data:
                values[pdf_name] = request.report_data[canonical_name]
                request_value_fields.add(pdf_name)
        values.update(
            {
                name: value
                for name, value in request.report_data.items()
                if name in page_fields
            }
        )
        request_value_fields.update(
            name for name in request.report_data if name in page_fields
        )

        overlay_buffer = BytesIO()
        overlay = canvas.Canvas(
            overlay_buffer,
            pagesize=(page_width, page_height),
        )
        rendered_fields: list[RenderedField] = []
        populated_fields: list[str] = []
        missing_fields: list[str] = []
        warnings: list[str] = []

        # Fill every text field found among page one's PDF widgets.
        text_field_names = {
            name
            for name, widgets in page_fields.items()
            if any(widget["type"] == "/Tx" for widget in widgets)
        }
        for field_name in sorted(text_field_names):
            value = values.get(field_name)
            if value is None or str(value) == "":
                missing_fields.append(field_name)
                warnings.append(f"No value supplied for PDF field: {field_name}")
                continue

            text = str(value)
            widget = next(
                item for item in page_fields[field_name]
                if item["type"] == "/Tx"
            )
            x1, y1, x2, y2 = widget["rect"]
            available_width = max(x2 - x1 - 4, 1)
            font_size = 8.0
            while (
                overlay.stringWidth(text, "Helvetica", font_size)
                > available_width
                and font_size > 4.0
            ):
                font_size -= 0.5

            if overlay.stringWidth(text, "Helvetica", font_size) > available_width:
                warnings.append(
                    f"Text may not fit completely in PDF field: {field_name}"
                )

            overlay.setFont("Helvetica", font_size)
            y = y1 + ((y2 - y1) - font_size) / 2 + 1
            overlay.drawString(x1 + 2, y, text)
            populated_fields.append(field_name)
            rendered_fields.append(
                RenderedField(
                    field=field_name,
                    value=text,
                    source="request.report_data"
                    if field_name in request_value_fields
                    else "DEMO_DATA",
                    confidence=1.0,
                    status="POPULATED",
                )
            )

        # Mark selected checkbox/radio widgets at their actual positions.
        # The PDF's "CLEAR FORM" pushbutton is an action, not a data field.
        button_field_names = {
            name
            for name, widgets in page_fields.items()
            if any(widget["type"] == "/Btn" for widget in widgets)
            and name.casefold() != "clear form"
        }
        for field_name in sorted(button_field_names):
            selection = request.report_data.get(
                field_name,
                DEMO_CHECKBOX_SELECTIONS.get(field_name),
            )
            selected_widget = None
            if selection is not None:
                selected_widget = next(
                    (
                        item
                        for item in page_fields[field_name]
                        if item["type"] == "/Btn"
                        and str(selection).casefold()
                        in {state.casefold() for state in item["on_states"]}
                    ),
                    None,
                )
                if selected_widget is None:
                    warnings.append(
                        f"Checkbox selection '{selection}' does not match "
                        f"a PDF option for: {field_name}"
                    )

            if selected_widget:
                x1, y1, x2, y2 = selected_widget["rect"]
                width = x2 - x1
                height = y2 - y1
                overlay.setStrokeColorRGB(0, 0, 0)
                overlay.setLineWidth(max(min(width, height) * 0.12, 0.65))
                overlay.setLineCap(1)
                overlay.line(
                    x1 + width * 0.18,
                    y1 + height * 0.48,
                    x1 + width * 0.42,
                    y1 + height * 0.22,
                )
                overlay.line(
                    x1 + width * 0.40,
                    y1 + height * 0.22,
                    x1 + width * 0.83,
                    y1 + height * 0.80,
                )
                populated_fields.append(field_name)
                status = "POPULATED"
                value = selection
            else:
                status = "LEFT_BLANK"
                value = ""

            rendered_fields.append(
                RenderedField(
                    field=field_name,
                    value=value,
                    source="request.report_data"
                    if field_name in request.report_data
                    else "DEMO_DATA",
                    confidence=1.0,
                    status=status,
                )
            )

        overlay.save()
        overlay_buffer.seek(0)
        overlay_page = PdfReader(overlay_buffer).pages[0]
        page.merge_page(overlay_page)

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        safe_case_id = Path(request.case_id).name
        output_path = OUTPUT_DIR / f"{safe_case_id}_TX_MEASLES_PAGE1_AUTO.pdf"

        writer = PdfWriter()
        for pdf_page in reader.pages:
            writer.add_page(pdf_page)
        with output_path.open("wb") as output_file:
            writer.write(output_file)

        return FormRenderingResponse(
            case_id=request.case_id,
            form_id=request.form_id,
            form_version=request.form_version,
            status="RENDERED",
            fields=rendered_fields,
            populated_fields=populated_fields,
            missing_fields=missing_fields,
            warnings=warnings,
            rendered_document=str(output_path),
        )
