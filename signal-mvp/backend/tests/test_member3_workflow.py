import json
from pathlib import Path

from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction

from backend.app.reportability.models import ReportabilityInput
from backend.app.reportability.evaluator import evaluate_reportability

from backend.app.rckms.decision_support import evaluate_decision_support

from backend.app.decision.models import ReconciliationInput
from backend.app.decision.reconciler import reconcile_decisions

from backend.app.case.models import CaseAssemblyInput


DATA_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "texas"
    / "measles"
    / "member3_reportability_test.json"
)


def load_candidates():
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def _candidate(candidate_id):
    return next(
        candidate
        for candidate in load_candidates()
        if candidate["candidate_id"] == candidate_id
    )


def _evaluate_candidate(candidate):
    candidate_id = candidate["candidate_id"]

    patient = candidate.get("patient", {})
    facility = candidate.get("facility", {})
    provider = candidate.get("provider", {})

    # ---------------------------------------------------------
    # 1. JURISDICTION
    # ---------------------------------------------------------
    jurisdiction_input = JurisdictionInput(
        candidate_id=candidate_id,
        patient_state=patient.get("state"),
        patient_county=patient.get("county"),
        facility_state=facility.get("state"),
        facility_county=facility.get("county"),
        disease=candidate.get("disease"),
    )

    jurisdiction_result = resolve_jurisdiction(jurisdiction_input)

    # ---------------------------------------------------------
    # 2. REPORTABILITY
    # ---------------------------------------------------------
    reportability_input = ReportabilityInput(
        candidate_id=candidate_id,
        jurisdiction=jurisdiction_result.jurisdiction,
        jurisdiction_status=jurisdiction_result.status,
        disease=candidate.get("disease"),
        clinical_evidence=candidate.get("clinical_evidence", {}),
        laboratory_evidence=candidate.get("laboratory_evidence", []),
        ai_evidence=candidate.get("ai_evidence", {}),
    )

    reportability_result = evaluate_reportability(reportability_input)

    # ---------------------------------------------------------
    # 3. RULE / DECISION SUPPORT
    # ---------------------------------------------------------
    rule_result = evaluate_decision_support(
        candidate_id=candidate_id,
        disease=candidate.get("disease"),
        laboratory_evidence=candidate.get("laboratory_evidence", []),
        clinical_evidence=candidate.get("clinical_evidence", {}),
        jurisdiction=jurisdiction_result.jurisdiction,
    )

    # ---------------------------------------------------------
    # 4. AI DECISION
    # ---------------------------------------------------------
    ai_evidence = candidate.get("ai_evidence", {})
    ai_condition = ai_evidence.get("condition")
    disease = candidate.get("disease")

    if ai_condition:
        ai_decision = (
            "POSITIVE"
            if disease
            and ai_condition.lower() == str(disease).lower()
            else "NEGATIVE"
        )
    else:
        ai_decision = None

    # ---------------------------------------------------------
    # 5. RECONCILIATION
    # ---------------------------------------------------------
    reconciliation = reconcile_decisions(
        ReconciliationInput(
            candidate_id=candidate_id,
            ai_decision=ai_decision,
            ai_confidence=ai_evidence.get("confidence"),
            laboratory_decision=None,
            rule_decision=rule_result.decision,
            jurisdiction_status=jurisdiction_result.status,
            reportability_decision=reportability_result.decision,
        )
    )

    # ---------------------------------------------------------
    # 6. CASE INPUT
    # ---------------------------------------------------------
    case_input = CaseAssemblyInput(
        candidate_id=candidate_id,
        patient=patient,
        facility=facility,
        provider=provider,
        disease=disease,
        clinical_evidence=candidate.get(
            "clinical_evidence",
            {},
        ),
        laboratory_evidence=candidate.get(
            "laboratory_evidence",
            [],
        ),
        ai_evidence=ai_evidence,
        jurisdiction=jurisdiction_result.jurisdiction,
        jurisdiction_status=jurisdiction_result.status,
        reportability_decision=reportability_result.decision,
        reportability_evidence_status=(
            reportability_result.evidence_status
        ),
        final_decision=reconciliation.final_decision,
        rule_id=rule_result.rule_id,
    )

    return {
        "candidate_id": candidate_id,
        "jurisdiction": jurisdiction_result,
        "reportability": reportability_result,
        "rule": rule_result,
        "reconciliation": reconciliation,
        "case_input": case_input,
    }


# =============================================================
# TEST 1 — HAPPY PATH
# =============================================================

def test_happy_path_reaches_report_decision():
    result = _evaluate_candidate(_candidate("CAND-001"))

    assert result["jurisdiction"].status == "RESOLVED"
    assert result["reportability"].decision == "REPORT"
    assert result["reconciliation"].final_decision == "REPORT"


# =============================================================
# TEST 2 — PENDING LAB
# =============================================================

def test_pending_lab_is_held():
    result = _evaluate_candidate(_candidate("CAND-007"))

    assert result["reportability"].evidence_status == "PENDING_LAB"
    assert result["reconciliation"].final_decision == "HOLD"


# =============================================================
# TEST 3 — JURISDICTION CONFLICT
# =============================================================

def test_jurisdiction_conflict_requires_review():
    result = _evaluate_candidate(_candidate("CAND-010"))

    assert result["jurisdiction"].status == "NEEDS_REVIEW"
    assert result["reconciliation"].final_decision == "NEEDS_REVIEW"


# =============================================================
# TEST 4 — CONFLICTING AI AND LAB
# =============================================================

def test_conflicting_lab_and_ai_requires_review():
    result = _evaluate_candidate(_candidate("CAND-008"))

    assert (
        result["reportability"].evidence_status
        == "CONFLICTING_AI_AND_LAB"
    )
    assert result["reconciliation"].final_decision == "NEEDS_REVIEW"


# =============================================================
# TEST 5 — MISSING DISEASE
# =============================================================

def test_missing_disease_is_detected():
    candidate = dict(_candidate("CAND-011"))

    result = _evaluate_candidate(candidate)

    assert candidate.get("disease") is None
    assert result["case_input"].disease is None


# =============================================================
# TEST 6 — MISSING DOB
# =============================================================

def test_missing_dob_is_preserved_for_validation():
    candidate = dict(_candidate("CAND-007"))
    candidate["patient"] = dict(candidate["patient"])
    candidate["patient"].pop("dob", None)

    result = _evaluate_candidate(candidate)

    assert "dob" not in result["case_input"].patient


# =============================================================
# TEST 7 — CONSISTENT FINAL DECISIONS
# =============================================================

def test_all_member3_candidates_have_final_decisions():
    for candidate in load_candidates():
        result = _evaluate_candidate(candidate)

        assert result["reconciliation"].final_decision in {
            "REPORT",
            "HOLD",
            "NEEDS_REVIEW",
            "REJECTED",
        }