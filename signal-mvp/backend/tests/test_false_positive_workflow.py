from backend.app.decision.models import ReconciliationInput
from backend.app.decision.reconciler import reconcile_decisions
from backend.app.detection.api import _add_synthetic_measles_false_positive_candidate
from backend.app.reportability.evaluator import evaluate_reportability
from backend.app.reportability.models import ReportabilityInput


def test_synthetic_measles_false_positive_is_not_reportable():
    evidence = {
        "candidate_evidence": [{"scenario_id": "measles-false-positive"}],
    }
    assessment = evaluate_reportability(ReportabilityInput(
        candidate_id="synthetic-fp",
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        disease="measles",
        clinical_evidence=evidence,
        laboratory_evidence=[{
            "test": "Measles virus PCR",
            "status": "final",
            "result": "Not detected",
        }],
        ai_evidence={"condition": "measles", "confidence": 0.99},
    ))

    assert assessment.decision == "NOT_REPORTABLE"
    assert assessment.evidence_status == "SYNTHETIC_FALSE_POSITIVE_RULED_OUT"

    disposition = reconcile_decisions(ReconciliationInput(
        candidate_id="synthetic-fp",
        ai_decision="POSITIVE",
        ai_confidence=0.99,
        laboratory_decision="NEGATIVE",
        rule_decision="REPORT",
        jurisdiction_status="RESOLVED",
        reportability_decision=assessment.decision,
        human_review_required=True,
        conflicts=["synthetic edge case"],
    ))
    assert disposition.final_decision == "NOT_REPORTABLE"


def test_negative_measles_result_without_edge_case_tag_still_needs_review():
    assessment = evaluate_reportability(ReportabilityInput(
        candidate_id="ordinary-negative",
        jurisdiction="TX",
        jurisdiction_status="RESOLVED",
        disease="measles",
        clinical_evidence={},
        laboratory_evidence=[{"status": "final", "result": "Not detected"}],
        ai_evidence={},
    ))

    assert assessment.decision == "NEEDS_REVIEW"


def test_tagged_fhir_patient_gets_potential_measles_candidate_for_validation():
    result = {
        "candidates": [{"disease_id": "viral_exanthem"}],
        "candidate_count": 1,
        "signal_count": 1,
        "lab_signal_count": 0,
        "signals": [],
    }
    context = {
        "patient": {
            "patient_id": "synthetic-patient",
            "provenance": {"source": "synthetic_false_positive"},
        },
        "encounters": [{"encounter_id": "synthetic-encounter"}],
        "conditions": [{
            "condition_id": "cond-exanthem",
            "code": {"display": "Viral exanthem"},
        }],
    }

    assert _add_synthetic_measles_false_positive_candidate(result, context)
    candidate = result["candidates"][0]
    assert candidate["disease_id"] == "measles"
    assert candidate["confidence"] is None
    assert candidate["signals"][0]["result"] == "Not detected"
    assert result["candidate_count"] == 1
    assert len(result["candidates"]) == 1


def test_unmarked_patient_does_not_receive_synthetic_measles_candidate():
    result = {"candidates": [], "candidate_count": 0, "signal_count": 0, "signals": []}
    context = {"patient": {"provenance": {"source": "fhir"}}}

    assert not _add_synthetic_measles_false_positive_candidate(result, context)
    assert result["candidates"] == []
