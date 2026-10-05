from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import BooleanClauseList
from sqlalchemy.sql import operators

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.encounter import Encounter
from backend.app.models.follow_up import FollowUp
from backend.app.models.submissions import Submission


def case_row(status, final_decision, reportability_decision, jurisdiction_status):
    return SimpleNamespace(
        case_id=status + final_decision + reportability_decision + jurisdiction_status,
        status=status,
        final_decision=final_decision,
        reportability_decision=reportability_decision,
        jurisdiction_status=jurisdiction_status,
    )


class FakeQuery:
    def __init__(self, rows, entity):
        self.rows = list(rows)
        self.entity = entity
        self.is_distinct = False

    @staticmethod
    def matches(row, expression):
        if isinstance(expression, BooleanClauseList) and expression.operator is operators.or_:
            return any(FakeQuery.matches(row, clause) for clause in expression.clauses)
        if expression.operator is operators.eq:
            return getattr(row, expression.left.key) == expression.right.value
        raise AssertionError(f"Unsupported filter expression: {expression}")

    def filter(self, *expressions):
        for expression in expressions:
            self.rows = [row for row in self.rows if self.matches(row, expression)]
        return self

    def distinct(self):
        self.is_distinct = True
        return self

    def order_by(self, expression):
        column = expression
        while not getattr(column, "key", None):
            column = getattr(column, "element", None)
            if column is None:
                return self

        self.rows.sort(
            key=lambda row: (
                getattr(row, column.key) is not None,
                getattr(row, column.key),
            ),
            reverse=True,
        )
        return self

    def all(self):
        return self.rows

    def first(self):
        return self.rows[0] if self.rows else None

    def count(self):
        if not self.is_distinct:
            return len(self.rows)
        key = self.entity.key
        return len({getattr(row, key) for row in self.rows})


class FakeSession:
    def __init__(
        self,
        cases=None,
        encounters=None,
        submissions=None,
        follow_ups=None,
        deadlines=None,
    ):
        self.rows = {
            Case: list(cases or []),
            Encounter: list(encounters or []),
            Submission: list(submissions or []),
            FollowUp: list(follow_ups or []),
            DeadlineEscalation: list(deadlines or []),
        }

    def query(self, entity):
        model = entity if isinstance(entity, type) else entity.class_
        return FakeQuery(self.rows[model], entity)


def client_for(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_dashboard_summary_aggregates_database_records():
    cases = [
        case_row("REPORT", "REPORT", "PROCEED_TO_RULES", "RESOLVED"),
        case_row("NEEDS_REVIEW", "NEEDS_REVIEW", "NEEDS_REVIEW", "NEEDS_REVIEW"),
        case_row("HOLD", "HOLD", "HOLD", "RESOLVED"),
    ]
    db = FakeSession(
        cases=cases,
        submissions=[
            SimpleNamespace(case_id="case-1"),
            SimpleNamespace(case_id="case-1"),
            SimpleNamespace(case_id="case-2"),
        ],
        follow_ups=[
            SimpleNamespace(case_id="case-2"),
            SimpleNamespace(case_id="case-2"),
        ],
        deadlines=[
            SimpleNamespace(escalation_id="esc-1", status="UPCOMING"),
            SimpleNamespace(escalation_id="esc-2", status="UPCOMING"),
            SimpleNamespace(escalation_id="esc-3", status="OVERDUE"),
        ],
    )
    client = client_for(db)
    try:
        response = client.get("/api/dashboard/summary")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {
        "cases": 3,
        "reportable_cases": 1,
        "needs_review": 1,
        "submitted_cases": 2,
        "follow_up_cases": 1,
        "upcoming_deadlines": 2,
    }


def test_dashboard_summary_returns_zero_for_empty_database():
    client = client_for(FakeSession())
    try:
        response = client.get("/api/dashboard/summary")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {
        "cases": 0,
        "reportable_cases": 0,
        "needs_review": 0,
        "submitted_cases": 0,
        "follow_up_cases": 0,
        "upcoming_deadlines": 0,
    }


def test_dashboard_work_items_include_the_latest_patient_encounter():
    patient_with_encounters = uuid4()
    patient_without_encounter = uuid4()
    earlier = datetime(2026, 1, 5, tzinfo=timezone.utc)
    latest = datetime(2026, 2, 10, tzinfo=timezone.utc)
    cases = [
        SimpleNamespace(
            case_id=uuid4(),
            candidate_id="candidate-1",
            patient={
                "patient_id": str(patient_with_encounters),
                "first_name": "Ada",
                "last_name": "Lovelace",
            },
            disease="measles",
            status="NEEDS_REVIEW",
            reportability_decision="NEEDS_REVIEW",
            final_decision="NEEDS_REVIEW",
            updated_at=latest,
        ),
        SimpleNamespace(
            case_id=uuid4(),
            candidate_id="candidate-2",
            patient={"patient_id": str(patient_without_encounter)},
            disease="measles",
            status="HOLD",
            reportability_decision="HOLD",
            final_decision="HOLD",
            updated_at=earlier,
        ),
    ]
    encounters = [
        SimpleNamespace(patient_id=patient_with_encounters, start_time=earlier),
        SimpleNamespace(patient_id=patient_with_encounters, start_time=latest),
    ]
    client = client_for(FakeSession(cases=cases, encounters=encounters))
    try:
        response = client.get("/api/dashboard/work-items")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["patient_id"] == str(patient_with_encounters)
    assert items[0]["patient_name"] == "Ada Lovelace"
    assert datetime.fromisoformat(
        items[0]["last_encounter"].replace("Z", "+00:00")
    ) == latest
    assert items[1]["patient_id"] == str(patient_without_encounter)
    assert items[1]["last_encounter"] is None


def test_existing_health_endpoint_still_works():
    client = client_for(FakeSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
