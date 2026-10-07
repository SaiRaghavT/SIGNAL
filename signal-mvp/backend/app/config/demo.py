"""Stable identifiers for SIGNAL's controlled Texas demo dataset."""

DEMO_FACILITY_ID = "SIGNAL-MVP-TX-DEMO"
DEMO_PATIENT_SOURCE_ID = "SIGNAL-DEMO-TX-002"


def is_demo_case(case) -> bool:
    patient = case.patient if isinstance(case.patient, dict) else {}
    facility = case.facility if isinstance(case.facility, dict) else {}
    facility_ids = {
        str(facility.get(key) or "").strip().upper()
        for key in ("facility_id", "id", "source_id")
    }
    source_patient_id = str(patient.get("source_patient_id") or "").strip().upper()
    return DEMO_FACILITY_ID in facility_ids and source_patient_id == DEMO_PATIENT_SOURCE_ID
