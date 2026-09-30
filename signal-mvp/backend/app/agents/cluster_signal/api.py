from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.app.agents.cluster_signal.agent import run_cluster_signal


router = APIRouter(
    prefix="/api/clusters",
    tags=["Cluster SIGNAL"],
)


class CaseLocation(BaseModel):
    state: str | None = None
    county: str | None = None
    postal_code: str | None = None
    city: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class ClusterCase(BaseModel):
    case_id: str
    disease_id: str
    onset_date: date
    patient_location: CaseLocation | None = None
    facility_id: str | None = None
    facility_location: CaseLocation | None = None
    setting_id: str | None = None
    age_years: int | None = Field(default=None, ge=0, le=125)
    sex: str | None = None


class ClusterEvent(BaseModel):
    patient_id: str
    event_date: date | None = None
    onset_date: date | None = None
    county: str | None = None
    zip_code: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    facility_id: str | None = None
    case_status: str | None = None
    lab_result: str | None = None


class ClusterAnalysisRequest(BaseModel):
    disease: str | None = None
    events: list[ClusterEvent] = Field(default_factory=list)
    # Keep the earlier request shape available for callers already using it.
    cases: list[ClusterCase] | None = None
    as_of_date: date = Field(default_factory=date.today)
    window_days: int = Field(default=7, ge=1, le=90)
    baseline_days: int = Field(default=90, ge=7, le=730)
    minimum_cases: int = Field(default=5, ge=2)
    anomaly_threshold: float = Field(default=3.0, gt=0)


@router.post("/analyze")
def analyze_cluster_signals(
    request: ClusterAnalysisRequest,
) -> dict[str, Any]:
    """Analyze a batch of cases and return potential cluster alerts."""

    if request.events:
        if not request.disease:
            raise HTTPException(
                status_code=422,
                detail="disease is required when events are provided.",
            )
        if any(not (event.onset_date or event.event_date) for event in request.events):
            raise HTTPException(
                status_code=422,
                detail="Each event must include onset_date or event_date.",
            )

        cases = [
            {
                "case_id": event.patient_id,
                "disease_id": request.disease,
                "onset_date": event.onset_date or event.event_date,
                "patient_location": {
                    "county": event.county,
                    "postal_code": event.zip_code,
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                },
                "facility_id": event.facility_id,
                "case_status": event.case_status,
                "lab_result": event.lab_result,
            }
            for event in request.events
        ]
    else:
        cases = [case.model_dump() for case in (request.cases or [])]

    return run_cluster_signal(
        cases,
        as_of_date=request.as_of_date,
        window_days=request.window_days,
        baseline_days=request.baseline_days,
        minimum_cases=request.minimum_cases,
        anomaly_threshold=request.anomaly_threshold,
    )
