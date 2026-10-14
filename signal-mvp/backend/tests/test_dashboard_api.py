from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import BooleanClauseList
from sqlalchemy.sql import operators

from backend.app.database import get_db
from backend.app.canonical.query_service import _patient_deadline
from backend.app.main import app
from backend.app.models.case import Case
from backend.app.models.deadline_escalation import DeadlineEscalation
from backend.app.models.encounter import Encounter
from backend.app.models.submissions import Submission
from backend.app.models.patient import Patient
from backend.app.dashboard import service as dashboard_service


def case_row(status, final_decision, reportability_decision, jurisdiction_status, case_id=None):
    return SimpleNamespace(
        case_id=case_id or status + final_decision + reportability_decision + jurisdiction_status,
        status=status,
        final_decision=final_decision,
        reportability_decision=reportability_decision,
        jurisdiction_status=jurisdiction_status,
    )


class FakeQuery:
    def __init__(self, rows, entity, db):
        self.rows = list(rows)
        self.entity = entity
        self.db = db
        self.is_distinct = False

    def matches(self, row, expression):
        if isinstance(expression, BooleanClauseList) and expression.operator is operators.or_:
            return any(self.matches(row, clause) for clause in expression.clauses)
        if getattr(expression, "operator", None) is operators.inv:
            return not self.matches(row, expression.element)
        if expression.operator is operators.not_in_op:
            return str(getattr(row, "case_id", "")) not in self.db.reported_case_ids
        if expression.operator is operators.in_op and "SELECT" in str(expression.right).upper():
            return str(getattr(row, "case_id", "")) in self.db.reported_case_ids
        left = expression.left
        while not (getattr(left, "key", None) or getattr(left, "name", None)):
            left = getattr(left, "element", None)
            if left is None:
                raise AssertionError(f"Unsupported filter expression: {expression}")
        key = getattr(left, "key", None) or getattr(left, "name")
        if expression.operator is operators.in_op:
            right = expression.right
            values = getattr(right, "value", None)
            if values is None:
                values = self.db.reported_case_ids
            return getattr(row, key) in values
        if expression.operator is operators.eq:
            return getattr(row, key) == getattr(expression.right, "value", None)
        raise AssertionError(f"Unsupported filter expression: {expression}")

    def filter(self, *expressions):
        for expression in expressions:
            self.rows = [row for row in self.rows if self.matches(row, expression)]
        return self

    def distinct(self):
        self.is_distinct = True
        return self

    def order_by(self, *expressions):
        expression = expressions[0]
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

    def join(self, subquery, _onclause):
        self.rows = [row for row in self.rows if str(getattr(row, self.entity.key)) in subquery.values]
        return self

    def subquery(self):
        values = {str(getattr(row, self.entity.key)) for row in self.rows}
        return SimpleNamespace(values=values, c=SimpleNamespace(case_id=Case.case_id))


class FakeSession:
    def __init__(
        self,
        cases=None,
        encounters=None,
        submissions=None,
        deadlines=None,
    ):
        self.rows = {
            Case: list(cases or []),
            Encounter: list(encounters or []),
            Submission: list(submissions or []),
            DeadlineEscalation: list(deadlines or []),
            Patient: [],
        }
        self.reported_case_ids = {
            str(row.case_id) for row in self.rows[Submission]
            if getattr(row, "status", "SUBMITTED") in {"SUBMITTED", "ACKNOWLEDGED"}
        }

    def query(self, entity):
        if isinstance(entity, type):
            model = entity
        else:
            selected = entity
            while getattr(selected, "table", None) is None:
                selected = getattr(selected, "element", None)
                if selected is None:
                    raise AssertionError(f"Unsupported selected entity: {entity}")
            model = {
                "cases": Case,
                "submissions": Submission,
                "deadline_escalations": DeadlineEscalation,
                "patients": Patient,
                "encounters": Encounter,
            }[selected.table.name]
        return FakeQuery(self.rows[model], entity, self)


def client_for(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_dashboard_summary_aggregates_database_records():
    cases = [
        case_row("REPORT", "REPORT", "PROCEED_TO_RULES", "RESOLVED", "case-1"),
        case_row("NEEDS_REVIEW", "NEEDS_REVIEW", "NEEDS_REVIEW", "NEEDS_REVIEW", "case-2"),
        case_row("HOLD", "HOLD", "HOLD", "RESOLVED", "case-3"),
    ]
    db = FakeSession(
        cases=cases,
        submissions=[
            SimpleNamespace(case_id="case-1", status="SUBMITTED"),
            SimpleNamespace(case_id="case-1", status="SUBMITTED"),
            SimpleNamespace(case_id="case-2", status="PENDING"),
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
        "upcoming_deadlines": 2,
        "total_patients": 0,
        "active_cases": 1,
        "patients_due_today": 0,
        "reported_cases": 1,
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
        "upcoming_deadlines": 0,
        "total_patients": 0,
        "active_cases": 0,
        "patients_due_today": 0,
        "reported_cases": 0,
    }


def test_dashboard_patient_deadline_uses_persisted_case_rule_id():
    patient_id = uuid4()
    patient = SimpleNamespace(
        patient_id=patient_id,
        source_patient_id="patient-1",
        first_name="Jordan",
        last_name="Smith",
        date_of_birth=None,
        sex=None,
        address_line=None,
        city=None,
        county=None,
        state="TX",
        postal_code=None,
        source="test",
        source_resource="Patient",
    )
    case = SimpleNamespace(
        disease="measles",
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        rule_id="MEASLES-TX",
        deadline=None,
        clinical_evidence={"event_time": "2026-01-15T12:00:00+00:00"},
        laboratory_evidence={},
    )

    deadline, reason = _patient_deadline(
        patient=patient,
        conditions=[],
        lab_results=[],
        candidate=None,
        case=case,
    )

    assert reason is None
    assert deadline["rule_id"] == "MEASLES-TX"
    assert deadline["status"] != "NO_RULE"


def test_legacy_work_items_route_is_not_part_of_dashboard_api():
    # The current dashboard uses /summary, /reporting-status, /activity,
    # /deadlines, and /canonical/patients. There is no work-items API contract.
    assert TestClient(app).get("/api/dashboard/work-items").status_code == 404


def test_dashboard_measles_priority_uses_canonical_eligibility_and_returns_only_table_fields(monkeypatch):
    calls = {}

    def canonical_worklist(db, **kwargs):
        calls.update(kwargs)
        return {
            "total": 58,
            "items": [{
                "patient_id": "patient-1",
                "first_name": "Ada",
                "last_name": "Lovelace",
                "condition": "Measles",
                "jurisdiction": "TX",
                "deadline": {"deadline": "2026-10-10T12:00:00+00:00", "urgency": "HIGH"},
                "conditions": [{"display": "not exposed by the priority endpoint"}],
            }],
        }

    monkeypatch.setattr(dashboard_service, "list_patients", canonical_worklist)
    client = client_for(FakeSession())
    try:
        response = client.get("/api/dashboard/measles-priority")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert calls == {"page": 1, "page_size": 5, "condition": "measles", "include_facilities": False}
    assert response.json() == {
        "total": 58,
        "items": [{
            "patient_id": "patient-1",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "condition": "Measles",
            "jurisdiction": "TX",
            "deadline": {"deadline": "2026-10-10T12:00:00+00:00", "urgency": "HIGH"},
        }],
    }


def test_existing_health_endpoint_still_works():
    client = client_for(FakeSession())
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
