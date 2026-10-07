from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    cases: int
    reportable_cases: int
    needs_review: int
    submitted_cases: int
    upcoming_deadlines: int
    total_measles_patients: int
    active_measles_cases: int
    measles_patients_due_today: int
    reported_measles_cases: int


class DashboardWorkItem(BaseModel):
    case_id: str
    candidate_id: str
    patient_id: str | None = None
    patient_name: str | None = None
    disease: str | None = None
    status: str
    reportability_decision: str
    final_decision: str | None = None
    last_encounter: datetime | None = None


class DashboardWorkItemsResponse(BaseModel):
    items: list[DashboardWorkItem] = Field(default_factory=list)
