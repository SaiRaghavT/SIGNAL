from datetime import datetime, timezone
import json
from typing import Any
from uuid import UUID

from sqlalchemy import String, cast, func, inspect, or_
from sqlalchemy.orm import Session

from backend.app.agents.deadline_calculation.schemas import DeadlineCalculationRequest
from backend.app.agents.deadline_calculation.service import DeadlineCalculationService
from backend.app.detection.adapter import canonical_context_to_detection_input
from backend.app.detection.structured_trigger import detect_structured_triggers
from backend.app.detection.structured_trigger import STRUCTURED_TRIGGERS
from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.models.patient import Patient
from backend.app.models.encounter import Encounter
from backend.app.models.condition import Condition
from backend.app.models.observation import Observation
from backend.app.models.lab_result import LabResult
from backend.app.models.clinical_document import ClinicalDocument


class CanonicalPatientNotFoundError(ValueError):
    """Raised when a requested patient does not exist."""


deadline_calculation_service = DeadlineCalculationService()


def _deadline_time_metadata(deadline: datetime) -> dict[str, Any]:
    """Calculate time-relative fields from an authoritative deadline."""
    now = datetime.now(timezone.utc)
    normalized_deadline = deadline
    if normalized_deadline.tzinfo is None:
        normalized_deadline = normalized_deadline.replace(tzinfo=timezone.utc)
    else:
        normalized_deadline = normalized_deadline.astimezone(timezone.utc)

    minutes_remaining = int((normalized_deadline - now).total_seconds() / 60)
    if minutes_remaining <= 4 * 60:
        urgency = "CRITICAL"
    elif minutes_remaining <= 24 * 60:
        urgency = "HIGH"
    elif minutes_remaining <= 72 * 60:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    if normalized_deadline < now:
        deadline_status = "OVERDUE"
    elif normalized_deadline.date() == now.date():
        deadline_status = "DUE TODAY"
    elif minutes_remaining <= 72 * 60:
        deadline_status = "DUE SOON"
    else:
        deadline_status = "ON TRACK"

    return {
        "urgency": urgency,
        "minutes_remaining": minutes_remaining,
        "deadline_status": deadline_status,
    }


def _is_measles_condition(condition: Condition) -> bool:
    display = (condition.condition_display or "").casefold()
    if "measles" in display:
        return True
    return any(
        trigger.get("disease_id") == "measles"
        and trigger.get("resource_type") == "Condition"
        and (condition.condition_system or "").casefold() == str(trigger.get("code_system") or "").casefold()
        and (condition.condition_code or "").casefold() in {str(code).casefold() for code in trigger.get("codes", [])}
        for trigger in STRUCTURED_TRIGGERS
    )


def _condition_patient_filter(db: Session, condition: str):
    term = condition.strip().casefold()
    return (
        db.query(Condition.patient_id)
        .filter(func.lower(Condition.condition_display).like(f"%{term}%"))
        .distinct()
    )


def _case_patient_id(case: Case) -> UUID | None:
    patient_snapshot = case.patient
    if isinstance(patient_snapshot, str):
        try:
            patient_snapshot = json.loads(patient_snapshot)
        except (TypeError, ValueError):
            return None
    if not isinstance(patient_snapshot, dict):
        return None
    try:
        return UUID(str(patient_snapshot.get("patient_id")))
    except (TypeError, ValueError):
        return None


def _is_texas_jurisdiction(value: str | None) -> bool:
    return str(value or "").strip().casefold() in {"tx", "texas"}


def _patient_jurisdiction(
    patient: Patient,
    candidate: Candidate | None = None,
    case: Case | None = None,
) -> str | None:
    """Resolve the cohort jurisdiction from workflow jurisdiction or canonical location.

    A resolved case jurisdiction takes precedence, followed by a candidate's
    explicit jurisdiction. If neither exists, the existing jurisdiction resolver
    uses the canonical Patient state. Encounter.facility_id has no state data,
    so it is not treated as evidence of Texas.
    """
    if case and case.jurisdiction_status == "RESOLVED" and case.jurisdiction:
        jurisdiction = case.jurisdiction.strip().upper()
        return "TX" if jurisdiction == "TEXAS" else jurisdiction
    if candidate and candidate.jurisdiction:
        jurisdiction = candidate.jurisdiction.strip().upper()
        return "TX" if jurisdiction == "TEXAS" else jurisdiction
    result = resolve_jurisdiction(
        JurisdictionInput(
            candidate_id=str(patient.patient_id),
            patient_state=patient.state,
            patient_county=patient.county,
            facility_state=None,
            facility_county=None,
            disease="measles",
        )
    )
    return result.jurisdiction if result.status == "RESOLVED" else None


def _measles_worklist_patient_ids(db: Session) -> set[UUID]:
    """Collect distinct patients with existing canonical/workflow Measles evidence."""
    patient_ids = {
        row[0]
        for row in db.query(Condition.patient_id)
        .filter(func.lower(Condition.condition_display).like("%measles%"))
        .distinct()
        .all()
    }

    if not inspect(db.get_bind()).has_table(Case.__tablename__):
        measles_cases = []
    else:
        measles_cases = (
            db.query(Case)
            .filter(func.lower(Case.disease) == "measles")
            .order_by(Case.updated_at.desc())
            .all()
        )
    case_candidate_ids = {item.candidate_id for item in measles_cases}
    candidate_query = db.query(Candidate).filter(
        or_(
            func.lower(Candidate.disease_id) == "measles",
            Candidate.candidate_id.in_(case_candidate_ids) if case_candidate_ids else False,
        )
    )
    measles_candidates = candidate_query.all()
    for candidate in measles_candidates:
        try:
            patient_ids.add(UUID(candidate.patient_id))
        except (TypeError, ValueError):
            continue
    patient_id_by_candidate = {
        candidate.candidate_id: candidate.patient_id
        for candidate in measles_candidates
    }
    for case in measles_cases:
        case_patient_id = _case_patient_id(case)
        if case_patient_id is not None:
            patient_ids.add(case_patient_id)
        elif case.candidate_id in patient_id_by_candidate:
            try:
                patient_ids.add(UUID(patient_id_by_candidate[case.candidate_id]))
            except (TypeError, ValueError):
                pass

    lab_triggers = [
        trigger
        for trigger in STRUCTURED_TRIGGERS
        if trigger.get("trigger_type") == "LAB_RESULT"
        and str(trigger.get("disease_id", "")).casefold() == "measles"
    ]
    lab_match_predicates = []
    for trigger in lab_triggers:
        for term in trigger.get("test_terms", []):
            pattern = f"%{str(term).casefold()}%"
            lab_match_predicates.append(
                or_(
                    func.lower(LabResult.test_display).like(pattern),
                    func.lower(LabResult.test_code).like(pattern),
                    func.lower(LabResult.conclusion).like(pattern),
                )
            )
    if lab_match_predicates:
        possible_positive_labs = (
            db.query(LabResult)
            .filter(or_(*lab_match_predicates))
            .all()
        )
    else:
        # Detection trigger definitions are loaded dynamically and may not be
        # exposed through STRUCTURED_TRIGGERS. Keep the existing measles queue
        # discoverable from its canonical test display in that case.
        possible_positive_labs = (
            db.query(LabResult)
            .filter(
                or_(
                    func.lower(LabResult.test_display).like("%measles%"),
                    func.lower(LabResult.test_code).like("%measles%"),
                    func.lower(LabResult.conclusion).like("%measles%"),
                )
            )
            .all()
        )
    if lab_match_predicates or possible_positive_labs:
        for lab_result in possible_positive_labs:
            normalized = canonical_context_to_detection_input(
                {
                    "patient": {"patient_id": str(lab_result.patient_id)},
                    "lab_results": [_lab_result_to_dict(lab_result)],
                }
            )
            is_positive_measles = any(
                str(signal.get("disease_id", "")).casefold() == "measles"
                and str(signal.get("evidence", {}).get("source_id", ""))
                == str(lab_result.lab_result_id)
                for signal in detect_structured_triggers(normalized)
            )
            if is_positive_measles:
                patient_ids.add(lab_result.patient_id)

    if not patient_ids:
        return set()

    # Texas is determined only from explicit resolved workflow jurisdiction or
    # canonical patient state via the existing resolver; no patient is assumed
    # to be in Texas just because it has Measles evidence.
    patients_by_id = {
        patient.patient_id: patient
        for patient in db.query(Patient).filter(Patient.patient_id.in_(patient_ids)).all()
    }
    candidates_by_patient: dict[UUID, Candidate] = {}
    candidate_jurisdiction_query = db.query(Candidate).filter(
        Candidate.patient_id.in_([str(patient_id) for patient_id in patient_ids]),
        or_(
            func.lower(Candidate.disease_id) == "measles",
            Candidate.candidate_id.in_(case_candidate_ids) if case_candidate_ids else False,
        ),
    )
    for candidate in (
        candidate_jurisdiction_query
        .order_by(Candidate.updated_at.desc())
        .all()
    ):
        try:
            candidates_by_patient.setdefault(UUID(candidate.patient_id), candidate)
        except (TypeError, ValueError):
            continue
    cases_by_patient: dict[UUID, Case] = {}
    for case in measles_cases:
        case_patient_id = _case_patient_id(case)
        if case_patient_id is not None:
            cases_by_patient.setdefault(case_patient_id, case)

    texas_patient_ids = set()
    for patient_id, patient in patients_by_id.items():
        jurisdiction = _patient_jurisdiction(
            patient,
            candidates_by_patient.get(patient_id),
            cases_by_patient.get(patient_id),
        )
        if _is_texas_jurisdiction(jurisdiction):
            texas_patient_ids.add(patient_id)
    return texas_patient_ids


def _condition_disease(condition: Condition) -> str | None:
    display = (condition.condition_display or "").casefold()
    if "measles" in display or "rubeola" in display:
        return "measles"
    system = (condition.condition_system or "").casefold()
    code = (condition.condition_code or "").casefold()
    for trigger in STRUCTURED_TRIGGERS:
        if trigger.get("resource_type") != "Condition":
            continue
        disease = str(trigger.get("disease_id") or "").strip()
        if not disease:
            continue
        code_match = (
            system == str(trigger.get("code_system") or "").casefold()
            and code in {str(value).casefold() for value in trigger.get("codes", [])}
        )
        if code_match or disease.casefold() in display:
            return disease
    if condition.condition_display and condition.condition_display.strip():
        return condition.condition_display.strip()
    if condition.condition_system and condition.condition_code:
        return f"{condition.condition_system}|{condition.condition_code}"
    return None


def _not_patient_birth_date(patient: Patient, event_time: datetime | None) -> bool:
    """Reject condition-derived timestamps that only repeat the DOB date."""
    return not (
        event_time is not None
        and patient.date_of_birth is not None
        and event_time.date() == patient.date_of_birth
    )


def _payload_event_time(payload: Any, patient: Patient) -> datetime | None:
    """Find explicit clinical event fields; ignore processing/creation timestamps."""
    if isinstance(payload, dict):
        for key in ("event_time", "effective_time", "onset_time"):
            value = payload.get(key)
            if isinstance(value, datetime) and _not_patient_birth_date(patient, value):
                return value
            if isinstance(value, str):
                try:
                    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if _not_patient_birth_date(patient, parsed):
                    return parsed
        for value in payload.values():
            found = _payload_event_time(value, patient)
            if found is not None:
                return found
    elif isinstance(payload, (list, tuple)):
        for value in payload:
            found = _payload_event_time(value, patient)
            if found is not None:
                return found
    return None


def _patient_deadline(
    patient: Patient,
    conditions: list[Condition],
    lab_results: list[LabResult],
    candidate: Candidate | None,
    case: Case | None,
    disease_filter: str | None = None,
    last_encounter: datetime | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    disease_candidates = [
        disease_filter,
        case.disease if case else None,
        candidate.disease_id if candidate else None,
        *(_condition_disease(condition) for condition in conditions),
    ]
    disease_candidates = [value for value in disease_candidates if value]
    disease = disease_candidates[0] if disease_candidates else None
    positive_lab_event_time = None
    if not disease and lab_results:
        detection_input = canonical_context_to_detection_input(
            {
                "patient": _patient_to_dict(patient),
                "conditions": [_condition_to_dict(item) for item in conditions],
                "observations": [],
                "lab_results": [_lab_result_to_dict(item) for item in lab_results],
            }
        )
        for signal in detect_structured_triggers(detection_input):
            signal_disease = str(signal.get("disease_id") or "")
            source_id = str(signal.get("evidence", {}).get("source_id") or "")
            if not signal_disease:
                continue
            disease_candidates.append(signal_disease)
            disease = signal_disease
            matching_lab = next(
                (item for item in lab_results if str(item.lab_result_id) == source_id),
                None,
            )
            if matching_lab is not None:
                positive_lab_event_time = (
                    matching_lab.effective_time
                    or matching_lab.issued_time
                    or next(
                        (item.effective_time for item in matching_lab.observations if item.effective_time),
                        None,
                    )
                )
            break
    if not disease:
        return None, "No disease could be resolved from the patient's condition or workflow data."

    jurisdiction = None
    if case and case.jurisdiction_status == "RESOLVED":
        jurisdiction = case.jurisdiction
    elif candidate and candidate.jurisdiction:
        jurisdiction = candidate.jurisdiction
    else:
        jurisdiction_result = resolve_jurisdiction(
            JurisdictionInput(
                candidate_id=str(patient.patient_id),
                patient_state=patient.state,
                patient_county=patient.county,
                facility_state=None,
                facility_county=None,
                disease=disease,
            )
        )
        if jurisdiction_result.status == "RESOLVED":
            jurisdiction = jurisdiction_result.jurisdiction
    if not jurisdiction:
        return None, "Jurisdiction could not be resolved from patient, facility, or workflow data."
    jurisdiction = "TX" if jurisdiction.strip().casefold() == "texas" else jurisdiction

    persisted_deadline = (case.deadline if case else None) or (candidate.deadline if candidate else None)
    rule = None
    selected_disease = None
    for disease_candidate in disease_candidates:
        try:
            rule = deadline_calculation_service._load_rule(
                disease=disease_candidate,
                jurisdiction=jurisdiction,
                rule_id=None,
            )
            selected_disease = disease_candidate
            break
        except ValueError:
            continue

    if rule is None and lab_results:
        detection_input = canonical_context_to_detection_input(
            {
                "patient": _patient_to_dict(patient),
                "conditions": [_condition_to_dict(item) for item in conditions],
                "observations": [],
                "lab_results": [_lab_result_to_dict(item) for item in lab_results],
            }
        )
        for signal in detect_structured_triggers(detection_input):
            signal_disease = str(signal.get("disease_id") or "")
            source_id = str(signal.get("evidence", {}).get("source_id") or "")
            if not signal_disease:
                continue
            try:
                rule = deadline_calculation_service._load_rule(
                    disease=signal_disease,
                    jurisdiction=jurisdiction,
                    rule_id=None,
                )
                selected_disease = signal_disease
                matching_lab = next(
                    (item for item in lab_results if str(item.lab_result_id) == source_id),
                    None,
                )
                if matching_lab is not None:
                    positive_lab_event_time = (
                        matching_lab.effective_time
                        or matching_lab.issued_time
                        or next(
                            (item.effective_time for item in matching_lab.observations if item.effective_time),
                            None,
                        )
                    )
                break
            except ValueError:
                continue

    if rule is None:
        if persisted_deadline is not None and last_encounter is None:
            return {
                "deadline": persisted_deadline,
                "status": "PERSISTED",
                "calculation_basis": "Existing workflow deadline.",
                "disease": disease,
                "jurisdiction": jurisdiction,
                "rule_id": None,
                "reporting_timing": None,
                "reporting_method": None,
                **_deadline_time_metadata(persisted_deadline),
            }, None
        if not disease:
            return None, "No condition could be resolved from the patient's clinical or workflow data."
        return None, f"No Texas 2026 reporting deadline rule applies to '{disease}' in {jurisdiction}."

    disease = selected_disease or disease
    reporting = rule.get("reporting", {})
    rule_id = rule.get("rule_id")
    if str(reporting.get("timing", "")).upper() == "SEE_RULES":
        return {
            "deadline": None,
            "status": "SEE_RULES",
            "calculation_basis": rule.get("instructions") or "Follow the condition-specific Texas reporting rules.",
            "disease": disease,
            "jurisdiction": jurisdiction,
            "rule_id": rule_id,
            "reporting_timing": "SEE_RULES",
            "reporting_method": reporting.get("method"),
            "is_immediate": False,
            "effective_year": rule.get("effective_year"),
            "source_url": rule.get("source_url"),
            "applicability": rule.get("applicability"),
        }, None

    event_time = None
    if case:
        event_time = _payload_event_time(case.clinical_evidence, patient)
        if event_time is None:
            event_time = _payload_event_time(case.laboratory_evidence, patient)
    if event_time is None and candidate:
        event_time = _payload_event_time(candidate.evidence, patient)
        if event_time is None:
            event_time = _payload_event_time(candidate.signals, patient)
    if event_time is None:
        event_time = positive_lab_event_time
    if event_time is None:
        for condition in conditions:
            if condition.onset_time and _not_patient_birth_date(patient, condition.onset_time):
                event_time = condition.onset_time
                break
    if event_time is None:
        for lab_result in lab_results:
            event_time = (
                lab_result.effective_time
                or lab_result.issued_time
                or next(
                    (item.effective_time for item in lab_result.observations if item.effective_time),
                    None,
                )
            )
            if event_time is not None:
                break
    if event_time is None:
        event_time = last_encounter

    if event_time is None:
        if persisted_deadline is not None:
            return {
                "deadline": persisted_deadline,
                "status": "PERSISTED",
                "calculation_basis": "Existing workflow deadline; no newer reporting trigger is recorded.",
                "disease": disease,
                "jurisdiction": jurisdiction,
                "rule_id": rule_id,
                "reporting_timing": reporting.get("timing"),
                "reporting_method": reporting.get("method"),
                "effective_year": rule.get("effective_year"),
                "source_url": rule.get("source_url"),
                **_deadline_time_metadata(persisted_deadline),
            }, None
        return None, "No clinical event or encounter timestamp is available to calculate a reporting deadline."
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)

    try:
        result = deadline_calculation_service.calculate(
            DeadlineCalculationRequest(
                event_time=event_time,
                disease=disease,
                jurisdiction=jurisdiction,
                rule_id=rule_id,
                reporting_scope="CASE_REPORT",
            )
        )
    except ValueError as exc:
        return None, str(exc)
    result_data = result.model_dump()
    if result.deadline is not None:
        result_data.update(_deadline_time_metadata(result.deadline))
    return result_data, None


def list_patients(
    db: Session,
    page: int = 1,
    page_size: int = 10,
    search: str | None = None,
    facility: str | None = None,
    condition: str | None = None,
) -> dict[str, Any]:
    """Return a paginated patient list using fields present in canonical models."""
    query = db.query(Patient)
    search_text = (search or "").strip()
    if search_text:
        pattern = f"%{search_text}%"
        query = query.filter(or_(
            cast(Patient.patient_id, String).ilike(pattern),
            Patient.source_patient_id.ilike(pattern),
            Patient.first_name.ilike(pattern),
            Patient.last_name.ilike(pattern),
            cast(Patient.date_of_birth, String).ilike(pattern),
        ))

    facility_text = (facility or "").strip()
    if facility_text:
        patient_ids_at_facility = (
            db.query(Encounter.patient_id)
            .filter(Encounter.facility_id == facility_text)
            .distinct()
        )
        query = query.filter(Patient.patient_id.in_(patient_ids_at_facility))

    condition_text = (condition or "").strip()
    if condition_text.casefold() == "measles":
        query = query.filter(Patient.patient_id.in_(_measles_worklist_patient_ids(db)))
    elif condition_text:
        query = query.filter(Patient.patient_id.in_(_condition_patient_filter(db, condition_text)))

    ordered_query = query.order_by(Patient.created_at.desc(), Patient.patient_id.asc())
    is_measles_worklist = condition_text.casefold() == "measles"
    if is_measles_worklist:
        worklist_patients = ordered_query.all()
        total = len(worklist_patients)
        start = (page - 1) * page_size
        patients = worklist_patients[start:start + page_size]
    else:
        total = query.count()
        patients = ordered_query.offset((page - 1) * page_size).limit(page_size).all()
        worklist_patients = patients
    patient_ids = [patient.patient_id for patient in worklist_patients]

    facilities = [
        row[0]
        for row in (
            db.query(Encounter.facility_id)
            .filter(Encounter.facility_id.isnot(None))
            .distinct()
            .order_by(Encounter.facility_id.asc())
            .all()
        )
        if row[0]
    ]

    encounters = []
    conditions = []
    lab_results = []
    if patient_ids:
        encounters = (
            db.query(Encounter)
            .filter(Encounter.patient_id.in_(patient_ids))
            .order_by(Encounter.start_time.desc().nullslast())
            .all()
        )
        conditions = (
            db.query(Condition)
            .filter(Condition.patient_id.in_(patient_ids))
            .order_by(Condition.recorded_time.desc().nullslast())
            .all()
        )
        lab_results = (
            db.query(LabResult)
            .filter(LabResult.patient_id.in_(patient_ids))
            .order_by(LabResult.issued_time.desc().nullslast())
            .all()
        )

    last_encounter_by_patient: dict[UUID, datetime] = {}
    if patient_ids:
        last_encounter_by_patient = dict(
            db.query(
                Encounter.patient_id,
                func.max(func.coalesce(Encounter.end_time, Encounter.start_time)),
            )
            .filter(
                Encounter.patient_id.in_(patient_ids),
                func.coalesce(Encounter.end_time, Encounter.start_time).isnot(None),
            )
            .group_by(Encounter.patient_id)
            .all()
        )

    facility_by_patient: dict[UUID, str] = {}
    for encounter in encounters:
        if encounter.facility_id:
            facility_by_patient.setdefault(encounter.patient_id, encounter.facility_id)

    conditions_by_patient: dict[UUID, list[dict[str, str | None]]] = {}
    condition_label_by_patient: dict[UUID, str] = {}
    measles_by_patient: set[UUID] = set()
    for condition in conditions:
        if condition.condition_display or condition.condition_code:
            value = {
                "code": condition.condition_code,
                "display": condition.condition_display,
            }
            conditions_by_patient.setdefault(condition.patient_id, []).append(value)
            is_measles = _is_measles_condition(condition)
            label = condition.condition_display or ("Measles" if is_measles else condition.condition_code)
            current = condition_label_by_patient.get(condition.patient_id)
            if label and (current is None or (is_measles and condition.patient_id not in measles_by_patient)):
                condition_label_by_patient[condition.patient_id] = label
            if is_measles:
                measles_by_patient.add(condition.patient_id)

    measles_lab_label_by_patient: dict[UUID, str] = {}
    for lab_result in lab_results:
        label = (lab_result.test_display or "").strip()
        if label and "measles" in label.casefold():
            measles_lab_label_by_patient.setdefault(lab_result.patient_id, "Measles")
    for patient_id, label in measles_lab_label_by_patient.items():
        condition_label_by_patient.setdefault(patient_id, label)
    if condition_text.casefold() == "measles":
        for patient_id in patient_ids:
            condition_label_by_patient.setdefault(patient_id, "Measles")

    condition_rows_by_patient: dict[UUID, list[Condition]] = {}
    for condition in conditions:
        condition_rows_by_patient.setdefault(condition.patient_id, []).append(condition)

    lab_rows_by_patient: dict[UUID, list[LabResult]] = {}
    for lab_result in lab_results:
        lab_rows_by_patient.setdefault(lab_result.patient_id, []).append(lab_result)

    candidates_by_patient: dict[str, Candidate] = {}
    if patient_ids:
        for candidate in (
            db.query(Candidate)
            .filter(Candidate.patient_id.in_([str(patient_id) for patient_id in patient_ids]))
            .order_by(Candidate.updated_at.desc())
            .all()
        ):
            candidates_by_patient.setdefault(candidate.patient_id, candidate)

    cases_by_candidate: dict[str, Case] = {}
    candidate_ids = [candidate.candidate_id for candidate in candidates_by_patient.values()]
    cases_by_patient: dict[UUID, Case] = {}
    if inspect(db.get_bind()).has_table(Case.__tablename__):
        case_query = db.query(Case)
        if candidate_ids:
            case_query = case_query.filter(
                or_(Case.candidate_id.in_(candidate_ids), func.lower(Case.disease) == "measles")
            )
        else:
            case_query = case_query.filter(func.lower(Case.disease) == "measles")
        for case in case_query.order_by(Case.updated_at.desc()).all():
            cases_by_candidate.setdefault(case.candidate_id, case)
            case_patient_id = _case_patient_id(case)
            if case_patient_id is not None:
                cases_by_patient.setdefault(case_patient_id, case)

    deadlines_by_patient: dict[UUID, tuple[dict[str, Any] | None, str | None]] = {}
    jurisdiction_by_patient: dict[UUID, str | None] = {}
    for patient in worklist_patients:
        candidate = candidates_by_patient.get(str(patient.patient_id))
        case = (
            cases_by_candidate.get(candidate.candidate_id) if candidate else None
        ) or cases_by_patient.get(patient.patient_id)
        jurisdiction_by_patient[patient.patient_id] = _patient_jurisdiction(patient, candidate, case)
        deadlines_by_patient[patient.patient_id] = _patient_deadline(
            patient=patient,
            conditions=condition_rows_by_patient.get(patient.patient_id, []),
            lab_results=lab_rows_by_patient.get(patient.patient_id, []),
            candidate=candidate,
            case=case,
            disease_filter="measles" if condition_text.casefold() == "measles" else None,
            last_encounter=last_encounter_by_patient.get(patient.patient_id),
        )

        deadline_data, reason = deadlines_by_patient[patient.patient_id]
        if deadline_data:
            existing_priority = (case.severity if case else None) or (candidate.severity if candidate else None)
            if not deadline_data.get("urgency") and existing_priority:
                deadline_data["urgency"] = existing_priority

    return {
        "items": [
            {
                "patient_id": str(patient.patient_id),
                "source_patient_id": patient.source_patient_id,
                "first_name": patient.first_name,
                "last_name": patient.last_name,
                "date_of_birth": (
                    patient.date_of_birth.isoformat()
                    if patient.date_of_birth
                    else None
                ),
                "condition": condition_label_by_patient.get(patient.patient_id),
                "last_encounter": last_encounter_by_patient.get(patient.patient_id),
                "jurisdiction": jurisdiction_by_patient[patient.patient_id],
                "deadline": deadlines_by_patient[patient.patient_id][0],
                "deadline_reason": deadlines_by_patient[patient.patient_id][1],
                "facility": facility_by_patient.get(patient.patient_id),
                "conditions": [
                    {"code": item.condition_code, "display": item.condition_display}
                    for item in condition_rows_by_patient.get(patient.patient_id, [])
                ],
            }
            for patient in patients
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "facilities": facilities,
        "condition_filter": condition_text.title() if condition_text else None,
    }


def _patient_to_dict(patient: Patient) -> dict[str, Any]:
    return {
        "patient_id": str(patient.patient_id),
        "source_patient_id": patient.source_patient_id,

        # Patient name
        "first_name": patient.first_name,
        "last_name": patient.last_name,

        "date_of_birth": (
            patient.date_of_birth.isoformat()
            if patient.date_of_birth
            else None
        ),
        "sex": patient.sex,
        "address": {
            "line": patient.address_line,
            "city": patient.city,
            "county": patient.county,
            "state": patient.state,
            "postal_code": patient.postal_code,
        },
        "provenance": {
            "source": patient.source,
            "source_resource": patient.source_resource,
        },
    }


def _encounter_to_dict(encounter: Encounter) -> dict[str, Any]:
    return {
        "encounter_id": str(encounter.encounter_id),
        "source_encounter_id": encounter.source_encounter_id,
        "patient_id": str(encounter.patient_id),
        "facility_id": encounter.facility_id,
        "encounter_type": encounter.encounter_type,
        "status": encounter.status,
        "start_time": (
            encounter.start_time.isoformat()
            if encounter.start_time
            else None
        ),
        "end_time": (
            encounter.end_time.isoformat()
            if encounter.end_time
            else None
        ),
        "provenance": {
            "source": encounter.source,
            "source_resource": encounter.source_resource,
        },
    }


def _condition_to_dict(condition: Condition) -> dict[str, Any]:
    return {
        "condition_id": str(condition.condition_id),
        "source_condition_id": condition.source_condition_id,
        "patient_id": str(condition.patient_id),
        "encounter_id": (
            str(condition.encounter_id)
            if condition.encounter_id
            else None
        ),
        "code": {
            "system": condition.condition_system,
            "code": condition.condition_code,
            "display": condition.condition_display,
        },
        "clinical_status": condition.clinical_status,
        "verification_status": condition.verification_status,
        "onset_time": (
            condition.onset_time.isoformat()
            if condition.onset_time
            else None
        ),
        "recorded_time": (
            condition.recorded_time.isoformat()
            if condition.recorded_time
            else None
        ),
        "provenance": {
            "source": condition.source,
            "source_resource": condition.source_resource,
        },
    }


def _observation_to_dict(observation: Observation) -> dict[str, Any]:
    return {
        "observation_id": str(observation.observation_id),
        "source_observation_id": observation.source_observation_id,
        "patient_id": str(observation.patient_id),
        "encounter_id": (
            str(observation.encounter_id)
            if observation.encounter_id
            else None
        ),
        "code": {
            "system": observation.observation_system,
            "code": observation.observation_code,
            "display": observation.observation_display,
        },
        "status": observation.status,
        "value": {
            "numeric": (
                float(observation.value_numeric)
                if observation.value_numeric is not None
                else None
            ),
            "text": observation.value_text,
            "unit": observation.unit,
            "system": observation.value_system,
            "code": observation.value_code,
        },
        "effective_time": (
            observation.effective_time.isoformat()
            if observation.effective_time
            else None
        ),
        "provenance": {
            "source": observation.source,
            "source_resource": observation.source_resource,
        },
    }


def _lab_result_to_dict(lab_result: LabResult) -> dict[str, Any]:
    return {
        "lab_result_id": str(lab_result.lab_result_id),
        "source_lab_result_id": lab_result.source_lab_result_id,
        "patient_id": str(lab_result.patient_id),
        "encounter_id": (
            str(lab_result.encounter_id)
            if lab_result.encounter_id
            else None
        ),
        "test": {
            "system": lab_result.test_system,
            "code": lab_result.test_code,
            "display": lab_result.test_display,
        },
        "report_status": lab_result.report_status,
        "category": lab_result.category,
        "effective_time": (
            lab_result.effective_time.isoformat()
            if lab_result.effective_time
            else None
        ),
        "issued_time": (
            lab_result.issued_time.isoformat()
            if lab_result.issued_time
            else None
        ),
        "performer_reference": lab_result.performer_reference,
        "conclusion": lab_result.conclusion,
        "observations": [
            {
                "observation_id": str(observation.observation_id),
                "source_observation_id": observation.source_observation_id,
                "code": {
                    "system": observation.observation_system,
                    "code": observation.observation_code,
                    "display": observation.observation_display,
                },
                "value": {
                    "numeric": (
                        float(observation.value_numeric)
                        if observation.value_numeric is not None
                        else None
                    ),
                    "text": observation.value_text,
                    "unit": observation.unit,
                    "code": observation.value_code,
                    "system": observation.value_system,
                },
                "status": observation.status,
                "effective_time": (
                    observation.effective_time.isoformat()
                    if observation.effective_time
                    else None
                ),
            }
            for observation in lab_result.observations
        ],
        "provenance": {
            "source": lab_result.source,
            "source_resource": lab_result.source_resource,
        },
    }


def _clinical_document_to_dict(
    document: ClinicalDocument,
) -> dict[str, Any]:
    return {
        "document_id": str(document.document_id),
        "source_document_id": document.source_document_id,
        "patient_id": str(document.patient_id),
        "encounter_id": (
            str(document.encounter_id)
            if document.encounter_id
            else None
        ),
        "document_type": document.document_type,
        "document_status": document.document_status,
        "title": document.title,
        "document_date": (
            document.document_date.isoformat()
            if document.document_date
            else None
        ),
        "author_reference": document.author_reference,
        "content_type": document.content_type,
        "content_location": document.content_location,
        "extracted_text": document.extracted_text,
        "provenance": {
            "source": document.source,
            "source_resource": document.source_resource,
        },
    }


def get_patient_context(
    db: Session,
    patient_id: UUID,
) -> dict[str, Any]:
    """
    Retrieve the complete canonical context for one patient.

    This is the primary read interface for downstream SIGNAL
    components such as AI agents, reportability logic, case
    assembly, and workflow services.
    """

    patient = (
        db.query(Patient)
        .filter(Patient.patient_id == patient_id)
        .first()
    )

    if patient is None:
        raise CanonicalPatientNotFoundError(
            f"Patient not found: {patient_id}"
        )

    encounters = (
        db.query(Encounter)
        .filter(Encounter.patient_id == patient_id)
        .order_by(Encounter.start_time.asc())
        .all()
    )

    conditions = (
        db.query(Condition)
        .filter(Condition.patient_id == patient_id)
        .order_by(Condition.recorded_time.asc())
        .all()
    )

    observations = (
        db.query(Observation)
        .filter(Observation.patient_id == patient_id)
        .order_by(Observation.effective_time.asc())
        .all()
    )

    lab_results = (
        db.query(LabResult)
        .filter(LabResult.patient_id == patient_id)
        .order_by(LabResult.effective_time.asc())
        .all()
    )

    clinical_documents = (
        db.query(ClinicalDocument)
        .filter(ClinicalDocument.patient_id == patient_id)
        .order_by(ClinicalDocument.document_date.asc())
        .all()
    )

    return {
        "patient": _patient_to_dict(patient),
        "encounters": [
            _encounter_to_dict(encounter)
            for encounter in encounters
        ],
        "conditions": [
            _condition_to_dict(condition)
            for condition in conditions
        ],
        "observations": [
            _observation_to_dict(observation)
            for observation in observations
        ],
        "lab_results": [
            _lab_result_to_dict(lab_result)
            for lab_result in lab_results
        ],
        "clinical_documents": [
            _clinical_document_to_dict(document)
            for document in clinical_documents
        ],
    }
