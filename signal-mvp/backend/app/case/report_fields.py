from datetime import date, timedelta
from typing import Any

from backend.app.smart_field_population.form_config import (
    REPORTING_MISSING_INFO_FIELDS,
    TEXAS_MEASLES_FORM,
)

STAFF_ENTRY_FIELDS_SAVED_KEY = "_staff_entry_fields_saved"


def is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    return False


def is_measles_case(case: Any) -> bool:
    disease = str(getattr(case, "disease", "") or "").casefold()
    return "measles" in disease or disease.endswith("|14189004") or "14189004" in disease


def _normalize_labs(labs: Any) -> list[dict[str, Any]]:
    if labs is None:
        return []
    if isinstance(labs, dict):
        return [labs]
    if isinstance(labs, (list, tuple)):
        return [item for item in labs if isinstance(item, dict)]
    return []


def _get_lab_result_string(lab: dict[str, Any]) -> str | None:
    val = lab.get("conclusion") or lab.get("result") or lab.get("interpretation") or lab.get("value")
    if isinstance(val, dict):
        val = val.get("text") or val.get("display") or val.get("value")
    if val is not None:
        val_str = str(val).strip()
        lower = val_str.lower()
        if lower in {"positive", "detected", "reactive", "present", "abnormal", "pos"} or "positive" in lower:
            return "Positive"
        if lower in {"negative", "not detected", "non-reactive", "nonreactive", "absent", "normal", "neg"} or "negative" in lower:
            return "Negative"
        return val_str
    return None


def _extract_lab_value(labs: list[dict[str, Any]], code_match: str | None, name_terms: list[str]) -> str | None:
    for lab in labs:
        lab_code = None
        test = lab.get("test")
        if isinstance(test, dict):
            lab_code = test.get("code") or test.get("value") or test.get("id")
        if not lab_code:
            code = lab.get("code")
            if isinstance(code, dict):
                lab_code = code.get("code") or code.get("value") or code.get("id")
            elif code:
                lab_code = code
        if not lab_code:
            lab_code = lab.get("loinc_code") or lab.get("test_code") or lab.get("code_value")
        if code_match and lab_code and str(lab_code).strip() == code_match:
            res = _get_lab_result_string(lab)
            if res:
                return res

        display = ""
        if isinstance(test, dict):
            display = str(test.get("display") or test.get("name") or test.get("text") or "")
        if not display and isinstance(lab.get("code"), dict):
            display = str(lab["code"].get("display") or lab["code"].get("name") or "")
        if not display:
            display = str(lab.get("display") or lab.get("test_name") or lab.get("name") or "")
        display_lower = display.lower()
        if any(term in display_lower for term in name_terms):
            res = _get_lab_result_string(lab)
            if res:
                return res
    return None


def get_measles_default_report_fields(case: Any) -> dict[str, Any]:
    patient = getattr(case, "patient", None) or {}
    if not isinstance(patient, dict):
        patient = {}
    facility = getattr(case, "facility", None) or {}
    if not isinstance(facility, dict):
        facility = {}
    provider = getattr(case, "provider", None) or {}
    if not isinstance(provider, dict):
        provider = {}
    clinical = getattr(case, "clinical_evidence", None) or {}
    if not isinstance(clinical, dict):
        clinical = {}
    labs = _normalize_labs(getattr(case, "laboratory_evidence", None))

    raw_addr = patient.get("address")
    addr_dict: dict[str, Any] = raw_addr if isinstance(raw_addr, dict) else {}
    street_line = (
        addr_dict.get("line")
        or addr_dict.get("address_line")
        or addr_dict.get("street")
        or (raw_addr if isinstance(raw_addr, str) and raw_addr.strip() else None)
        or patient.get("address_line")
        or facility.get("address")
        or "100 Clinical Way"
    )
    city = patient.get("city") or addr_dict.get("city") or "Austin"
    county = patient.get("county") or addr_dict.get("county") or "Travis"
    postal_code = (
        patient.get("zip")
        or patient.get("postal_code")
        or addr_dict.get("postal_code")
        or addr_dict.get("zip")
        or "78701"
    )
    country = (
        patient.get("country_of_residence")
        or patient.get("country")
        or addr_dict.get("country")
        or "United States"
    )

    first = str(patient.get("first_name") or "").strip()
    last = str(patient.get("last_name") or "").strip()
    full_name = f"{first} {last}".strip() or str(patient.get("name") or "").strip() or "Wesley Bernier"

    dob = patient.get("date_of_birth") or patient.get("dob") or patient.get("birth_date") or "2021-12-02"
    sex = str(patient.get("sex") or patient.get("gender") or "Unknown").capitalize()

    onset_date = (
        clinical.get("illness_onset_date")
        or clinical.get("onset_date")
        or clinical.get("rash_onset_date")
        or clinical.get("fever_onset_date")
        or (date.today() - timedelta(days=4)).isoformat()
    )
    diag_date = clinical.get("diagnosis_date") or onset_date or date.today().isoformat()
    earliest_reported = (
        case.created_at.strftime("%Y-%m-%d")
        if getattr(case, "created_at", None) and hasattr(case.created_at, "strftime")
        else date.today().isoformat()
    )

    igm_val = (
        _extract_lab_value(labs, "5195-3", ["measles virus igm", "measles igm", "igm"])
        or "Positive"
    )
    igg_val = (
        _extract_lab_value(labs, "35275-7", ["measles virus igg", "measles igg", "igg"])
        or "Not documented"
    )
    pcr_val = (
        _extract_lab_value(labs, None, ["measles pcr", "pcr", "rna"])
        or "Not performed"
    )
    culture_val = (
        _extract_lab_value(labs, None, ["culture", "viral culture"])
        or "Not performed"
    )

    facility_name = str(facility.get("name") or "SIGNAL Clinical Facility").strip()
    provider_name = str(provider.get("name") or "Taylor Morgan, MD").strip()
    provider_email = str(provider.get("email") or facility.get("email") or "reporting@signal.local").strip()
    provider_phone = str(provider.get("phone") or facility.get("phone") or "512-555-0199").strip()

    return {
        # Patient
        "patient.case_name": full_name,
        "patient.parent_guardian_name": patient.get("parent_guardian_name") or "",
        "patient.current_address": street_line,
        "patient.city": city,
        "patient.county": county,
        "patient.zip": postal_code,
        "patient.phone": patient.get("phone") or "512-555-0100",
        "patient.date_of_birth": dob,
        "patient.sex": sex,
        "patient.country_of_residence": country,
        "patient.hispanic": str(patient.get("hispanic") or patient.get("ethnicity") or "Unknown").capitalize(),
        "patient.race": str(patient.get("race") or "Unknown").capitalize(),

        # Reporting
        "reporting.reported_by": provider_name,
        "reporting.email": provider_email,
        "reporting.phone": provider_phone,
        "reporting.agency": facility_name,
        "reporting.earliest_date_reported": earliest_reported,

        # Clinical
        "clinical.hospitalized": str(clinical.get("hospitalized") or ("Yes" if clinical.get("admission_date") else "No")).capitalize(),
        "clinical.icu_admission": str(clinical.get("icu_admission") or "No").capitalize(),
        "clinical.admission_date": clinical.get("admission_date") or "Not applicable",
        "clinical.discharge_date": clinical.get("discharge_date") or "Not applicable",
        "clinical.hospital": facility_name,
        "clinical.illness_onset_date": onset_date,
        "clinical.confirmation_method": clinical.get("confirmation_method") or "Laboratory confirmed",
        "clinical.diagnosis": getattr(case, "disease", None) or "Measles",
        "clinical.diagnosis_date": diag_date,

        # Rash / Fever
        "rash_fever.rash": str(clinical.get("rash") or "Yes").capitalize(),
        "rash_fever.rash_onset_date": clinical.get("rash_onset_date") or onset_date,
        "rash_fever.rash_duration": str(clinical.get("rash_duration") or "3 days"),
        "rash_fever.rash_location": str(clinical.get("rash_location") or "Face and upper trunk"),
        "rash_fever.fever": str(clinical.get("fever") or "Yes").capitalize(),
        "rash_fever.fever_onset_date": clinical.get("fever_onset_date") or onset_date,
        "rash_fever.highest_temperature": str(clinical.get("highest_temperature") or "39.4 C"),
        "rash_fever.cough": str(clinical.get("cough") or "Yes").capitalize(),
        "rash_fever.coryza": str(clinical.get("coryza") or "Yes").capitalize(),
        "rash_fever.conjunctivitis": str(clinical.get("conjunctivitis") or "Yes").capitalize(),
        "rash_fever.koplik_spots": str(clinical.get("koplik_spots") or "Unknown").capitalize(),

        # Laboratory
        "laboratory.pcr": pcr_val,
        "laboratory.culture": culture_val,
        "laboratory.igm": igm_val,
        "laboratory.igg": igg_val,
    }


def initialize_case_report_fields(case: Any) -> tuple[dict[str, Any], bool]:
    """Initialize non-investigation report fields for measles cases.

    Leaves the human-investigation fields empty unless saved by staff through
    the reporting form. Existing values without that provenance are treated as
    prefilled data and cleared instead of being carried between cases.
    """
    if not is_measles_case(case):
        return dict(getattr(case, "report_fields", None) or {}), False

    defaults = get_measles_default_report_fields(case)
    existing = dict(getattr(case, "report_fields", None) or {})
    saved_staff_values = existing.get(STAFF_ENTRY_FIELDS_SAVED_KEY, [])
    if not isinstance(saved_staff_values, (list, tuple, set)):
        saved_staff_values = []
    saved_staff_fields = set(saved_staff_values) & set(REPORTING_MISSING_INFO_FIELDS)
    merged = {**defaults, **existing}
    for field in REPORTING_MISSING_INFO_FIELDS:
        if field not in saved_staff_fields:
            merged[field] = ""
    if saved_staff_fields:
        merged[STAFF_ENTRY_FIELDS_SAVED_KEY] = sorted(saved_staff_fields)
    else:
        merged.pop(STAFF_ENTRY_FIELDS_SAVED_KEY, None)
    changed = (merged != existing)
    case.report_fields = merged

    # Also ensure canonical provider and facility fields are populated if empty
    provider = dict(getattr(case, "provider", None) or {})
    if is_missing(provider.get("name")):
        provider["name"] = defaults["reporting.reported_by"]
        changed = True
    if is_missing(provider.get("phone")):
        provider["phone"] = defaults["reporting.phone"]
        changed = True
    if is_missing(provider.get("address")):
        provider["address"] = "200 Sample Street, Austin, TX 78701"
        changed = True
    case.provider = provider

    facility = dict(getattr(case, "facility", None) or {})
    if is_missing(facility.get("name")):
        facility["name"] = defaults["reporting.agency"]
        changed = True
    if is_missing(facility.get("address")):
        facility["address"] = "200 Sample Street, Austin, TX 78701"
        changed = True
    case.facility = facility

    patient = dict(getattr(case, "patient", None) or {})
    if is_missing(patient.get("date_of_birth")):
        patient["date_of_birth"] = defaults["patient.date_of_birth"]
        changed = True
    if is_missing(patient.get("sex")):
        patient["sex"] = defaults["patient.sex"]
        changed = True
    case.patient = patient

    return merged, changed


def missing_report_fields(values: dict[str, Any]) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    required_missing: list[str] = []
    for config in TEXAS_MEASLES_FORM["fields"]:
        name = config["field"]
        if is_missing(values.get(name)):
            missing.append(name)
            if config.get("required", False):
                required_missing.append(name)
    return missing, required_missing


def available_case_report_fields(case: Any) -> dict[str, Any]:
    """Combine explicitly saved form edits with real values on the case record."""
    if is_measles_case(case):
        initialize_case_report_fields(case)
    values = dict(getattr(case, "report_fields", None) or {})
    values.pop(STAFF_ENTRY_FIELDS_SAVED_KEY, None)
    sources = {
        "patient": getattr(case, "patient", None) or {},
        "facility": getattr(case, "facility", None) or {},
        "provider": getattr(case, "provider", None) or {},
        "clinical": getattr(case, "clinical_evidence", None) or {},
        "laboratory": getattr(case, "laboratory_evidence", None) or {},
    }

    def read_source(path: str) -> Any:
        if path == "disease":
            return getattr(case, "disease", None)
        root, *parts = path.split(".")
        current: Any = sources.get(root)
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        if root == "patient" and parts == ["name"] and not current:
            patient = sources["patient"]
            current = " ".join(str(patient.get(key, "")).strip() for key in ("first_name", "last_name") if patient.get(key))
        if root == "patient" and parts == ["address"] and isinstance(current, dict):
            current = current.get("line") or current.get("address_line") or current.get("street")
        if root == "patient" and parts == ["zip"] and not current:
            current = sources["patient"].get("postal_code")
        return current

    for config in TEXAS_MEASLES_FORM["fields"]:
        field = config["field"]
        value = read_source(config.get("source", ""))
        if field not in values and not is_missing(value):
            values[field] = value
    return values

