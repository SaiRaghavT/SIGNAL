from types import SimpleNamespace

from backend.app.agents.reportability_workflow.service import (
    _build_laboratory_evidence,
    _calculate_laboratory_decision,
)
from backend.app.smart_field_population.mapper import _build_derived_fields


def test_candidate_lab_signal_uses_nested_source_id_to_load_canonical_result():
    canonical_lab = {
        "lab_result_id": "lab-result-uuid",
        "report_status": "final",
        "conclusion": "Detected",
        "test": {"display": "Measles PCR"},
    }
    request = SimpleNamespace(
        laboratory_evidence=[
            {
                "trigger_type": "LAB_RESULT",
                "evidence": {
                    "source_id": "lab-result-uuid",
                    "source_type": "DiagnosticReport",
                },
            }
        ]
    )

    evidence = _build_laboratory_evidence(
        request,
        {"lab_results": [canonical_lab]},
    )

    assert evidence[0]["report_status"] == "final"
    assert evidence[0]["conclusion"] == "Detected"
    assert _calculate_laboratory_decision(evidence) == "POSITIVE"


def test_smart_field_mapper_reads_nested_canonical_lab_test():
    fields = _build_derived_fields(
        {
            "laboratory_evidence": [
                {
                    "test": {
                        "code": "5195-3",
                        "display": "Measles virus IgM Ab",
                    },
                    "conclusion": "Detected",
                }
            ]
        }
    )

    assert fields["laboratory.igm"] == "Positive"
