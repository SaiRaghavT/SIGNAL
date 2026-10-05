from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.app.agents.public_health_followup.schemas import PublicHealthFollowupRequest
from backend.app.agents.public_health_followup.service import PublicHealthFollowupService
from backend.app.database import get_db
from backend.app.models.follow_up import FollowUp

router = APIRouter(prefix="/api/follow-ups", tags=["Follow-ups"])


class FollowUpUpdate(BaseModel):
    status: str
    next_action: str | None = None
    due_date: date | None = None
    notes: str | None = None


def _payload(item: FollowUp) -> dict:
    return {
        "followup_id": item.followup_id,
        "case_id": item.case_id,
        "submission_id": item.submission_id,
        "patient_id": item.patient_id,
        "disease": item.disease,
        "status": item.status,
        "action": item.action,
        "next_action": item.next_action,
        "due_date": item.due_date,
        "notes": item.notes,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }


@router.get("")
def list_followups(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None, max_length=50),
    search: str | None = Query(None, max_length=200),
    db: Session = Depends(get_db),
) -> dict:
    query = db.query(FollowUp)
    if status:
        query = query.filter(FollowUp.status == status)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                FollowUp.case_id.ilike(pattern),
                FollowUp.submission_id.ilike(pattern),
                FollowUp.patient_id.ilike(pattern),
                FollowUp.disease.ilike(pattern),
            )
        )
    total = query.count()
    rows = query.order_by(FollowUp.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": [_payload(item) for item in rows], "page": page, "page_size": page_size, "total": total, "pages": (total + page_size - 1) // page_size}


def _get(db: Session, followup_id: str) -> FollowUp:
    row = db.query(FollowUp).filter(FollowUp.followup_id == followup_id).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Follow-up not found.")
    return row


@router.get("/{followup_id}")
def get_followup(followup_id: str, db: Session = Depends(get_db)) -> dict:
    return _payload(_get(db, followup_id))


@router.post("", status_code=201)
def create_followup(request: PublicHealthFollowupRequest, db: Session = Depends(get_db)) -> dict:
    try:
        result = PublicHealthFollowupService().process(request, db)
    except ValueError as exc:
        raise HTTPException(status_code=404 if str(exc).startswith("Case not found:") else 422, detail=str(exc)) from exc
    return result.model_dump(mode="json")


@router.patch("/{followup_id}")
def update_followup(
    followup_id: str,
    request: FollowUpUpdate,
    db: Session = Depends(get_db),
) -> dict:
    row = _get(db, followup_id)
    row.status = request.status.upper()
    row.next_action = request.next_action
    row.due_date = datetime.combine(request.due_date, time.min, tzinfo=timezone.utc) if request.due_date else None
    row.notes = request.notes
    db.commit()
    db.refresh(row)
    from backend.app.agents.audit_ledger.schemas import AuditEventCreate
    from backend.app.agents.audit_ledger.service import AuditLedgerService

    AuditLedgerService().record_event(
        AuditEventCreate(
            entity_type="CASE",
            entity_id=row.case_id,
            event_type="FOLLOW_UP_UPDATED",
            actor_type="USER",
            actor_id="reporting_user",
            source_agent="follow_up_api",
            status=row.status,
            new_value={"followup_id": row.followup_id, "status": row.status},
            workflow_stage="PHA_FOLLOW_UP",
        ),
        db,
    )
    return _payload(row)
