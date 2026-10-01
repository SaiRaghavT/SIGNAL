from typing import Any

from backend.app.case.assembler import assemble_case
from backend.app.case.models import CaseAssemblyInput
from backend.app.decision.models import ReconciliationInput
from backend.app.decision.reconciler import reconcile_decisions
from backend.app.ecr.builder import build_ecr
from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction
from backend.app.rckms.decision_support import evaluate_decision_support
from backend.app.reportability.evaluator import evaluate_reportability
from backend.app.reportability.models import ReportabilityInput
from backend.app.schemas.validation import validate_ecr
from backend.app.smart_field_population.mapper import populate_report_fields
from backend.app.submission.service import submit_ecr
from sqlalchemy.orm import Session

from .schemas import CandidateProcessRequest


def process_candidate(
    request: CandidateProcessRequest,
    db: Session,
) -> dict[str, Any]:
    """Run jurisdiction, evidence, rules, review, and eCR processing."""

    patient = request.patient
    facility = request.facility
    provider = request.provider
    clinical_evidence = request.clinical_evidence
    laboratory_evidence = request.laboratory_evidence
    ai_evidence = request.ai_evidence

    patient_state = request.patient_state or patient.get("state")
    patient_county = request.patient_county or patient.get("county")
    facility_state = request.facility_state or facility.get("state")
    facility_county = request.facility_county or facility.get("county")

    jurisdiction = resolve_jurisdiction(
        JurisdictionInput(
            candidate_id=request.candidate_id,
            patient_state=patient_state,
            patient_county=patient_county,
            facility_state=facility_state,
            facility_county=facility_county,
            disease=request.disease,
        )
    )

    reportability = evaluate_reportability(
        ReportabilityInput(
            candidate_id=request.candidate_id,
            jurisdiction=jurisdiction.jurisdiction,
            jurisdiction_status=jurisdiction.status,
            disease=request.disease,
            clinical_evidence=clinical_evidence,
            laboratory_evidence=laboratory_evidence,
            ai_evidence=ai_evidence,
        )
    )

    rule_result = evaluate_decision_support(
    candidate_id=request.candidate_id,
    disease=request.disease,
    jurisdiction=jurisdiction.jurisdiction,
    laboratory_evidence=laboratory_evidence,
    clinical_evidence=clinical_evidence,
)
    ai_condition = ai_evidence.get("condition")
    ai_decision = None
    if ai_condition and request.disease:
        ai_decision = (
            "POSITIVE"
            if str(ai_condition).casefold() == request.disease.casefold()
            else "NEGATIVE"
        )

    lab_decisions: list[str] = []
    for lab in laboratory_evidence:
        status = str(lab.get("status", "")).strip().upper()
        result = str(lab.get("result", "")).strip().upper()
        if status in {"PENDING", "IN_PROGRESS"} or result in {
            "PENDING",
            "IN PROGRESS",
        }:
            lab_decisions.append("PENDING")
        elif status in {"INCONCLUSIVE", "INDETERMINATE"} or result in {
            "INCONCLUSIVE",
            "INDETERMINATE",
        }:
            lab_decisions.append("INCONCLUSIVE")
        elif result in {"POSITIVE", "DETECTED", "REACTIVE"}:
            lab_decisions.append("POSITIVE")
        elif result in {"NEGATIVE", "NOT DETECTED", "NON-REACTIVE"}:
            lab_decisions.append("NEGATIVE")

    if "PENDING" in lab_decisions:
        laboratory_decision = "PENDING"
    elif "INCONCLUSIVE" in lab_decisions:
        laboratory_decision = "INCONCLUSIVE"
    elif "POSITIVE" in lab_decisions and "NEGATIVE" in lab_decisions:
        laboratory_decision = "INCONCLUSIVE"
    elif lab_decisions:
        laboratory_decision = lab_decisions[0]
    else:
        laboratory_decision = None

    reconciliation = reconcile_decisions(
        ReconciliationInput(
            candidate_id=request.candidate_id,
            ai_decision=ai_decision,
            ai_confidence=ai_evidence.get("confidence"),
            laboratory_decision=laboratory_decision,
            rule_decision=rule_result.decision,
            jurisdiction_status=jurisdiction.status,
            reportability_decision=reportability.decision,
            human_review_required=rule_result.human_review_required,
            conflicts=rule_result.conflicts,
        )
    )

    candidate_data = {
        "candidate_id": request.candidate_id,
        "disease": request.disease,
        "patient": patient,
        "provider": provider,
        "facility": facility,
        "clinical_evidence": clinical_evidence,
        "laboratory_evidence": laboratory_evidence,
        "ai_evidence": ai_evidence,
        "jurisdiction": jurisdiction.jurisdiction,
        "jurisdiction_status": jurisdiction.status,
        "reportability_decision": reportability.decision,
        "reportability_evidence_status": reportability.evidence_status,
        "reconciliation_decision": reconciliation.final_decision,
    }
    smart_fields = populate_report_fields(candidate_data)

    case = assemble_case(
    CaseAssemblyInput(
        candidate_id=request.candidate_id,
        patient=patient,
        facility=facility,
        provider=provider,
        disease=request.disease,
        clinical_evidence=clinical_evidence,
        laboratory_evidence=laboratory_evidence,
        ai_evidence=ai_evidence,
        jurisdiction=jurisdiction.jurisdiction,
        jurisdiction_status=jurisdiction.status,
        reportability_decision=reportability.decision,
        reportability_evidence_status=reportability.evidence_status,
        final_decision=reconciliation.final_decision,
        rule_id=rule_result.rule_id,
    ),
    db,
)

    ecr = build_ecr(case)
    validation = validate_ecr(ecr, smart_fields)
    submission = submit_ecr(ecr, validation)

    return {
        "candidate_id": request.candidate_id,
        "workflow_status": reconciliation.final_decision,
        "jurisdiction": {
            "value": jurisdiction.jurisdiction,
            "status": jurisdiction.status,
            "reasons": jurisdiction.reasons,
        },
        "reportability": {
            "decision": reportability.decision,
            "evidence_status": reportability.evidence_status,
            "reasons": reportability.reasons,
            "warnings": reportability.warnings,
        },
        "rule_evaluation": {
            "decision": rule_result.decision,
            "rule_id": rule_result.rule_id,
            "reasons": rule_result.reasons,
            "warnings": rule_result.warnings,
            "llm_reasoning": rule_result.llm_reasoning,
        },
        "reconciliation": {
            "final_decision": reconciliation.final_decision,
            "reasons": reconciliation.reasons,
            "warnings": reconciliation.warnings,
        },
        "smart_field_population": {
    "fields": smart_fields.fields,
    "populated_fields": smart_fields.populated_fields,
    "missing_fields": smart_fields.missing_fields,
    "sources": smart_fields.sources,
    "confidence": smart_fields.confidence,
    "warnings": smart_fields.warnings,
},
        "case": {
            "case_id": case.case_id,
            "status": case.status,
            "warnings": case.warnings,
        },
        "ecr": {
            "ecr_id": ecr.ecr_id,
            "status": ecr.status,
            "rule_id": ecr.rule_id,
            "warnings": ecr.warnings,
        },
        "validation": {
            "valid": validation.valid,
            "errors": validation.errors,
            "warnings": validation.warnings,
        },
        "submission": {
            "status": submission.status,
            "submission_id": submission.submission_id,
            "destination": submission.destination,
            "errors": submission.errors,
            "warnings": submission.warnings,
        },
    }
