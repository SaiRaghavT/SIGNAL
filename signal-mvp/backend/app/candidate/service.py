import hashlib
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.agents.candidate_disposition.schemas import CandidateDispositionRequest
from backend.app.agents.candidate_disposition.service import determine_candidate_disposition
from backend.app.models.candidate import Candidate
from backend.app.models.patient import Patient

from .schemas import CandidateDispositionUpdate, CandidateResponse


def persist_detection_candidates(db: Session, detection: dict[str, Any]) -> list[Candidate]:
    patient_id = str(detection.get("patient_id") or "")
    if not patient_id:
        raise ValueError("Detection result must identify a canonical patient.")
    candidates = detection.get("candidates")
    if not isinstance(candidates, list):
        raise ValueError("Detection result candidates must be a list.")

    persisted: list[Candidate] = []
    for value in candidates:
        disease = str(value.get("disease_id") or "").strip()
        if not disease:
            continue
        encounter_id = value.get("encounter_id")
        natural_key = "\x1f".join((patient_id, disease.casefold(), str(encounter_id or "")))
        detection_key = hashlib.sha256(natural_key.encode("utf-8")).hexdigest()
        candidate = db.query(Candidate).filter(Candidate.detection_key == detection_key).first()
        signals = value.get("signals") or []
        evidence = value.get("evidence") or []
        confidence_values = [
            item.get("confidence")
            for item in signals
            if isinstance(item, dict) and isinstance(item.get("confidence"), (int, float))
        ]
        if candidate is None:
            candidate = Candidate(
                detection_key=detection_key,
                patient_id=patient_id,
                encounter_id=str(encounter_id) if encounter_id is not None else None,
                disease_id=disease,
                detection_source=",".join(value.get("trigger_types") or ["structured"]),
                confidence=max(confidence_values) if confidence_values else value.get("confidence"),
                evidence=evidence,
                signals=signals,
                status="POTENTIAL",
            )
            db.add(candidate)
            db.flush()
            AuditLedgerService().record_event(
                AuditEventCreate(
                    entity_type="CANDIDATE",
                    entity_id=candidate.candidate_id,
                    event_type="CANDIDATE_CREATED",
                    actor_type="SYSTEM",
                    actor_id="SIGNAL",
                    source_agent="candidate_fusion",
                    status="SUCCESS",
                    new_value={"patient_id": patient_id, "disease": disease},
                    metadata={"detection_key": detection_key},
                ),
                db,
            )
        else:
            candidate.confidence = max(confidence_values) if confidence_values else candidate.confidence
            candidate.evidence = evidence
            candidate.signals = signals
            candidate.detection_source = ",".join(value.get("trigger_types") or ["structured"])
        persisted.append(candidate)

    db.commit()
    for candidate in persisted:
        db.refresh(candidate)
    return persisted


def candidate_to_response(db: Session, candidate: Candidate) -> CandidateResponse:
    patient = db.query(Patient).filter(Patient.patient_id == candidate.patient_id).first()
    if patient is None:
        raise HTTPException(status_code=409, detail="Candidate refers to a missing canonical patient.")
    return CandidateResponse(
        candidate_id=candidate.candidate_id,
        patient_id=candidate.patient_id,
        patient={
            "patient_id": str(patient.patient_id),
            "first_name": patient.first_name,
            "last_name": patient.last_name,
            "date_of_birth": patient.date_of_birth,
            "sex": patient.sex,
        },
        disease=candidate.disease_id,
        jurisdiction=candidate.jurisdiction,
        evidence=candidate.evidence or [],
        confidence=candidate.confidence,
        status=candidate.status,
        case_id=candidate.case_id,
        created_at=candidate.created_at,
        updated_at=candidate.updated_at,
    )


def update_candidate_disposition(
    db: Session,
    candidate: Candidate,
    update: CandidateDispositionUpdate,
) -> dict[str, Any]:
    signals = candidate.signals or []
    data = determine_candidate_disposition(
        CandidateDispositionRequest(
            candidate_id=candidate.candidate_id,
            ai_decision=update.ai_decision,
            ai_confidence=update.ai_confidence if update.ai_confidence is not None else candidate.confidence,
            laboratory_decision=update.laboratory_decision,
            rule_decision=update.rule_decision,
            jurisdiction_status=update.jurisdiction_status,
            reportability_decision=update.reportability_decision,
            human_review_required=update.human_review_required,
            conflicts=update.conflicts,
        )
    )
    candidate.status = data.final_decision
    AuditLedgerService().record_event(
        AuditEventCreate(
            entity_type="CANDIDATE",
            entity_id=candidate.candidate_id,
            event_type="CANDIDATE_DISPOSITION_UPDATED",
            actor_type="USER",
            actor_id="reporting_user",
            source_agent="candidate_disposition",
            status="SUCCESS",
            new_value={"decision": data.final_decision},
            metadata={"signal_count": len(signals)},
        ),
        db,
    )
    db.commit()
    db.refresh(candidate)
    return {
        "candidate_id": candidate.candidate_id,
        "final_decision": data.final_decision,
        "reasons": data.reasons,
        "warnings": data.warnings,
        "status": candidate.status,
    }
