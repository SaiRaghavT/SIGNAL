from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.database import get_db

from .schemas import DashboardSummaryResponse
from .service import get_dashboard_summary


router = APIRouter(prefix="/api/dashboard", tags=["Dashboard"])


@router.get("/summary", response_model=DashboardSummaryResponse)
def dashboard_summary(
    db: Session = Depends(get_db),
) -> DashboardSummaryResponse:
    return get_dashboard_summary(db)
