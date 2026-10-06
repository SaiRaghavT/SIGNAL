import json
from datetime import date
from pathlib import Path
from threading import Lock
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.ingestion.fhir.batch_service import ingest_fhir_bundles
from backend.app.ingestion.fhir.service import ingest_fhir_bundle
from backend.app.ingestion.fhir.validator import FHIRValidationError


router = APIRouter(
    prefix="/api/ingestion",
    tags=["FHIR Ingestion"],
)

FHIR_SEED_DIR = Path(__file__).resolve().parents[4] / "data" / "seed" / "fhir"
_seed_candidates: tuple[dict[str, Any], ...] | None = None
_seed_candidates_lock = Lock()


def _concept_display(concept: Any) -> str | None:
    if isinstance(concept, list):
        return next((display for item in concept if (display := _concept_display(item))), None)
    if not isinstance(concept, dict):
        return None
    if concept.get("text"):
        return str(concept["text"])
    for coding in concept.get("coding", []):
        if isinstance(coding, dict) and coding.get("display"):
            return str(coding["display"])
    return None


def _resource_value(resource: dict[str, Any]) -> str | None:
    for field in ("valueString", "valueCode", "valueBoolean", "valueInteger", "valueDateTime"):
        if resource.get(field) is not None:
            return str(resource[field])
    quantity = resource.get("valueQuantity")
    if isinstance(quantity, dict) and quantity.get("value") is not None:
        return f"{quantity['value']} {quantity.get('unit', '')}".strip()
    return _concept_display(resource.get("valueCodeableConcept"))


def _patient_extension_text(patient: dict[str, Any], url_fragment: str) -> str | None:
    extension = next((
        item for item in patient.get("extension", [])
        if url_fragment in str(item.get("url", ""))
    ), None)
    if not extension:
        return None
    nested = extension.get("extension", [])
    text = next((item.get("valueString") for item in nested if item.get("url") == "text"), None)
    if text:
        return str(text)
    category = next((item.get("valueCoding") for item in nested if item.get("url") == "ombCategory"), None)
    return _concept_display(category)


def _candidate_from_bundle(bundle: dict[str, Any], filename: str) -> dict[str, Any] | None:
    resources = [
        entry["resource"]
        for entry in bundle.get("entry", [])
        if isinstance(entry, dict) and isinstance(entry.get("resource"), dict)
    ]
    patient = next((item for item in resources if item.get("resourceType") == "Patient"), None)
    if patient is None:
        return None

    names = patient.get("name") or []
    name = next((item for item in names if item.get("use") == "official"), names[0] if names else {})
    patient_name = " ".join([*(name.get("given") or []), name.get("family", "")]).strip() or "Unknown patient"
    identifiers = patient.get("identifier") or []
    mrn = next((
        item.get("value")
        for item in identifiers
        if any(coding.get("code") == "MR" for coding in (item.get("type") or {}).get("coding", []))
    ), patient.get("id", "Not provided"))

    addresses = patient.get("address") or []
    address = next((item for item in addresses if item.get("use") == "home"), addresses[0] if addresses else {})
    state = address.get("state")
    city = address.get("city")
    county = address.get("district")
    address_lines = address.get("line") or []
    address_text = ", ".join(str(line) for line in address_lines if line) if isinstance(address_lines, list) else str(address_lines)
    postal_code = address.get("postalCode")
    country = address.get("country")
    phone = next((
        item.get("value") for item in patient.get("telecom", [])
        if item.get("system") == "phone" and item.get("value")
    ), None)
    race_text = _patient_extension_text(patient, "us-core-race")
    ethnicity_text = _patient_extension_text(patient, "us-core-ethnicity")
    patient_id = str(patient.get("id") or Path(filename).stem)

    conditions = [item for item in resources if item.get("resourceType") == "Condition"]
    condition_names = list(dict.fromkeys(
        display
        for item in conditions
        if (display := _concept_display(item.get("code")))
    ))
    condition = condition_names[0] if condition_names else "No condition recorded"

    encounters = [item for item in resources if item.get("resourceType") == "Encounter"]
    encounters.sort(key=lambda item: (item.get("period") or {}).get("start", ""))
    latest_encounter = encounters[-1] if encounters else {}
    facility = (latest_encounter.get("serviceProvider") or {}).get("display") or "Not recorded"
    detected = next((item.get("onsetDateTime") for item in conditions if item.get("onsetDateTime")), None)
    detected = detected or (latest_encounter.get("period") or {}).get("start") or "Not recorded"
    encounter_summaries = [
        {
            "date": (item.get("period") or {}).get("start") or "Not recorded",
            "type": _concept_display(item.get("type")) or _concept_display(item.get("class")) or "Encounter",
            "status": item.get("status") or "Not recorded",
            "facility": (item.get("serviceProvider") or {}).get("display") or "Not recorded",
            "reason": _concept_display(item.get("reasonCode")) or "Not recorded",
        }
        for item in encounters
    ]
    communications = patient.get("communication") or []
    language = _concept_display(communications[0].get("language")) if communications else None

    birth_date = patient.get("birthDate") or "Not provided"
    age = "N/A"
    try:
        born = date.fromisoformat(birth_date)
        today = date.today()
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    except ValueError:
        pass

    evidence = []
    resource_counts: dict[str, int] = {}
    for resource_index, item in enumerate(resources):
        resource_type = str(item.get("resourceType") or "Resource")
        resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
        if resource_type == "Patient":
            continue
        label = (
            _concept_display(item.get("code"))
            or _concept_display(item.get("type"))
            or _concept_display(item.get("vaccineCode"))
            or _concept_display(item.get("medicationCodeableConcept"))
            or (item.get("serviceProvider") or {}).get("display")
            or item.get("status")
            or resource_type
        )
        value = _resource_value(item)
        evidence.append(f"{resource_type} [{resource_index}]: {label}" + (f" · {value}" if value else ""))

    diagnostics = [item for item in resources if item.get("resourceType") == "DiagnosticReport"]
    laboratory_evidence = []
    for item in diagnostics:
        conclusion_codes = item.get("conclusionCode") or []
        if isinstance(conclusion_codes, dict):
            conclusion_codes = [conclusion_codes]
        conclusion = item.get("conclusion") or (
            _concept_display(conclusion_codes[0]) if conclusion_codes else None
        )
        laboratory_evidence.append({
            "test": _concept_display(item.get("code")) or "Diagnostic report",
            "status": item.get("status", "unknown"),
            "result": conclusion,
        })

    given_names = name.get("given") or []
    report_data: dict[str, Any] = {
        "patient.name": patient_name,
        "patient.first_name": " ".join(str(value) for value in given_names if value),
        "patient.last_name": name.get("family"),
        "patient.address": address_text,
        "patient.city": city,
        "patient.county": county,
        "patient.zip": postal_code,
        "patient.phone": phone,
        "patient.date_of_birth": patient.get("birthDate"),
        "patient.age": age if isinstance(age, int) else None,
        "patient.sex": patient.get("gender"),
        "patient.country_of_residence": (
            "USA" if country and country.casefold() in {"us", "u.s.", "united states", "united states of america"}
            else country
        ),
        "patient.race": [race_text] if race_text else None,
        "patient.hispanic": (
            "yes" if ethnicity_text and "hispanic" in ethnicity_text.casefold()
            else "no" if ethnicity_text
            else None
        ),
        "facility.name": facility if facility != "Not recorded" else None,
        "clinical.diagnosis": condition if condition != "No condition recorded" else None,
        "disease": condition if condition != "No condition recorded" else None,
    }
    primary_condition = conditions[0] if conditions else {}
    onset = primary_condition.get("onsetDateTime") or (primary_condition.get("onsetPeriod") or {}).get("start")
    diagnosis_date = primary_condition.get("recordedDate")
    if onset:
        report_data["clinical.onset_date"] = onset
    if diagnosis_date:
        report_data["clinical.diagnosis_date"] = diagnosis_date
    condition_encounter_reference = (primary_condition.get("encounter") or {}).get("reference")
    condition_encounter_id = condition_encounter_reference.rsplit("/", 1)[-1].removeprefix("urn:uuid:") if condition_encounter_reference else None
    condition_encounter = next((
        item for item in encounters
        if item.get("id") == condition_encounter_id
    ), None)
    encounter_class = (condition_encounter or {}).get("class") or {}
    encounter_class_code = encounter_class.get("code") if isinstance(encounter_class, dict) else None
    hospitalization_by_class = {
        "IMP": "inpatient",
        "AMB": "outpatient",
        "EMER": "ER only",
        "URG": "urgent care",
    }
    if encounter_class_code in hospitalization_by_class:
        report_data["clinical.hospitalized"] = hospitalization_by_class[encounter_class_code]
        if encounter_class_code == "IMP":
            encounter_period = condition_encounter.get("period") or {}
            if encounter_period.get("start"):
                report_data["clinical.admission_date"] = encounter_period["start"]
            if encounter_period.get("end"):
                report_data["clinical.discharge_date"] = encounter_period["end"]
    igm_result = next((
        item.get("result") or item.get("status")
        for item in laboratory_evidence
        if "igm" in item.get("test", "").casefold()
    ), None)
    if igm_result:
        report_data["laboratory.igm"] = igm_result
    report_data = {key: value for key, value in report_data.items() if value not in (None, "", [])}

    return {
        "id": patient_id,
        "patient": patient_name,
        "initials": "".join(part[0] for part in patient_name.split() if part)[:2].upper(),
        "mrn": str(mrn),
        "dob": birth_date,
        "sex": str(patient.get("gender") or "Not provided").capitalize(),
        "language": language or "Not recorded",
        "age": age,
        "facility": facility,
        "condition": condition,
        "conditions": condition_names,
        "jurisdiction": state or "Not recorded",
        "priority": "Not assessed",
        "detected": detected,
        "status": "Unreviewed",
        "rule": "Not evaluated",
        "deadline": "Not calculated",
        "confidence": "Not available",
        "evidence": evidence,
        "encounters": encounter_summaries,
        "provider": {},
        "patient_context": {"state": state, "county": county, "city": city, "address": address_text, "postal_code": postal_code, "country": country},
        "report_data": report_data,
        "laboratory_evidence": laboratory_evidence,
        "fhir_resource_counts": resource_counts,
        "source_file": filename,
    }


def _load_seed_candidates() -> tuple[dict[str, Any], ...]:
    global _seed_candidates
    if _seed_candidates is not None:
        return _seed_candidates

    with _seed_candidates_lock:
        if _seed_candidates is not None:
            return _seed_candidates
        candidates = []
        for path in sorted(FHIR_SEED_DIR.glob("*.json")):
            with path.open("r", encoding="utf-8") as source:
                candidate = _candidate_from_bundle(json.load(source), path.name)
            if candidate is not None:
                candidates.append(candidate)
        _seed_candidates = tuple(candidates)
        return _seed_candidates


def get_seed_candidate_summary(candidate_id: str) -> dict[str, Any] | None:
    return next((item for item in _load_seed_candidates() if item["id"] == candidate_id), None)


class FHIRBatchRequest(BaseModel):
    bundles: list[dict[str, Any]]


@router.get("/fhir/seed-candidates")
def list_seed_fhir_candidates() -> dict[str, Any]:
    if not FHIR_SEED_DIR.is_dir():
        raise HTTPException(status_code=404, detail="FHIR seed directory was not found.")
    items = _load_seed_candidates()
    return {"items": items, "total": len(items), "source": "data/seed/fhir"}


@router.post("/fhir")
def ingest_fhir(
    payload: dict[str, Any],
    source: str = Query(
        default="fhir",
        description=(
            "Source system of the FHIR Bundle, "
            "e.g. synthea, epic, hapi_fhir"
        ),
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Ingest a single FHIR Bundle into the SIGNAL
    canonical database.
    """

    try:
        result = ingest_fhir_bundle(
            db=db,
            payload=payload,
            source=source,
        )

        return result

    except FHIRValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="FHIR Bundle ingestion failed.",
        ) from exc


@router.post("/fhir/batch")
def ingest_fhir_batch(
    request: FHIRBatchRequest,
    source: str = Query(
        default="fhir",
        description=(
            "Source system of the FHIR Bundles, "
            "e.g. synthea, epic, hapi_fhir"
        ),
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """
    Ingest multiple FHIR Bundles into the SIGNAL
    canonical database.
    """

    try:
        return ingest_fhir_bundles(
            db=db,
            payloads=request.bundles,
            source=source,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="FHIR batch ingestion failed.",
        ) from exc