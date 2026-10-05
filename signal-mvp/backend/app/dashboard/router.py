from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import DashboardSummaryResponse
from .service import (
    get_dashboard_activity,
    get_dashboard_deadlines,
    get_dashboard_summary,
    get_reporting_status,
)


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    return get_dashboard_summary(db)


@router.get("/activity")
def dashboard_activity(db: Session = Depends(get_db)) -> dict:
    return get_dashboard_activity(db)


@router.get("/deadlines")
def dashboard_deadlines(db: Session = Depends(get_db)) -> dict:
    return get_dashboard_deadlines(db)


@router.get("/analytics")
def dashboard_analytics(db: Session = Depends(get_db)) -> dict:
    return get_dashboard_summary(db).model_dump()


@router.get("/reporting-status")
def dashboard_reporting_status(db: Session = Depends(get_db)) -> dict:
    return get_reporting_status(db)


@router.get("/quality")
def dashboard_quality(db: Session = Depends(get_db)) -> dict:
    return get_reporting_status(db)["quality"]


@router.get("/submissions")
def dashboard_submissions(db: Session = Depends(get_db)) -> dict:
    return get_reporting_status(db)["submissions"]


@router.get("/conditions")
def dashboard_conditions(db: Session = Depends(get_db)) -> dict:
    return get_reporting_status(db)["conditions"]


@router.get("/jurisdictions")
def dashboard_jurisdictions(db: Session = Depends(get_db)) -> dict:
    return get_reporting_status(db)["jurisdictions"]
