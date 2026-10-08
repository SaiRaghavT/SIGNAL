from io import BytesIO
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from backend.app.forms.mappings.texas_measles import (
    PDF_CHECKBOX_MAP,
    PDF_FIELD_MAP,
    PDF_MULTI_CHECKBOX_MAP,
)
from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM
from .schemas import FormRenderingRequest, FormRenderingResponse, RenderedField


PROJECT_ROOT = Path(__file__).resolve().parents[4]
TEMPLATE_PATH = PROJECT_ROOT / "backend" / "app" / "forms" / "templates" / "TX_MEASLES_OUTBREAK_CRF_2025.pdf"
OUTPUT_DIR = PROJECT_ROOT / "backend" / "app" / "forms" / "generated"
RENDERED_FILE_SUFFIX = "_TX_MEASLES.pdf"
_RENDER_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def get_rendered_pdf_path(render_id: str) -> Path | None:
    """Resolve an opaque render ID only to its generated PDF, if present."""
    if not _RENDER_ID_PATTERN.fullmatch(render_id):
        return None
    try:
        output_root = OUTPUT_DIR.resolve()
        pdf_path = (output_root / f"{render_id}{RENDERED_FILE_SUFFIX}").resolve()
        pdf_path.relative_to(output_root)
    except (OSError, ValueError):
        return None
    return pdf_path if pdf_path.is_file() else None


def _object(value: Any) -> Any:
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
    return {str(state).lstrip("/") for state in normal.keys() if str(state) != "/Off"}


def _report_value(report_data: dict[str, Any], path: str) -> Any:
    """Resolve configured dotted paths from flat data or persisted objects."""
    if path in report_data:
        return report_data[path]
    parts = path.split(".")
    value: Any = report_data
    for part in parts:
        if not isinstance(value, dict) or part not in value:
            value = None
            break
        value = value[part]
    if value is not None:
        return value
    root_alias = {
        "clinical": "clinical_evidence",
        "rash_fever": "clinical_evidence",
        "laboratory": "laboratory_evidence",
    }.get(parts[0], parts[0])
    value = report_data.get(root_alias)
    for part in parts[1:]:
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    if value is None and parts[0] in {"patient", "case", "reporting"}:
        value = report_data.get(parts[-1])
    if value is None and parts[0] == "patient" and len(parts) == 2:
        patient = report_data.get("patient") or {}
        permanent_address = patient.get("permanent_address") if isinstance(patient, dict) else None
        permanent_address = permanent_address if isinstance(permanent_address, dict) else {}
        permanent_keys = {
            "permanent_address": ("line", "address_line", "street"),
            "permanent_city": ("city",),
            "permanent_county": ("county",),
            "permanent_zip": ("postal_code", "zip", "zip_code"),
        }
        for key in permanent_keys.get(parts[1], ()):
            if permanent_address.get(key) not in (None, ""):
                value = permanent_address[key]
                break
    return value


def _normal(value: Any) -> str:
    return str(value).strip().casefold()


def _display_value(value: Any) -> Any:
    """Extract printable data from common backend value/address objects."""
    if isinstance(value, dict):
        for key in ("value", "display", "text", "line", "address_line", "street"):
            if value.get(key) not in (None, ""):
                value = value[key]
                break
        else:
            return None
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value if item not in (None, ""))
    return value


class FormRenderingService:
    def render_form(
        self,
        request: FormRenderingRequest,
        report_data: dict[str, Any],
        *,
        demo_fill: bool = False,
        required_missing_fields: list[str] | None = None,
    ) -> FormRenderingResponse:
        if not TEMPLATE_PATH.exists():
            raise ValueError(f"Template not found: {TEMPLATE_PATH}")
        reader = PdfReader(str(TEMPLATE_PATH))
        if not reader.pages:
            raise ValueError("PDF template contains no pages.")

        # Resolve case data through backend-maintained mappings. No values are
        # synthesized here; an absent source value remains blank in the form.
        values: dict[str, Any] = {}
        request_value_fields: set[str] = set()
        for source, target in PDF_FIELD_MAP.items():
            value = _display_value(_report_value(report_data, source))
            if value is not None and str(value) != "":
                values[target] = value
                request_value_fields.add(target)

        checkbox_values: dict[str, Any] = {}
        for source, definition in PDF_CHECKBOX_MAP.items():
            value = _report_value(report_data, source)
            if value is None or str(value).strip() == "":
                continue
            selected = definition["values"].get(_normal(value))
            if selected:
                checkbox_values[definition["pdf_field"]] = selected
                request_value_fields.add(definition["pdf_field"])
        for source, choices in PDF_MULTI_CHECKBOX_MAP.items():
            value = _report_value(report_data, source)
            if value is None or str(value).strip() == "":
                continue
            if isinstance(value, (list, tuple, set)):
                selections = value
            elif isinstance(value, str) and ("," in value or ";" in value):
                selections = re.split(r"[,;]", value)
            else:
                selections = [value]
            for selection in selections:
                target = choices.get(_normal(selection))
                if target:
                    checkbox_values[target] = "1"
                    request_value_fields.add(target)
        # Also accept exact PDF widget names for existing API integrations.
        for name, value in report_data.items():
            if isinstance(name, str) and value is not None:
                values.setdefault(name, value)
                checkbox_values.setdefault(name, value)

        demo_blank_widgets: set[str] = set()
        if demo_fill:
            # A demo case without an outcome is treated as a recovered case.
            # Never show death details alongside a Survived selection.
            if not checkbox_values.get("OUTCOME"):
                checkbox_values["OUTCOME"] = "Survived"
            if _normal(checkbox_values["OUTCOME"]) == "survived":
                values.pop("DEATH_DATE", None)
                values.pop("DEATH_CAUSE", None)
                demo_blank_widgets.update({"DEATH_DATE", "DEATH_CAUSE"})

            missing_fields_set = set(required_missing_fields or [])
            for definition in TEXAS_MEASLES_FORM["fields"]:
                if definition["field"] not in missing_fields_set:
                    continue
                source = definition.get("source", definition["field"])
                if source in PDF_FIELD_MAP:
                    demo_blank_widgets.add(PDF_FIELD_MAP[source])
                checkbox = PDF_CHECKBOX_MAP.get(source)
                if checkbox:
                    demo_blank_widgets.add(checkbox["pdf_field"])
                demo_blank_widgets.update(PDF_MULTI_CHECKBOX_MAP.get(source, {}).values())

        def demo_text_value(name: str) -> str:
            normalized = name.casefold()
            case_suffix = re.sub(r"[^A-F0-9]", "", request.case_id.upper())[:8]
            if normalized == "nbs patient id":
                return f"DEMO-PAT-{case_suffix}"
            if normalized == "nbs investigation id":
                return f"DEMO-INV-{case_suffix}"
            if "epi linked nbs case id" in normalized:
                return "Not applicable"
            if "first name" in normalized:
                return "Taylor"
            if "last name" in normalized:
                return "Reed"
            if "parent or guardian" in normalized:
                return "Jordan Reed"
            if "email" in normalized:
                return "jordan.reed@example.com"
            if "phone" in normalized:
                return "512-555-0142"
            if "address" in normalized or "street" in normalized:
                return "100 Congress Avenue"
            if "city" in normalized:
                return "Austin"
            if "county" in normalized:
                return "Travis"
            if "zip" in normalized or "postal" in normalized:
                return "78701"
            if "country" in normalized:
                return "United States"
            if "hospital" in normalized or "facility" in normalized:
                return "Central Texas Medical Center"
            if "physician" in normalized or "provider" in normalized or "doctor" in normalized:
                return "Dr. Maya Patel"
            if "agency" in normalized or "investigated by" in normalized or "reported by" in normalized:
                return "Austin Public Health"
            if "diagnosis" in normalized:
                return "Measles"
            if "pcr" in normalized or "igm" in normalized:
                return "Positive"
            if "igg" in normalized or "culture" in normalized:
                return "Negative"
            if "temperature" in normalized or "temp" in normalized:
                return "101.2"
            if "duration" in normalized or "age" in normalized or "length of time" in normalized:
                return "3"
            if "time" in normalized:
                return "10:00 AM"
            if "date" in normalized or normalized.endswith("_af_date"):
                if "rash" in normalized or "fever" in normalized or "onset" in normalized:
                    return "2026-09-29"
                if "discharge" in normalized or "completed" in normalized:
                    return "2026-10-04"
                if "admit" in normalized or "start" in normalized:
                    return "2026-10-01"
                return "2026-10-02"
            if "name" in normalized or "contact" in normalized:
                return "Case Contact"
            if "occupation" in normalized:
                return "Teacher"
            if "location" in normalized or "address" in normalized:
                return "Austin, TX"
            if "other" in normalized or "notes" in normalized or "specify" in normalized:
                return "Not applicable"
            return "Not applicable"

        rendered_fields: list[RenderedField] = []
        populated_fields: list[str] = []
        missing_fields: list[str] = []
        warnings: list[str] = []

        # Overlay every page independently and merge it into the original
        # source page. This retains the complete multi-page Texas form.
        for page in reader.pages:
            annotations = _object(page.get("/Annots")) or []
            page_fields: dict[str, list[dict[str, Any]]] = {}
            for annotation in annotations:
                widget = _object(annotation)
                name = _field_name(widget)
                rect = widget.get("/Rect")
                if not name or not rect:
                    continue
                page_fields.setdefault(name, []).append({
                    "rect": [float(value) for value in rect],
                    "type": _field_type(widget),
                    "on_states": _on_states(widget),
                })

            if demo_fill:
                for name, widgets in page_fields.items():
                    text_widgets = [widget for widget in widgets if widget["type"] == "/Tx"]
                    if text_widgets and name not in values and name not in demo_blank_widgets:
                        values[name] = demo_text_value(name)
                    button_widgets = [widget for widget in widgets if widget["type"] == "/Btn"]
                    if (button_widgets and name not in checkbox_values and name not in demo_blank_widgets
                            and name.casefold() != "clear form" and not name.startswith("RACE_")):
                        first_choice = next(
                            (state for widget in button_widgets for state in widget["on_states"]),
                            None,
                        )
                        if first_choice:
                            checkbox_values[name] = first_choice

            buffer = BytesIO()
            overlay = canvas.Canvas(buffer, pagesize=(float(page.mediabox.width), float(page.mediabox.height)))
            for name, widgets in page_fields.items():
                text_widgets = [widget for widget in widgets if widget["type"] == "/Tx"]
                if text_widgets:
                    value = values.get(name)
                    if value is None or str(value) == "":
                        if name not in missing_fields:
                            missing_fields.append(name)
                        continue
                    value_text = str(value)
                    for widget in text_widgets:
                        x1, y1, x2, y2 = widget["rect"]
                        width = max(x2 - x1 - 4, 1)
                        size = 8.0
                        while overlay.stringWidth(value_text, "Helvetica", size) > width and size > 4.0:
                            size -= 0.5
                        if overlay.stringWidth(value_text, "Helvetica", size) > width:
                            warnings.append(f"Text may not fit completely in PDF field: {name}")
                        overlay.setFont("Helvetica", size)
                        overlay.drawString(x1 + 2, y1 + ((y2 - y1) - size) / 2 + 1, value_text)
                    if name not in populated_fields:
                        populated_fields.append(name)
                        rendered_fields.append(RenderedField(
                            field=name, value=value_text,
                            source="persisted_case" if name in request_value_fields else None,
                            confidence=1.0, status="POPULATED",
                        ))

                button_widgets = [widget for widget in widgets if widget["type"] == "/Btn"]
                if button_widgets and name.casefold() != "clear form":
                    selection = checkbox_values.get(name)
                    selected_widget = next((widget for widget in button_widgets
                        if selection is not None and _normal(selection) in {_normal(state) for state in widget["on_states"]}), None)
                    if selection is not None and selected_widget is None:
                        warnings.append(f"Checkbox selection '{selection}' does not match a PDF option for: {name}")
                    if selected_widget:
                        x1, y1, x2, y2 = selected_widget["rect"]
                        width, height = x2 - x1, y2 - y1
                        overlay.setStrokeColorRGB(0, 0, 0)
                        overlay.setLineWidth(max(min(width, height) * 0.12, 0.65))
                        overlay.setLineCap(1)
                        overlay.line(x1 + width * 0.18, y1 + height * 0.48, x1 + width * 0.42, y1 + height * 0.22)
                        overlay.line(x1 + width * 0.40, y1 + height * 0.22, x1 + width * 0.83, y1 + height * 0.80)
                        if name not in populated_fields:
                            populated_fields.append(name)
                            rendered_fields.append(RenderedField(
                                field=name, value=selection,
                                source="persisted_case" if name in request_value_fields else None,
                                confidence=1.0, status="POPULATED",
                            ))
            overlay.save()
            buffer.seek(0)
            page.merge_page(PdfReader(buffer).pages[0])

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        render_id = uuid4().hex
        output_path = OUTPUT_DIR / f"{render_id}{RENDERED_FILE_SUFFIX}"
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        with output_path.open("wb") as output_file:
            writer.write(output_file)

        return FormRenderingResponse(
            case_id=request.case_id,
            form_id=request.form_id,
            render_id=render_id,
            form_version=request.form_version,
            status="RENDERED",
            fields=rendered_fields,
            populated_fields=populated_fields,
            missing_fields=missing_fields,
            warnings=warnings,
            rendered_document=str(output_path),
        )
