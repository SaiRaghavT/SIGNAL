from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from backend.app.config.settings import settings

# ---------------------------------------------------------
# Member 1 / Member 2 routers
# ---------------------------------------------------------

from backend.app.agents.cluster_signal.api import router as cluster_router
from backend.app.canonical.api import router as canonical_router
from backend.app.detection.api import router as detection_router
from backend.app.ingestion.api.fhir import router as fhir_router
from backend.app.ingestion.documents.api import router as document_router
from backend.app.ingestion.hl7.api import router as hl7_router
from backend.app.agents.acknowledgement.router import router as acknowledgement_router
from backend.app.agents.attestation_control.router import router as attestation_router
from backend.app.agents.audit_ledger.router import router as audit_ledger_router
from backend.app.agents.case_assembly.router import router as case_assembly_router
from backend.app.agents.deadline_calculation.router import router as deadline_router
from backend.app.agents.deadline_escalation.router import router as deadline_escalation_router
from backend.app.agents.ecr_submission.router import router as ecr_submission_router
from backend.app.agents.form_rendering.router import router as form_rendering_router
from backend.app.agents.manual_reporting.router import router as manual_reporting_router
from backend.app.agents.public_health_followup.router import router as public_health_followup_router
from backend.app.agents.retry_resubmission.router import router as retry_resubmission_router
from backend.app.agents.submission_tracking.router import router as submission_tracking_router


# ---------------------------------------------------------
# Member 3 - Reportability & Reporting
# ---------------------------------------------------------

from backend.app.jurisdiction.models import JurisdictionInput
from backend.app.jurisdiction.resolver import resolve_jurisdiction

from backend.app.reportability.models import ReportabilityInput
from backend.app.reportability.evaluator import evaluate_reportability

from backend.app.rckms.decision_support import evaluate_decision_support

from backend.app.decision.models import ReconciliationInput
from backend.app.decision.reconciler import reconcile_decisions

from backend.app.smart_field_population.mapper import populate_report_fields

from backend.app.case.models import CaseAssemblyInput
from backend.app.case.assembler import assemble_case

from backend.app.ecr.builder import build_ecr

from backend.app.schemas.validation import validate_ecr

from backend.app.submission.service import submit_ecr


# ---------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------

app = FastAPI(
    title="SIGNAL MVP",
    description="Public Health Reporting Intelligence Layer",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Member 3 request model
# ---------------------------------------------------------

class CandidateProcessRequest(BaseModel):
    candidate_id: str

    patient_state: Optional[str] = None
    patient_county: Optional[str] = None

    facility_state: Optional[str] = None
    facility_county: Optional[str] = None

    disease: Optional[str] = None

    patient: Optional[dict] = None
    provider: Optional[dict] = None
    facility: Optional[dict] = None

    clinical_evidence: Optional[dict] = None
    laboratory_evidence: Optional[list] = None
    ai_evidence: Optional[dict] = None


# =========================================================
# MEMBER 1 / MEMBER 2 ROUTERS
# =========================================================

# ---------------------------------------------------------
# Ingestion APIs
# ---------------------------------------------------------

# FHIR ingestion
app.include_router(fhir_router)

# HL7 v2 ingestion
app.include_router(hl7_router)

# Unstructured document ingestion
app.include_router(document_router)

# Audit ledger
app.include_router(audit_ledger_router)


# ---------------------------------------------------------
# Canonical Data APIs
# ---------------------------------------------------------

# Standardized SIGNAL patient context
app.include_router(canonical_router)

# Candidate detection
app.include_router(detection_router)

# Population-level cluster analysis
app.include_router(cluster_router)

# =========================================================
# Reporting, submission, and PHA follow-up agent APIs
# =========================================================

app.include_router(acknowledgement_router)
app.include_router(attestation_router)
app.include_router(case_assembly_router)
app.include_router(deadline_router)
app.include_router(deadline_escalation_router)
app.include_router(ecr_submission_router)
app.include_router(form_rendering_router)
app.include_router(manual_reporting_router)
app.include_router(public_health_followup_router)
app.include_router(retry_resubmission_router)
app.include_router(submission_tracking_router)


# =========================================================
# MEMBER 3 - REPORTABILITY & REPORTING
# =========================================================

# ---------------------------------------------------------
# Agent 21 - Jurisdiction / RCKMS Decision Support
# ---------------------------------------------------------

@app.post("/api/jurisdiction/resolve")
def jurisdiction_resolve(data: JurisdictionInput):
    result = resolve_jurisdiction(data)

    return {
        "candidate_id": result.candidate_id,
        "jurisdiction": result.jurisdiction,
        "status": result.status,
        "reasons": result.reasons,
    }


# ---------------------------------------------------------
# Agents 21, 22, 27, 28
# Complete Member 3 candidate workflow
# ---------------------------------------------------------

@app.post("/api/candidate/process")
def process_candidate(data: CandidateProcessRequest):

    # -----------------------------------------------------
    # Prepare input data
    # -----------------------------------------------------

    patient = data.patient or {}
    facility = data.facility or {}
    provider = data.provider or {}

    clinical_evidence = data.clinical_evidence or {}
    laboratory_evidence = data.laboratory_evidence or []
    ai_evidence = data.ai_evidence or {}

    patient_state = (
        data.patient_state
        or patient.get("state")
    )

    patient_county = (
        data.patient_county
        or patient.get("county")
    )

    facility_state = (
        data.facility_state
        or facility.get("state")
    )

    facility_county = (
        data.facility_county
        or facility.get("county")
    )

    # -----------------------------------------------------
    # Agent 21 - Jurisdiction Resolution
    # -----------------------------------------------------

    jurisdiction_input = JurisdictionInput(
        candidate_id=data.candidate_id,
        patient_state=patient_state,
        patient_county=patient_county,
        facility_state=facility_state,
        facility_county=facility_county,
        disease=data.disease,
    )

    jurisdiction = resolve_jurisdiction(
        jurisdiction_input
    )

    # -----------------------------------------------------
    # Reportability Evaluation
    # -----------------------------------------------------

    reportability_input = ReportabilityInput(
        candidate_id=data.candidate_id,
        jurisdiction=jurisdiction.jurisdiction,
        jurisdiction_status=jurisdiction.status,
        disease=data.disease,
        clinical_evidence=clinical_evidence,
        laboratory_evidence=laboratory_evidence,
        ai_evidence=ai_evidence,
    )

    reportability = evaluate_reportability(
        reportability_input
    )

    # -----------------------------------------------------
    # Agent 21 - RCKMS / Decision Support
    # -----------------------------------------------------

    rule_result = evaluate_decision_support(
        candidate_id=data.candidate_id,
        disease=data.disease,
        laboratory_evidence=laboratory_evidence,
        clinical_evidence=clinical_evidence,
    )

    # -----------------------------------------------------
    # Prepare AI decision
    # -----------------------------------------------------

    ai_condition = ai_evidence.get("condition")
    ai_confidence = ai_evidence.get("confidence")

    ai_decision = None

    if ai_condition and data.disease:

        if (
            str(ai_condition).lower()
            == str(data.disease).lower()
        ):
            ai_decision = "POSITIVE"
        else:
            ai_decision = "NEGATIVE"

    # -----------------------------------------------------
    # Laboratory decision
    # -----------------------------------------------------

    laboratory_decisions = []

    for lab in laboratory_evidence:

        status = str(
            lab.get("status", "")
        ).upper()

        result = str(
            lab.get("result", "")
        ).upper()

        if (
            status in {"PENDING", "IN_PROGRESS"}
            or result in {"PENDING", "IN PROGRESS"}
        ):
            laboratory_decisions.append(
                "PENDING"
            )

        elif (
            status in {
                "INCONCLUSIVE",
                "INDETERMINATE",
            }
            or result in {
                "INCONCLUSIVE",
                "INDETERMINATE",
            }
        ):
            laboratory_decisions.append(
                "INCONCLUSIVE"
            )

        elif result in {
            "POSITIVE",
            "DETECTED",
            "REACTIVE",
        }:
            laboratory_decisions.append(
                "POSITIVE"
            )

        elif result in {
            "NEGATIVE",
            "NOT DETECTED",
            "NON-REACTIVE",
        }:
            laboratory_decisions.append(
                "NEGATIVE"
            )

    laboratory_decision = None

    if "PENDING" in laboratory_decisions:

        laboratory_decision = "PENDING"

    elif "INCONCLUSIVE" in laboratory_decisions:

        laboratory_decision = "INCONCLUSIVE"

    elif (
        "POSITIVE" in laboratory_decisions
        and "NEGATIVE" in laboratory_decisions
    ):

        laboratory_decision = "INCONCLUSIVE"

    elif laboratory_decisions:

        laboratory_decision = (
            laboratory_decisions[0]
        )

    # -----------------------------------------------------
    # Agent 22 - Decision Reconciliation
    # -----------------------------------------------------

    reconciliation_input = ReconciliationInput(
        candidate_id=data.candidate_id,
        ai_decision=ai_decision,
        ai_confidence=ai_confidence,
        laboratory_decision=(
            laboratory_decision
        ),
        rule_decision=rule_result.decision,
        jurisdiction_status=jurisdiction.status,
        reportability_decision=(
            reportability.decision
        ),
    )

    reconciliation = reconcile_decisions(
        reconciliation_input
    )

    # -----------------------------------------------------
    # Agent 27 - Smart Field Population
    # -----------------------------------------------------

    candidate_data = {
        "candidate_id": data.candidate_id,
        "disease": data.disease,
        "patient": patient,
        "provider": provider,
        "facility": facility,
        "clinical_evidence": clinical_evidence,
        "laboratory_evidence": laboratory_evidence,
        "ai_evidence": ai_evidence,
        "jurisdiction": jurisdiction.jurisdiction,
        "jurisdiction_status": jurisdiction.status,
        "reportability_decision": (
            reportability.decision
        ),
        "reportability_evidence_status": (
            reportability.evidence_status
        ),
        "reconciliation_decision": (
            reconciliation.final_decision
        ),
    }

    smart_fields = populate_report_fields(
        candidate_data
    )

    # -----------------------------------------------------
    # Case Assembly
    # -----------------------------------------------------

    case_input = CaseAssemblyInput(
        candidate_id=data.candidate_id,
        patient=patient,
        facility=facility,
        provider=provider,
        disease=data.disease,
        clinical_evidence=clinical_evidence,
        laboratory_evidence=laboratory_evidence,
        ai_evidence=ai_evidence,
        jurisdiction=jurisdiction.jurisdiction,
        jurisdiction_status=jurisdiction.status,
        reportability_decision=(
            reportability.decision
        ),
        reportability_evidence_status=(
            reportability.evidence_status
        ),
        final_decision=(
            reconciliation.final_decision
        ),
        rule_id=rule_result.rule_id,
    )

    case = assemble_case(case_input)

    # -----------------------------------------------------
    # eCR Generation
    # -----------------------------------------------------

    ecr = build_ecr(case)

    # -----------------------------------------------------
    # Agent 28 - Report Validation
    # -----------------------------------------------------

    validation = validate_ecr(ecr)

    # -----------------------------------------------------
    # Submission
    # -----------------------------------------------------

    submission = submit_ecr(
        ecr,
        validation,
    )

    # -----------------------------------------------------
    # Final response
    # -----------------------------------------------------

    return {
        "candidate_id": data.candidate_id,

        "workflow_status": (
            reconciliation.final_decision
        ),

        "jurisdiction": {
            "value": jurisdiction.jurisdiction,
            "status": jurisdiction.status,
            "reasons": jurisdiction.reasons,
        },

        "reportability": {
            "decision": reportability.decision,
            "evidence_status": (
                reportability.evidence_status
            ),
            "reasons": reportability.reasons,
            "warnings": reportability.warnings,
        },

        "rule_evaluation": {
            "decision": rule_result.decision,
            "rule_id": rule_result.rule_id,
            "reasons": rule_result.reasons,
            "warnings": rule_result.warnings,
        },

        "reconciliation": {
            "final_decision": (
                reconciliation.final_decision
            ),
            "reasons": reconciliation.reasons,
            "warnings": reconciliation.warnings,
        },

        "smart_field_population": {
            "fields": smart_fields.fields,
            "populated_fields": (
                smart_fields.populated_fields
            ),
            "missing_fields": (
                smart_fields.missing_fields
            ),
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
            "submission_id": (
                submission.submission_id
            ),
            "destination": (
                submission.destination
            ),
            "errors": submission.errors,
            "warnings": submission.warnings,
        },
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "signal-mvp",
    }