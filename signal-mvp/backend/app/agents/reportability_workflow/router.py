from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.canonical.query_service import CanonicalPatientNotFoundError
from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.config.demo import is_demo_case

from .schemas import CandidateProcessRequest, CandidateProcessResponse, CandidateWorkflowInput
from .service import process_candidate


router = APIRouter(tags=["Reportability Workflow"])


@router.post(
    "/api/candidate/process",
    response_model=CandidateProcessResponse,
)
def process_candidate_endpoint(
    request: CandidateProcessRequest,
    db: Session = Depends(get_db),
) -> CandidateProcessResponse:
    """Process a persisted candidate using canonical evidence as source of truth."""

    try:
        candidate = (
            db.query(Candidate)
            .filter(Candidate.candidate_id == request.candidate_id)
            .first()
        )
        if candidate is None:
            raise HTTPException(status_code=404, detail="Candidate not found.")
        already_processed = candidate.status == "PROCESSED"
        if candidate.status in {"CLOSED", "REJECTED"} or (already_processed and not candidate.case_id):
            raise HTTPException(status_code=409, detail=f"Candidate is not processable from status {candidate.status}.")
        existing_case_id = None
        if candidate.case_id:
            linked_case = db.query(Case).filter(Case.case_id == candidate.case_id).first()
            if linked_case is not None and linked_case.candidate_id == candidate.candidate_id and is_demo_case(linked_case):
                existing_case_id = str(linked_case.case_id)

        evidence = candidate.evidence or []
        signals = candidate.signals or []
        lab_evidence = [
            item for item in signals
            if isinstance(item, dict) and item.get("trigger_type") == "LAB_RESULT"
        ]
        result = process_candidate(
            CandidateWorkflowInput(
                candidate_id=candidate.candidate_id,
                existing_case_id=existing_case_id,
                patient_id=candidate.patient_id,
                disease=candidate.disease_id,
                clinical_evidence={
                    "candidate_evidence": evidence,
                    "candidate_signals": signals,
                },
                laboratory_evidence=lab_evidence,
                ai_evidence={"confidence": candidate.confidence},
            ),
            db,
        )
        candidate.status = "PROCESSED"
        candidate.case_id = result["case"]["case_id"]
        candidate.jurisdiction = result["jurisdiction"].get("value")
        if not already_processed:
            AuditLedgerService().record_event(
                AuditEventCreate(
                    entity_type="CANDIDATE",
                    entity_id=candidate.candidate_id,
                    event_type="CANDIDATE_PROCESSED",
                    actor_type="SYSTEM",
                    actor_id="SIGNAL",
                    source_agent="reportability_workflow",
                    status="SUCCESS",
                    new_value={"case_id": candidate.case_id, "workflow_status": result["workflow_status"]},
                ),
                db,
            )
        db.commit()
        return result
    except HTTPException:
        raise
    except CanonicalPatientNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
