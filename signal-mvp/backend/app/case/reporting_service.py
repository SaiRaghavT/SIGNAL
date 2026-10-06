from uuid import UUID
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.ecr.builder import build_ecr
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.schemas.validation import validate_ecr
from backend.app.smart_field_population.form_config import TEXAS_MEASLES_FORM

from .report_fields import is_missing, missing_report_fields
from .schemas import CaseReportUpdateRequest, CaseReportUpdateResponse


def update_case_report(
    db: Session,
    case_id: UUID,
    request: CaseReportUpdateRequest,
) -> CaseReportUpdateResponse:
    case = db.query(Case).filter(Case.case_id == case_id).first()
    if case is None:
        raise ValueError(f"Case not found: {case_id}")

    allowed_fields = {item["field"] for item in TEXAS_MEASLES_FORM["fields"]}
    allowed_fields.update({"provider.name", "provider.phone", "provider.address", "facility.name"})
    unknown_fields = sorted(set(request.report_fields) - allowed_fields)
    if unknown_fields:
        raise ValueError(f"Unknown report fields: {', '.join(unknown_fields)}")

    changed_fields = sorted(request.report_fields)
    report_updates = {key: value for key, value in request.report_fields.items() if not key.startswith(("provider.", "facility."))}
    case.report_fields = {**(case.report_fields or {}), **report_updates}
    provider_updates = {key.removeprefix("provider."): value for key, value in request.report_fields.items() if key.startswith("provider.")}
    facility_updates = {key.removeprefix("facility."): value for key, value in request.report_fields.items() if key.startswith("facility.")}
    if provider_updates:
        case.provider = {**(case.provider or {}), **provider_updates}
    if facility_updates:
        case.facility = {**(case.facility or {}), **facility_updates}
    if request.provider is not None:
        case.provider = {**(case.provider or {}), **request.provider}
        changed_fields.extend(f"provider.{key}" for key in request.provider)
        if case.provider.get("name"):
            case.provider["status"] = "HUMAN_COMPLETED"
            case.provider["missing_fields"] = [
                key for key in ("phone", "address") if is_missing(case.provider.get(key))
            ]
    if request.facility is not None:
        case.facility = {**(case.facility or {}), **request.facility}
        changed_fields.extend(f"facility.{key}" for key in request.facility)

    if changed_fields:
        current_records = db.query(CaseWorkflowRecord).filter(
            CaseWorkflowRecord.case_id == str(case.case_id),
            CaseWorkflowRecord.record_type.in_(("VALIDATION", "REVIEW", "ATTESTATION")),
            CaseWorkflowRecord.status.notin_(("SUPERSEDED",)),
        ).all()
        for record in current_records:
            record.status = "SUPERSEDED"
        for report in db.query(Report).filter(
            Report.case_id == str(case.case_id), Report.status == "GENERATED"
        ).all():
            report.status = "SUPERSEDED"

    missing, required_missing = missing_report_fields(case.report_fields)
    if case.final_decision != "HOLD":
        case.status = "NEEDS_REVIEW"
    db.commit()
    db.refresh(case)

    ecr = build_ecr(case)
    smart_fields = SimpleNamespace(
        fields=case.report_fields,
        missing_fields=missing,
        required_missing_fields=required_missing,
    )
    validation = validate_ecr(ecr, smart_fields)
    AuditLedgerService().record_event(
        AuditEventCreate(
            entity_type="CASE",
            entity_id=str(case.case_id),
            event_type="CASE_REPORT_FIELDS_UPDATED",
            actor_type="USER",
            actor_id=request.reviewer_id.strip() or "reporting_user",
            source_agent="Manual Review",
            status="SUCCESS",
            description="Reporting fields updated for human completion.",
            new_value={"changed_fields": changed_fields},
            metadata={
                "missing_report_fields": missing,
                "required_missing_fields": required_missing,
            },
        ),
        db,
    )
    return CaseReportUpdateResponse(
        case_id=str(case.case_id),
        report_fields=case.report_fields,
        provider=case.provider or {},
        facility=case.facility or {},
        missing_report_fields=missing,
        required_missing_fields=required_missing,
        validation={
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
            "completion_required": validation.completion_required,
        },
    )
