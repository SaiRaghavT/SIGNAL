import json
from pathlib import Path

from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction

from backend.app.reportability.models import ReportabilityInput
from backend.app.reportability.evaluator import evaluate_reportability

from backend.app.case.models import CaseAssemblyInput
from backend.app.case.assembler import assemble_case

from backend.app.ecr.builder import build_ecr

from backend.app.schemas.validation import validate_ecr

from backend.app.submission.service import submit_ecr
from backend.app.rckms.decision_support import evaluate_decision_support
from backend.app.decision.models import ReconciliationInput
from backend.app.decision.reconciler import reconcile_decisions


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


def main():
    candidates = load_candidates()

    print(f"Loaded {len(candidates)} candidates")
    print("=" * 90)

    for candidate in candidates:

        candidate_id = candidate["candidate_id"]

        # ---------------------------------------------------------
        # 1. JURISDICTION
        # ---------------------------------------------------------
        patient = candidate.get("patient", {})
        facility = candidate.get("facility", {})

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
        # 2. REPORTABILITY ASSESSMENT
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

        reportability_result = evaluate_reportability(
            reportability_input
        )

        # ---------------------------------------------------------
        # 3. CASE ASSEMBLY
        # ---------------------------------------------------------
        case_input = CaseAssemblyInput(
            candidate_id=candidate_id,
            patient=patient,
            facility=facility,
            provider=candidate.get("provider", {}),
            disease=candidate.get("disease"),
            clinical_evidence=candidate.get(
                "clinical_evidence", {}
            ),
            laboratory_evidence=candidate.get(
                "laboratory_evidence", []
            ),
            ai_evidence=candidate.get(
                "ai_evidence", {}
            ),
            jurisdiction=jurisdiction_result.jurisdiction,
            jurisdiction_status=jurisdiction_result.status,
            reportability_decision=reportability_result.decision,
            reportability_evidence_status=(
                reportability_result.evidence_status
            ),
        )

        rule_result = evaluate_decision_support(
            candidate_id=candidate_id,
            disease=candidate.get("disease"),
            laboratory_evidence=candidate.get("laboratory_evidence", []),
            clinical_evidence=candidate.get("clinical_evidence", {}),
        )
        ai_condition = candidate.get("ai_evidence", {}).get("condition")
        reconciliation = reconcile_decisions(
            ReconciliationInput(
                candidate_id=candidate_id,
                ai_decision=(
                    "POSITIVE"
                    if ai_condition
                    and ai_condition.lower()
                    == str(candidate.get("disease", "")).lower()
                    and candidate.get("disease")
                    else "NEGATIVE"
                    if candidate.get("ai_evidence", {}).get("condition")
                    else None
                ),
                ai_confidence=candidate.get("ai_evidence", {}).get("confidence"),
                laboratory_decision=None,
                rule_decision=rule_result.decision,
                jurisdiction_status=jurisdiction_result.status,
                reportability_decision=reportability_result.decision,
            )
        )
        case_input.final_decision = reconciliation.final_decision
        case_input.rule_id = rule_result.rule_id

        signal_case = assemble_case(case_input)

        # ---------------------------------------------------------
        # 4. ECR BUILD
        # ---------------------------------------------------------
        ecr = build_ecr(signal_case)

        # ---------------------------------------------------------
        # 5. ECR VALIDATION
        # ---------------------------------------------------------
        validation = validate_ecr(ecr)

        # ---------------------------------------------------------
        # 6. MOCK PHA SUBMISSION
        # ---------------------------------------------------------
        submission = submit_ecr(
            ecr,
            validation,
        )

        # ---------------------------------------------------------
        # 7. SUMMARY
        # ---------------------------------------------------------
        print(
            f"{candidate_id} | "
            f"Jurisdiction: {jurisdiction_result.status} | "
            f"Reportability: {reportability_result.decision} | "
            f"Case: {signal_case.status} | "
            f"ECR: {ecr.status} | "
            f"Validation: "
            f"{'VALID' if validation.valid else 'INVALID'} | "
            f"Submission: {submission.status}"
        )

    print("=" * 90)
    print("Member 3 workflow test completed.")


if __name__ == "__main__":
    main()


def _process_candidate(candidate):
    from backend.app.main import CandidateProcessRequest, process_candidate

    return process_candidate(CandidateProcessRequest(**candidate))


def _candidates_by_id():
    return {
        candidate["candidate_id"]: candidate
        for candidate in load_candidates()
    }


def test_happy_path_submits():
    result = _process_candidate(_candidates_by_id()["CAND-001"])
    assert result["workflow_status"] == "REPORT"
    assert result["case"]["status"] == "REPORT"
    assert result["ecr"]["status"] == "REPORT"
    assert result["validation"]["valid"] is True
    assert result["submission"]["status"] == "SUBMITTED"


def test_pending_lab_is_held_and_not_submitted():
    result = _process_candidate(_candidates_by_id()["CAND-007"])
    assert result["workflow_status"] == "HOLD"
    assert result["reportability"]["evidence_status"] == "PENDING_LAB"
    assert result["case"]["status"] == "HOLD"
    assert result["ecr"]["status"] == "HOLD"
    assert result["submission"]["status"] == "BLOCKED"


def test_jurisdiction_conflict_requires_review():
    result = _process_candidate(_candidates_by_id()["CAND-010"])
    assert result["jurisdiction"]["status"] == "NEEDS_REVIEW"
    assert result["workflow_status"] == "NEEDS_REVIEW"
    assert result["case"]["status"] == "NEEDS_REVIEW"
    assert result["ecr"]["status"] == "NEEDS_REVIEW"
    assert result["submission"]["status"] == "REJECTED"


def test_conflicting_lab_and_ai_evidence_requires_review():
    result = _process_candidate(_candidates_by_id()["CAND-008"])
    assert result["reportability"]["evidence_status"] == "CONFLICTING_AI_AND_LAB"
    assert result["workflow_status"] == "NEEDS_REVIEW"
    assert result["reconciliation"]["final_decision"] == "NEEDS_REVIEW"
    assert result["submission"]["status"] == "BLOCKED"


def test_missing_disease_fails_validation():
    result = _process_candidate(_candidates_by_id()["CAND-011"])
    assert result["workflow_status"] == "NEEDS_REVIEW"
    assert result["validation"]["valid"] is False
    assert "Disease information is missing." in result["validation"]["errors"]
    assert result["submission"]["status"] == "REJECTED"


def test_missing_required_dob_fails_validation():
    candidate = dict(_candidates_by_id()["CAND-007"])
    candidate["patient"] = dict(candidate["patient"])
    candidate["patient"].pop("dob", None)

    result = _process_candidate(candidate)
    assert result["workflow_status"] == "HOLD"
    assert result["validation"]["valid"] is False
    assert "Patient date of birth is missing." in result["validation"]["errors"]
    assert result["submission"]["status"] == "REJECTED"


def test_all_member3_candidates_have_consistent_final_statuses():
    for candidate in load_candidates():
        result = _process_candidate(candidate)
        decision = result["reconciliation"]["final_decision"]
        assert result["workflow_status"] == decision
        assert result["case"]["status"] == decision
        assert result["ecr"]["status"] == decision