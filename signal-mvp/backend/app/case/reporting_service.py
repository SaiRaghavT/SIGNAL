from uuid import UUID
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.ecr.builder import build_ecr
from backend.app.demo.synthetic_jordan_reporting import apply_synthetic_jordan_reporting_defaults
from backend.app.models.case import Case
from backend.app.models.workflow_records import CaseWorkflowRecord, Report
from backend.app.schemas.validation import validate_ecr
from backend.app.smart_field_population.form_config import (
    REPORTING_MISSING_INFO_FIELDS,
    TEXAS_MEASLES_FORM,
)

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
    # Patient identity fields entered on the reporting form are part of the
    # persisted Case as well as the rendered report. Keep the ECR patient
    # object in sync so validation sees a submitted date of birth, for example.
    patient_field_map = {
        "patient.current_address": "address",
        "patient.city": "city",
        "patient.county": "county",
        "patient.zip": "zip",
        "patient.phone": "phone",
        "patient.date_of_birth": "date_of_birth",
        "patient.sex": "sex",
        "patient.country_of_residence": "country_of_residence",
        "patient.hispanic": "hispanic",
        "patient.race": "race",
    }
    patient_updates = {
        patient_field_map[field]: value
        for field, value in report_updates.items()
        if field in patient_field_map
    }
    if patient_updates:
        case.patient = {**(case.patient or {}), **patient_updates}
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

    is_optional_missing_info_reset = (
        bool(report_updates)
        and set(report_updates).issubset(REPORTING_MISSING_INFO_FIELDS)
        and all(is_missing(value) for value in report_updates.values())
        and not provider_updates
        and not facility_updates
        and request.provider is None
        and request.facility is None
    )
    synthetic_changes = (
        [] if is_optional_missing_info_reset
        else apply_synthetic_jordan_reporting_defaults(case)
    )
    changed_fields.extend(synthetic_changes)
    # An explicit empty value is a user request to clear that field. Keep it
    # cleared even for synthetic demo cases that otherwise receive defaults.
    for field, value in report_updates.items():
        if is_missing(value):
            case.report_fields[field] = value

    # The five missing-information values are optional form fields. Clearing
    # only these values on a fresh form visit should not revoke clinical
    # approval or attestation for the otherwise unchanged case.
    clearing_optional_missing_info = is_optional_missing_info_reset and not synthetic_changes

    if changed_fields:
        if not clearing_optional_missing_info:
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
    if case.final_decision != "HOLD" and not clearing_optional_missing_info:
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
