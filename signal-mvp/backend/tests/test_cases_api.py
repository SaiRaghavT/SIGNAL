from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.sql.elements import UnaryExpression

from backend.app.database import get_db
from backend.app.main import app
from backend.app.models.case import Case


def make_case(*, status="REPORT", disease="measles", jurisdiction="TX", updated_at=None):
    now = updated_at or datetime.now(timezone.utc)
    return SimpleNamespace(
        case_id=uuid4(),
        candidate_id=f"candidate-{uuid4().hex[:8]}",
        disease=disease,
        jurisdiction=jurisdiction,
        status=status,
        reportability_decision="PROCEED_TO_RULES",
        final_decision=status,
        rule_id="RULE-1",
        created_at=now - timedelta(days=1),
        updated_at=now,
        warnings=["sample warning"],
        jurisdiction_status="RESOLVED",
        reportability_evidence_status="LAB_POSITIVE",
        patient={"sensitive": "patient data"},
        provider={"sensitive": "provider data"},
        facility={"sensitive": "facility data"},
        clinical_evidence={"sensitive": "clinical data"},
        laboratory_evidence=[{"sensitive": "lab data"}],
        ai_evidence={"sensitive": "ai data"},
    )


class FakeQuery:
    def __init__(self, rows):
        self.rows = list(rows)
        self._offset = 0
        self._limit = None

    def filter(self, *expressions):
        for expression in expressions:
            column = expression.left.key
            expected = expression.right.value
            self.rows = [row for row in self.rows if getattr(row, column) == expected]
        return self

    def count(self):
        return len(self.rows)

    def order_by(self, expression):
        column = expression.element.key if isinstance(expression, UnaryExpression) else expression.key
        reverse = isinstance(expression, UnaryExpression)
        self.rows.sort(key=lambda row: getattr(row, column), reverse=reverse)
        return self

    def offset(self, value):
        self._offset = value
        return self

    def limit(self, value):
        self._limit = value
        return self

    def all(self):
        end = None if self._limit is None else self._offset + self._limit
        return self.rows[self._offset:end]

    def first(self):
        return self.rows[0] if self.rows else None


class FakeSession:
    def __init__(self, cases):
        self.cases = cases

    def query(self, model):
        return FakeQuery(self.cases if model is Case else [])


def client_for(cases):
    def override_get_db():
        yield FakeSession(cases)

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_get_cases_returns_persisted_case_summaries_without_sensitive_json():
    case = make_case()
    client = client_for([case])
    try:
        response = client.get("/api/cases")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["case_id"] == str(case.case_id)
    assert body["items"][0]["disease"] == "measles"
    for forbidden in ("patient", "provider", "facility", "clinical_evidence", "laboratory_evidence", "ai_evidence"):
        assert forbidden not in body["items"][0]


def test_pagination_and_page_size_are_respected():
    cases = [make_case(updated_at=datetime(2026, 1, day, tzinfo=timezone.utc)) for day in range(1, 6)]
    client = client_for(cases)
    try:
        response = client.get("/api/cases?page=2&page_size=2")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["total"] == 5
    assert response.json()["page"] == 2
    assert response.json()["page_size"] == 2
    assert len(response.json()["items"]) == 2


def test_status_disease_jurisdiction_and_combined_filters():
    cases = [
        make_case(status="REPORT", disease="measles", jurisdiction="TX"),
        make_case(status="HOLD", disease="measles", jurisdiction="TX"),
        make_case(status="REPORT", disease="mumps", jurisdiction="TX"),
        make_case(status="REPORT", disease="measles", jurisdiction="CA"),
    ]
    client = client_for(cases)
    try:
        status = client.get("/api/cases?status=HOLD").json()
        disease = client.get("/api/cases?disease=mumps").json()
        jurisdiction = client.get("/api/cases?jurisdiction=CA").json()
        combined = client.get("/api/cases?status=REPORT&disease=measles&jurisdiction=TX").json()
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert [item["status"] for item in status["items"]] == ["HOLD"]
    assert [item["disease"] for item in disease["items"]] == ["mumps"]
    assert [item["jurisdiction"] for item in jurisdiction["items"]] == ["CA"]
    assert len(combined["items"]) == 1
    assert combined["items"][0]["status"] == "REPORT"
    assert combined["items"][0]["disease"] == "measles"
    assert combined["items"][0]["jurisdiction"] == "TX"


def test_cases_are_ordered_by_updated_at_descending():
    older = make_case(updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
    newer = make_case(updated_at=datetime(2026, 2, 1, tzinfo=timezone.utc))
    client = client_for([older, newer])
    try:
        response = client.get("/api/cases")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert [item["case_id"] for item in response.json()["items"]] == [
        str(newer.case_id),
        str(older.case_id),
    ]


def test_empty_results_return_successful_empty_page():
    client = client_for([])
    try:
        response = client.get("/api/cases")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0, "page": 1, "page_size": 20}


def test_invalid_pagination_is_rejected():
    client = client_for([])
    try:
        low_page = client.get("/api/cases?page=0")
        excessive_size = client.get("/api/cases?page_size=101")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert low_page.status_code == 422
    assert excessive_size.status_code == 422


def test_existing_health_endpoint_remains_registered():
    client = client_for([])
    try:
        response = client.get("/health")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_case_detail_returns_persisted_record_fields():
    case = make_case()
    client = client_for([case])
    try:
        response = client.get(f"/api/cases/{case.case_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    body = response.json()
    assert body["case_id"] == str(case.case_id)
    assert body["status"] == case.status
    assert body["disease"] == case.disease
    assert body["jurisdiction"] == case.jurisdiction
    assert body["reportability_decision"] == case.reportability_decision
    assert body["final_decision"] == case.final_decision
    assert body["rule_id"] == case.rule_id
    assert body["patient"] == case.patient
    assert body["facility"] == case.facility
    assert body["provider"] == case.provider
    assert body["clinical_evidence"] == case.clinical_evidence
    assert body["laboratory_evidence"] == case.laboratory_evidence
    assert body["ai_evidence"] == case.ai_evidence
    assert datetime.fromisoformat(body["created_at"].replace("Z", "+00:00")) == case.created_at
    assert datetime.fromisoformat(body["updated_at"].replace("Z", "+00:00")) == case.updated_at


def test_case_detail_unknown_valid_uuid_returns_404():
    missing_id = uuid4()
    client = client_for([])
    try:
        response = client.get(f"/api/cases/{missing_id}")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 404


def test_existing_case_list_and_journey_routes_still_work():
    case = make_case()
    client = client_for([case])
    try:
        list_response = client.get("/api/cases")
        journey_response = client.get(f"/api/workflow/cases/{case.case_id}/journey")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert list_response.status_code == 200
    assert len(list_response.json()["items"]) == 1
    assert journey_response.status_code == 200
    assert len(journey_response.json()["journey"]) == 9
