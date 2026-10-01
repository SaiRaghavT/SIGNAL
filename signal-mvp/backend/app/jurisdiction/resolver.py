from .models import JurisdictionInput, JurisdictionResult

def resolve_jurisdiction(data: JurisdictionInput) -> JurisdictionResult:
    patient_state = data.patient_state.strip().upper() if data.patient_state else None
    facility_state = data.facility_state.strip().upper() if data.facility_state else None
    reasons = []

    if patient_state and facility_state and patient_state == facility_state:
        reasons.append(f"Patient and facility are both located in {patient_state}.")
        return JurisdictionResult(data.candidate_id, patient_state, "RESOLVED", reasons)

    if patient_state and facility_state and patient_state != facility_state:
        reasons.append(f"Patient location is {patient_state}, while facility location is {facility_state}.")
        reasons.append("Conflicting location context requires jurisdiction review.")
        return JurisdictionResult(data.candidate_id, None, "NEEDS_REVIEW", reasons)

    if patient_state:
        reasons.append(f"Only patient state is available: {patient_state}.")
        return JurisdictionResult(data.candidate_id, patient_state, "NEEDS_REVIEW", reasons)

    if facility_state:
        reasons.append(f"Only facility state is available: {facility_state}.")
        return JurisdictionResult(data.candidate_id, facility_state, "NEEDS_REVIEW", reasons)

    reasons.append("No patient or facility state is available.")
    return JurisdictionResult(data.candidate_id, None, "NEEDS_REVIEW", reasons)
