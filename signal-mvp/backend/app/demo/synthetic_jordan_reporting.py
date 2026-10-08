"""Demo-only reporting defaults taken from the checked-in synthetic Jordan fixture."""

from typing import Any

from backend.app.case.report_fields import is_missing


SYNTHETIC_JORDAN_PATIENT_ID = "bb06202b-79bc-58c9-a8d6-be96e0775fdb"
SYNTHETIC_JORDAN_SOURCE_ID = "SIGNAL-DEMO-MEASLES-001"
SYNTHETIC_JORDAN_FACILITY_ID = "SIGNAL-DEMO-CLINIC"

REPORT_FIELD_DEFAULTS = {
    "patient.case_name": "Jordan Rivera",
    "patient.parent_guardian_name": "Alex Rivera (synthetic)",
    "patient.current_address": "100 Demo Avenue",
    "patient.city": "Austin",
    "patient.county": "Travis",
    "patient.zip": "78701",
    "patient.phone": "512-555-0100",
    "patient.date_of_birth": "2018-04-12",
    "patient.sex": "Female",
    "patient.country_of_residence": "United States",
    "patient.hispanic": "Unknown",
    "patient.race": "Unknown",
    "reporting.reported_by": "Taylor Morgan, MD",
    "reporting.email": "demo@signal.local",
    "reporting.phone": "512-555-0199",
    "reporting.agency": "SIGNAL Demonstration Clinic",
    "reporting.earliest_date_reported": "2026-10-01",
    "clinical.hospitalized": "No",
    "clinical.icu_admission": "No",
    "clinical.admission_date": "Not applicable",
    "clinical.discharge_date": "Not applicable",
    "clinical.hospital": "SIGNAL Demonstration Clinic",
    "clinical.illness_onset_date": "2026-09-28",
    "clinical.confirmation_method": "Laboratory confirmed",
    "clinical.diagnosis": "Measles",
    "clinical.diagnosis_date": "2026-10-01",
    "rash_fever.rash": "Yes",
    "rash_fever.rash_onset_date": "2026-09-30",
    "rash_fever.rash_duration": "2 days",
    "rash_fever.rash_location": "Face and upper trunk",
    "rash_fever.fever": "Yes",
    "rash_fever.fever_onset_date": "2026-09-28",
    "rash_fever.highest_temperature": "39.4 C",
    "rash_fever.cough": "Yes",
    "rash_fever.coryza": "Yes",
    "rash_fever.conjunctivitis": "Yes",
    "rash_fever.koplik_spots": "Unknown",
    "laboratory.pcr": "Positive",
    "laboratory.culture": "Not performed",
    "laboratory.igm": "Not documented",
    "laboratory.igg": "Not documented",
}

PATIENT_DEFAULTS = {
    "country_of_residence": "United States",
    "hispanic": "Unknown",
    "race": "Unknown",
    "phone": "512-555-0100",
}

PROVIDER_DEFAULTS = {
    "name": "Taylor Morgan, MD",
    "phone": "512-555-0199",
    "address": "200 Sample Street, Austin, TX 78701",
}

FACILITY_DEFAULTS = {
    "name": "SIGNAL Demonstration Clinic",
    "address": "200 Sample Street, Austin, TX 78701",
}

CLINICAL_DEFAULTS = {
    "onset_date": "2026-09-28",
    "illness_onset_date": "2026-09-28",
    "rash_onset_date": "2026-09-30",
    "rash_duration": "2 days",
    "highest_temperature": "39.4 C",
    "diagnosis": "Measles",
    "diagnosis_date": "2026-10-01",
    "confirmation_method": "Laboratory confirmed",
    "hospitalized": "No",
    "icu_admission": "No",
    "admission_date": "Not applicable",
    "discharge_date": "Not applicable",
    "rash": "Yes",
    "rash_location": "Face and upper trunk",
    "fever": "Yes",
    "fever_onset_date": "2026-09-28",
    "cough": "Yes",
    "coryza": "Yes",
    "conjunctivitis": "Yes",
    "koplik_spots": "Unknown",
}


def is_synthetic_jordan_case(case: Any) -> bool:
    patient = case.patient if isinstance(case.patient, dict) else {}
    facility = case.facility if isinstance(case.facility, dict) else {}
    provenance = patient.get("provenance") if isinstance(patient.get("provenance"), dict) else {}
    return (
        str(patient.get("patient_id") or "").lower() == SYNTHETIC_JORDAN_PATIENT_ID
        and str(patient.get("source_patient_id") or "").upper() == SYNTHETIC_JORDAN_SOURCE_ID
        and str(provenance.get("source") or "").upper() == "SIGNAL_DEMO"
        and str(facility.get("facility_id") or "").upper() == SYNTHETIC_JORDAN_FACILITY_ID
    )


def _fill_missing(current: dict[str, Any] | None, defaults: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    values = dict(current or {})
    changed = False
    for key, value in defaults.items():
        if is_missing(values.get(key)):
            values[key] = value
            changed = True
    return values, changed


def apply_synthetic_jordan_reporting_defaults(case: Any) -> list[str]:
    """Persist fixture-backed defaults only to the exact synthetic Jordan case."""
    if not is_synthetic_jordan_case(case):
        return []

    changed: list[str] = []
    case.patient, patient_changed = _fill_missing(case.patient, PATIENT_DEFAULTS)
    if patient_changed:
        changed.append("patient.demo_defaults")

    case.report_fields, fields_changed = _fill_missing(case.report_fields, REPORT_FIELD_DEFAULTS)
    if fields_changed:
        changed.extend(f"report_fields.{key}" for key in REPORT_FIELD_DEFAULTS if key in case.report_fields)

    case.provider, provider_changed = _fill_missing(case.provider, PROVIDER_DEFAULTS)
    if provider_changed:
        case.provider["status"] = "HUMAN_COMPLETED"
        case.provider["missing_fields"] = []
        changed.append("provider.demo_defaults")

    case.facility, facility_changed = _fill_missing(case.facility, FACILITY_DEFAULTS)
    if facility_changed:
        changed.append("facility.demo_defaults")

    case.clinical_evidence, clinical_changed = _fill_missing(case.clinical_evidence, CLINICAL_DEFAULTS)
    if clinical_changed:
        changed.append("clinical_evidence.demo_defaults")

    # The checked-in synthetic measles fixture is a reportable case with this
    # Texas rule. Keep workflow gates active; only correct the demo Case data.
    if (
        str(case.reportability_evidence_status or "").upper() == "LAB_POSITIVE"
        and str(case.final_decision or "").upper() in {"NEEDS_REVIEW", "PROCEED_TO_RULES"}
    ):
        case.reportability_decision = "REPORT"
        case.final_decision = "REPORT"
        case.rule_id = "TX-MEASLES-IMMEDIATE"
        changed.append("reportability.demo_fixture")

    if changed:
        warnings = list(case.warnings or [])
        demo_notice = "Synthetic demo defaults were used; this is not a real patient record."
        if demo_notice not in warnings:
            warnings.append(demo_notice)
        case.warnings = warnings
    return changed
