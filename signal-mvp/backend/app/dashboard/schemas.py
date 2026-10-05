from pydantic import BaseModel


class DashboardSummaryResponse(BaseModel):
    cases: int
    reportable_cases: int
    needs_review: int
    submitted_cases: int
    follow_up_cases: int
    upcoming_deadlines: int
