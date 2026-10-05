from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.candidate import Candidate
from backend.app.models.patient import Patient

from .schemas import CandidateDispositionResult, CandidateDispositionUpdate, CandidateListResponse, CandidateResponse
from .service import candidate_to_response, update_candidate_disposition


router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


@router.get("", response_model=CandidateListResponse)
def list_candidates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    status: str | None = Query(None, max_length=50),
    disease: str | None = Query(None, max_length=100),
    db: Session = Depends(get_db),
) -> CandidateListResponse:
    query = db.query(Candidate)
    if status:
        query = query.filter(Candidate.status == status)
    if disease:
        query = query.filter(Candidate.disease_id.ilike(f"%{disease.strip()}%"))
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        patient_ids = db.query(Patient.patient_id).filter(
            or_(Patient.first_name.ilike(pattern), Patient.last_name.ilike(pattern))
        )
        query = query.filter(or_(Candidate.patient_id.in_(patient_ids), Candidate.disease_id.ilike(pattern)))
    total = query.count()
    candidates = query.order_by(Candidate.updated_at.desc(), Candidate.candidate_id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return CandidateListResponse(
        items=[candidate_to_response(db, item) for item in candidates],
        page=page,
        page_size=page_size,
        total=total,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{candidate_id}", response_model=CandidateResponse)
def get_candidate(candidate_id: UUID, db: Session = Depends(get_db)) -> CandidateResponse:
    candidate = db.query(Candidate).filter(Candidate.candidate_id == str(candidate_id)).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return candidate_to_response(db, candidate)


@router.post("/{candidate_id}/disposition", response_model=CandidateDispositionResult)
def set_candidate_disposition(
    candidate_id: UUID,
    request: CandidateDispositionUpdate,
    db: Session = Depends(get_db),
) -> dict:
    candidate = db.query(Candidate).filter(Candidate.candidate_id == str(candidate_id)).first()
    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found.")
    return update_candidate_disposition(db, candidate, request)
