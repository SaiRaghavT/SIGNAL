from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .query_service import get_case_detail, list_cases
from .reporting_service import update_case_report
from .schemas import CaseDetailResponse, CaseListResponse, CaseReportUpdateRequest, CaseReportUpdateResponse


router = APIRouter(prefix="/api/cases", tags=["Cases"])


@router.patch("/{case_id}/report-fields", response_model=CaseReportUpdateResponse)
def patch_case_report_fields(
    case_id: UUID,
    request: CaseReportUpdateRequest,
    db: Session = Depends(get_db),
) -> CaseReportUpdateResponse:
    try:
        return update_case_report(db, case_id, request)
    except ValueError as exc:
        status_code = 404 if str(exc).startswith("Case not found:") else 422
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc


@router.get("/{case_id}", response_model=CaseDetailResponse)
def get_case(
    case_id: UUID,
    db: Session = Depends(get_db),
) -> CaseDetailResponse:
    case = get_case_detail(db, case_id)
    if case is None:
        raise HTTPException(status_code=404, detail=f"Case not found: {case_id}")
    return case


@router.get("", response_model=CaseListResponse)
def get_cases(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    disease: str | None = Query(default=None),
    jurisdiction: str | None = Query(default=None),
    patient_id: str | None = Query(default=None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
) -> CaseListResponse:
    return list_cases(
        db,
        page=page,
        page_size=page_size,
        status=status,
        disease=disease,
        jurisdiction=jurisdiction,
        patient_id=patient_id,
    )
