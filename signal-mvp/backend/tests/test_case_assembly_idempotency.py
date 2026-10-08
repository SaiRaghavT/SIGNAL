from uuid import uuid4

from backend.app.case.assembler import assemble_case
from backend.app.case.models import CaseAssemblyInput
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case


class FakeQuery:
    def __init__(self, db, model):
        self.db = db
        self.model = model
        self.expressions = []

    def filter(self, *expressions):
        self.expressions.extend(expressions)
        return self

    def first(self):
        rows = self.db.cases if self.model is Case else []
        for expression in self.expressions:
            key = expression.left.key
            expected = expression.right.value
            rows = [row for row in rows if getattr(row, key) == expected]
        return rows[0] if rows else None


class FakeSession:
    def __init__(self):
        self.cases = []
        self.commit_count = 0

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, case):
        self.cases.append(case)

    def flush(self):
        self.cases[-1].case_id = uuid4()

    def commit(self):
        self.commit_count += 1

    def refresh(self, _case):
        return None


def test_reprocessing_candidate_returns_existing_case_without_creating_another():
    db = FakeSession()
    request = CaseAssemblyInput(
        candidate_id="candidate-stable-event-1",
        patient={"patient_id": "patient-1"},
        facility={"name": "Clinic"},
        provider={"name": "Provider", "phone": "555-0100", "address": "Clinic"},
        disease="measles",
        clinical_evidence={"encounter_id": "encounter-1"},
        laboratory_evidence=[{"test_name": "Measles IgM", "result": "positive"}],
        ai_evidence={},
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        reportability_decision="REPORT",
        reportability_evidence_status="LAB_POSITIVE",
        final_decision="REPORT",
        rule_id="MEASLES-003",
    )

    first = assemble_case(request, db)
    second = assemble_case(request, db)

    assert first.case_id == second.case_id
    assert len(db.cases) == 1
    assert db.commit_count == 1
    assert db.cases[0].submission_mode is None
