from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .schemas import (
    FormDefinitionResponse,
    FormRenderingRequest,
    FormRenderingResponse,
)
from .service import FormRenderingService, get_rendered_pdf_path
from backend.app.smart_field_population.form_config import (
    REPORTING_MISSING_INFO_FIELDS,
    TEXAS_MEASLES_FORM,
)
from backend.app.database import get_db
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.config.demo import is_demo_case
from backend.app.detection.disease_concepts import canonical_disease_id
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.ingestion.api.fhir import get_seed_candidate_summary


router = APIRouter(
    prefix="/api/agents/form-rendering",
    tags=["Form Rendering"],
)
public_router = APIRouter(tags=["Reporting"])

service = FormRenderingService()


@public_router.post(
    "/api/forms/seed-patients/{patient_id}/render",
    response_model=FormRenderingResponse,
)
def render_seed_patient_form(
    patient_id: UUID,
    request: FormRenderingRequest,
) -> FormRenderingResponse:
    if get_seed_candidate_summary(str(patient_id)) is None:
        raise HTTPException(status_code=404, detail="FHIR seed patient not found.")
    if request.case_id != str(patient_id):
        raise HTTPException(status_code=422, detail="The path and body patient IDs must match.")
    if request.form_id != TEXAS_MEASLES_FORM["form_id"]:
        raise HTTPException(status_code=422, detail=f"Unsupported form: {request.form_id}")

    try:
        result = service.render_form(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not result.render_id:
        raise HTTPException(status_code=500, detail="Form rendering did not return a render identifier.")
    result.retrieval_url = f"{router.prefix}/{result.render_id}"
    result.rendered_document = result.retrieval_url
    return result


@router.get("/forms/{form_id}", response_model=FormDefinitionResponse)
def get_form_definition(form_id: str) -> FormDefinitionResponse:
    if form_id != TEXAS_MEASLES_FORM["form_id"]:
        raise HTTPException(status_code=404, detail=f"Reporting form not found: {form_id}")
    return FormDefinitionResponse(**TEXAS_MEASLES_FORM)


@router.post(
    "/render",
    response_model=FormRenderingResponse,
)
def render_form(
    request: FormRenderingRequest,
    db: Session = Depends(get_db),
) -> FormRenderingResponse:

    try:
        try:
            case_uuid = UUID(request.case_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="case_id must be a persisted case UUID.") from exc
        case = db.query(Case).filter(Case.case_id == case_uuid).first()
        if case is None:
            raise HTTPException(status_code=404, detail=f"Case not found: {request.case_id}")
        case_disease = " ".join((case.disease or "").casefold().replace("(disorder)", "").split())
        form_disease = TEXAS_MEASLES_FORM["disease"].casefold()
        case_jurisdiction = (case.jurisdiction or "").strip().casefold()
        form_jurisdiction = TEXAS_MEASLES_FORM["jurisdiction"].casefold()
        if (
            case_jurisdiction not in {form_jurisdiction, "texas"}
            or canonical_disease_id(case_disease) != canonical_disease_id(form_disease)
        ):
            raise HTTPException(status_code=422, detail="No Texas measles form is configured for this case.")
        if request.form_id != TEXAS_MEASLES_FORM["form_id"]:
            raise HTTPException(status_code=422, detail=f"Unsupported form: {request.form_id}")
        if request.form_version not in (None, TEXAS_MEASLES_FORM["form_version"]):
            raise HTTPException(status_code=422, detail=f"Unsupported form version: {request.form_version}")
        validation = (
            db.query(CaseWorkflowRecord)
            .filter(CaseWorkflowRecord.case_id == str(case.case_id), CaseWorkflowRecord.record_type == "VALIDATION")
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )
        attestation = (
            db.query(CaseWorkflowRecord)
            .filter(CaseWorkflowRecord.case_id == str(case.case_id), CaseWorkflowRecord.record_type == "ATTESTATION")
            .order_by(CaseWorkflowRecord.created_at.desc())
            .first()
        )
        # Use the same persisted record shown in Case Workspace as the source
        # for PDF population. Keep explicit report-field edits highest priority
        # and never replace them with absent values from the patient record.
        patient = case.patient if isinstance(case.patient, dict) else {}
        provider = case.provider if isinstance(case.provider, dict) else {}
        facility = case.facility if isinstance(case.facility, dict) else {}
        clinical = case.clinical_evidence if isinstance(case.clinical_evidence, dict) else {}
        laboratory = case.laboratory_evidence if isinstance(case.laboratory_evidence, dict) else {}
        address = patient.get("address")
        address_fields = address if isinstance(address, dict) else {}
        report_data = {
            "patient": patient,
            "provider": provider,
            "facility": facility,
            "clinical_evidence": clinical,
            "laboratory_evidence": laboratory,
            "clinical": clinical,
            "rash_fever": clinical,
            "laboratory": laboratory,
        }
        report_data.update(case.report_fields or {})
        derived_values = {
            "patient.first_name": patient.get("first_name"),
            "patient.last_name": patient.get("last_name"),
            "patient.date_of_birth": patient.get("date_of_birth"),
            "patient.address": (
                address_fields.get("line")
                or (address if isinstance(address, str) else None)
                or patient.get("address_line")
            ),
            "patient.city": address_fields.get("city") or patient.get("city"),
            "patient.county": address_fields.get("county") or patient.get("county"),
            "patient.zip": address_fields.get("postal_code") or patient.get("postal_code") or patient.get("zip"),
            "provider.name": provider.get("name"),
            "provider.phone": provider.get("phone"),
            "provider.address": provider.get("address"),
            "facility.name": facility.get("name"),
            "clinical.diagnosis": case.disease,
        }
        # Fill only absent values so missing backend fields cannot shadow real
        # saved report fields with the same dotted key.
        for key, value in derived_values.items():
            if value not in (None, ""):
                report_data.setdefault(key, value)
        required_missing_fields = list(REPORTING_MISSING_INFO_FIELDS)
        demo_case = is_demo_case(case)
        # Persisted report fields are authoritative. Explicit request values
        # remain supported for callers that intentionally request a preview.
        transient_fields = {
            field: value for field, value in request.field_values.items()
            if field in REPORTING_MISSING_INFO_FIELDS and str(value or "").strip()
        }
        report_data.update(transient_fields)
        required_missing_fields = [
            field for field in REPORTING_MISSING_INFO_FIELDS
            if not report_data.get(field)
        ]
        result = service.render_form(
            request,
            report_data,
            demo_fill=True,
            required_missing_fields=required_missing_fields,
        )
        result.missing_required_fields = required_missing_fields
        transient_preview = bool(request.field_values)
        result.demo_mode = demo_case or transient_preview
        if not result.render_id:
            raise HTTPException(
                status_code=500,
                detail="Form rendering did not return a render identifier.",
            )
        retrieval_url = f"{router.prefix}/{result.render_id}"
        result.retrieval_url = retrieval_url
        result.rendered_document = retrieval_url
        if not demo_case and not transient_preview:
            report = Report(
                case_id=str(case.case_id),
                form_id=result.form_id,
                form_version=result.form_version,
                render_id=result.render_id,
                disease=case.disease,
                jurisdiction=case.jurisdiction,
                validation=validation.payload if validation else {},
                attestation=attestation.payload if attestation else {},
                status="GENERATED",
            )
            db.add(report)
            db.commit()
            db.refresh(report)
            result.report_id = report.report_id
            AuditLedgerService().record_event(
                AuditEventCreate(
                    entity_type="CASE",
                    entity_id=str(case.case_id),
                    event_type="FORM_RENDERED",
                    actor_type="SYSTEM",
                    actor_id="SIGNAL",
                    source_agent="form_rendering",
                    status="SUCCESS",
                    new_value={"render_id": result.render_id, "report_id": report.report_id},
                    workflow_stage="REPORTING",
                ),
                db,
            )
        return result

    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


@router.get(
    "/{render_id}",
    response_class=FileResponse,
    name="retrieve_rendered_form",
)
def retrieve_rendered_form(render_id: str) -> FileResponse:
    pdf_path = get_rendered_pdf_path(render_id)
    if pdf_path is None:
        raise HTTPException(
            status_code=404,
            detail="Rendered form not found.",
        )
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"signal-form-{render_id}.pdf",
        content_disposition_type="inline",
    )


@public_router.get("/api/forms/{render_id}", name="view_rendered_form")
def view_rendered_form(render_id: str) -> FileResponse:
    return retrieve_rendered_form(render_id)


@public_router.get("/api/forms/{render_id}/download", name="download_rendered_form")
def download_rendered_form(render_id: str) -> FileResponse:
    pdf_path = get_rendered_pdf_path(render_id)
    if pdf_path is None:
        raise HTTPException(status_code=404, detail="Rendered form not found.")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=f"signal-form-{render_id}.pdf",
        content_disposition_type="attachment",
    )


@public_router.post("/api/cases/{case_id}/report", response_model=FormRenderingResponse)
def create_case_report(
    case_id: UUID,
    request: FormRenderingRequest,
    db: Session = Depends(get_db),
) -> FormRenderingResponse:
    if str(case_id) != request.case_id:
        raise HTTPException(status_code=422, detail="The path and body case IDs must match.")
    return render_form(request, db)


@public_router.get("/api/cases/{case_id}/report")
def get_case_report(case_id: UUID, db: Session = Depends(get_db)) -> dict:
    report = db.query(Report).filter(Report.case_id == str(case_id)).order_by(Report.created_at.desc()).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return _report_response(report)


@public_router.get("/api/reports/{report_id}")
def get_report(report_id: UUID, db: Session = Depends(get_db)) -> dict:
    report = db.query(Report).filter(Report.report_id == str(report_id)).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return _report_response(report)


def _report_response(report: Report) -> dict:
    return {
        "report_id": report.report_id,
        "case_id": report.case_id,
        "form_id": report.form_id,
        "form_version": report.form_version,
        "render_id": report.render_id,
        "report_type": report.report_type,
        "disease": report.disease,
        "jurisdiction": report.jurisdiction,
        "validation": report.validation,
        "attestation": report.attestation,
        "status": report.status,
        "created_at": report.created_at,
    }
