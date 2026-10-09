"""Complete controlled ADMIN-DEMO measles cases from backend demo fixtures."""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.case.report_fields import is_missing
from backend.app.models.patient import Patient
from backend.app.demo.synthetic_jordan_reporting import (
    CLINICAL_DEFAULTS,
    FACILITY_DEFAULTS,
    PATIENT_DEFAULTS,
    PROVIDER_DEFAULTS,
    REPORT_FIELD_DEFAULTS,
)


def _fill_missing(current: dict[str, Any] | None, defaults: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    values = dict(current or {})
    changed = False
    for key, value in defaults.items():
        if is_missing(values.get(key)):
            values[key] = value
            changed = True
    return values, changed


def _is_admin_demo_case(case: Any) -> bool:
    candidate_id = str(getattr(case, "candidate_id", "") or "").upper()
    facility = getattr(case, "facility", None)
    facility = facility if isinstance(facility, dict) else {}
    facility_name = str(facility.get("name") or "").casefold()
    return candidate_id.startswith("ADMIN-DEMO-") and "demo" in facility_name and "measles" in str(getattr(case, "disease", "") or "").casefold()


def canonical_patient_for_case(db: Session | None, case: Any) -> Patient | None:
    if db is None or not _is_admin_demo_case(case):
        return None
    patient = case.patient if isinstance(case.patient, dict) else {}
    try:
        patient_id = UUID(str(patient.get("patient_id")))
    except (TypeError, ValueError):
        return None
    return db.query(Patient).filter(Patient.patient_id == patient_id).first()


def apply_admin_demo_reporting_defaults(case: Any, canonical_patient: Any = None) -> list[str]:
    """Fill only controlled ADMIN-DEMO records from the checked-in backend fixture.

    Canonical patient demographics take precedence over demo defaults. Other
    missing form values come from the existing synthetic demo fixture and are
    explicitly labeled as demo data in the case warning.
    """
    if not _is_admin_demo_case(case):
        return []

    changed: list[str] = []
    patient = dict(case.patient or {})
    if canonical_patient is not None:
        canonical_values = {
            "date_of_birth": getattr(canonical_patient, "date_of_birth", None),
            "sex": getattr(canonical_patient, "sex", None),
            "address": getattr(canonical_patient, "address_line", None),
            "city": getattr(canonical_patient, "city", None),
            "county": getattr(canonical_patient, "county", None),
            "state": getattr(canonical_patient, "state", None),
            "postal_code": getattr(canonical_patient, "postal_code", None),
        }
        canonical_values = {
            key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in canonical_values.items()
            if not is_missing(value)
        }
        merged_patient = {**canonical_values, **patient}
        if merged_patient != patient:
            case.patient = merged_patient
            patient = merged_patient
            changed.append("patient.canonical_demographics")

    patient, patient_changed = _fill_missing(patient, PATIENT_DEFAULTS)
    if patient_changed:
        case.patient = patient
        changed.append("patient.demo_defaults")

    report_defaults = dict(REPORT_FIELD_DEFAULTS)
    patient_name = " ".join(
        str(patient.get(key) or "").strip()
        for key in ("first_name", "last_name")
        if str(patient.get(key) or "").strip()
    )
    if patient_name:
        report_defaults["patient.case_name"] = patient_name
    if is_missing(patient.get("date_of_birth")):
        patient["date_of_birth"] = report_defaults["patient.date_of_birth"]
        case.patient = patient
        changed.append("patient.demo_date_of_birth")
    for field, key in (
        ("patient.date_of_birth", "date_of_birth"),
        ("patient.sex", "sex"),
        ("patient.current_address", "address"),
        ("patient.city", "city"),
        ("patient.county", "county"),
        ("patient.zip", "postal_code"),
    ):
        if not is_missing(patient.get(key)):
            report_defaults[field] = patient[key]

    report_fields, fields_changed = _fill_missing(case.report_fields, report_defaults)
    if fields_changed:
        case.report_fields = report_fields
        changed.append("report_fields.demo_defaults")

    provider, provider_changed = _fill_missing(case.provider, PROVIDER_DEFAULTS)
    if provider_changed:
        provider["status"] = "HUMAN_COMPLETED"
        provider["missing_fields"] = []
        case.provider = provider
        changed.append("provider.demo_defaults")

    facility, facility_changed = _fill_missing(case.facility, FACILITY_DEFAULTS)
    if facility_changed:
        case.facility = facility
        changed.append("facility.demo_defaults")

    clinical, clinical_changed = _fill_missing(case.clinical_evidence, CLINICAL_DEFAULTS)
    if clinical_changed:
        case.clinical_evidence = clinical
        changed.append("clinical_evidence.demo_defaults")

    if changed:
        warnings = list(case.warnings or [])
        notice = "Synthetic demo defaults were used; this is not a real patient record."
        if notice not in warnings:
            warnings.append(notice)
        case.warnings = warnings
    return changed
