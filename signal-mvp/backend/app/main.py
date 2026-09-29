from datetime import datetime, timezone
from app.ingestion.fhir.normalizer import normalize_bundle
from app.detection.candidate_service import detect_candidates
from typing import Any, Dict, Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
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
app = FastAPI(title='SIGNAL API', description='SIGNAL Public Health Reporting Intelligence API', version='1.0.0')

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

@app.get("/")
def root():
    return {
        "service": "SIGNAL FHIR Ingestion API",
        "status": "running",
        "version": "1.0.0",
    }
@app.get('/health')
def health():
    return {'status': 'healthy'}

@app.post('/api/jurisdiction/resolve')
def jurisdiction_resolve(data: JurisdictionInput):
    result = resolve_jurisdiction(data)
    return {'candidate_id': result.candidate_id, 'jurisdiction': result.jurisdiction, 'status': result.status, 'reasons': result.reasons}

@app.post('/api/candidate/process')
def process_candidate(data: CandidateProcessRequest):
    patient = data.patient or {}
    facility = data.facility or {}
    provider = data.provider or {}
    clinical_evidence = data.clinical_evidence or {}
    laboratory_evidence = data.laboratory_evidence or []
    ai_evidence = data.ai_evidence or {}
    patient_state = data.patient_state or patient.get('state')
    patient_county = data.patient_county or patient.get('county')
    facility_state = data.facility_state or facility.get('state')
    facility_county = data.facility_county or facility.get('county')
    jurisdiction_input = JurisdictionInput(candidate_id=data.candidate_id, patient_state=patient_state, patient_county=patient_county, facility_state=facility_state, facility_county=facility_county, disease=data.disease)
    jurisdiction = resolve_jurisdiction(jurisdiction_input)
    reportability_input = ReportabilityInput(candidate_id=data.candidate_id, jurisdiction=jurisdiction.jurisdiction, jurisdiction_status=jurisdiction.status, disease=data.disease, clinical_evidence=clinical_evidence, laboratory_evidence=laboratory_evidence, ai_evidence=ai_evidence)
    reportability = evaluate_reportability(reportability_input)
    rule_result = evaluate_decision_support(candidate_id=data.candidate_id, disease=data.disease, laboratory_evidence=laboratory_evidence, clinical_evidence=clinical_evidence)
    ai_condition = ai_evidence.get('condition')
    ai_confidence = ai_evidence.get('confidence')
    ai_decision = None
    if ai_condition and data.disease:
        if str(ai_condition).lower() == str(data.disease).lower():
            ai_decision = 'POSITIVE'
        else:
            ai_decision = 'NEGATIVE'
    laboratory_decision = None
    laboratory_decisions = []
    for lab in laboratory_evidence:
        status = str(lab.get('status', '')).upper()
        result = str(lab.get('result', '')).upper()
        if status in {'PENDING', 'IN_PROGRESS'} or result in {'PENDING', 'IN PROGRESS'}:
            laboratory_decisions.append('PENDING')
        elif status in {'INCONCLUSIVE', 'INDETERMINATE'} or result in {'INCONCLUSIVE', 'INDETERMINATE'}:
            laboratory_decisions.append('INCONCLUSIVE')
        elif result in {'POSITIVE', 'DETECTED', 'REACTIVE'}:
            laboratory_decisions.append('POSITIVE')
        elif result in {'NEGATIVE', 'NOT DETECTED', 'NON-REACTIVE'}:
            laboratory_decisions.append('NEGATIVE')
    if 'PENDING' in laboratory_decisions:
        laboratory_decision = 'PENDING'
    elif 'INCONCLUSIVE' in laboratory_decisions:
        laboratory_decision = 'INCONCLUSIVE'
    elif 'POSITIVE' in laboratory_decisions and 'NEGATIVE' in laboratory_decisions:
        laboratory_decision = 'INCONCLUSIVE'
    elif laboratory_decisions:
        laboratory_decision = laboratory_decisions[0]
    reconciliation_input = ReconciliationInput(candidate_id=data.candidate_id, ai_decision=ai_decision, ai_confidence=ai_confidence, laboratory_decision=laboratory_decision, rule_decision=rule_result.decision, jurisdiction_status=jurisdiction.status, reportability_decision=reportability.decision)
    reconciliation = reconcile_decisions(reconciliation_input)
    candidate_data = {'candidate_id': data.candidate_id, 'disease': data.disease, 'patient': patient, 'provider': provider, 'facility': facility, 'clinical_evidence': clinical_evidence, 'laboratory_evidence': laboratory_evidence, 'ai_evidence': ai_evidence, 'jurisdiction': jurisdiction.jurisdiction, 'jurisdiction_status': jurisdiction.status, 'reportability_decision': reportability.decision, 'reportability_evidence_status': reportability.evidence_status, 'reconciliation_decision': reconciliation.final_decision}
    smart_fields = populate_report_fields(candidate_data)
    case_input = CaseAssemblyInput(candidate_id=data.candidate_id, patient=patient, facility=facility, provider=provider, disease=data.disease, clinical_evidence=clinical_evidence, laboratory_evidence=laboratory_evidence, ai_evidence=ai_evidence, jurisdiction=jurisdiction.jurisdiction, jurisdiction_status=jurisdiction.status, reportability_decision=reportability.decision, reportability_evidence_status=reportability.evidence_status, final_decision=reconciliation.final_decision, rule_id=rule_result.rule_id)
    case = assemble_case(case_input)
    ecr = build_ecr(case)
    validation = validate_ecr(ecr)
    submission = submit_ecr(ecr, validation)
    return {'candidate_id': data.candidate_id, 'workflow_status': reconciliation.final_decision, 'jurisdiction': {'value': jurisdiction.jurisdiction, 'status': jurisdiction.status, 'reasons': jurisdiction.reasons}, 'reportability': {'decision': reportability.decision, 'evidence_status': reportability.evidence_status, 'reasons': reportability.reasons, 'warnings': reportability.warnings}, 'rule_evaluation': {'decision': rule_result.decision, 'rule_id': rule_result.rule_id, 'reasons': rule_result.reasons, 'warnings': rule_result.warnings}, 'reconciliation': {'final_decision': reconciliation.final_decision, 'reasons': reconciliation.reasons, 'warnings': reconciliation.warnings}, 'smart_field_population': {'fields': smart_fields.fields, 'populated_fields': smart_fields.populated_fields, 'missing_fields': smart_fields.missing_fields, 'warnings': smart_fields.warnings}, 'case': {'case_id': case.case_id, 'status': case.status, 'warnings': case.warnings}, 'ecr': {'ecr_id': ecr.ecr_id, 'status': ecr.status, 'rule_id': ecr.rule_id, 'warnings': ecr.warnings}, 'validation': {'valid': validation.valid, 'errors': validation.errors, 'warnings': validation.warnings}, 'submission': {'status': submission.status, 'submission_id': submission.submission_id, 'destination': submission.destination, 'errors': submission.errors, 'warnings': submission.warnings}}

@app.post('/api/ingestion/fhir')
def ingest_fhir(bundle: Dict[str, Any], source_system: str | None=Header(default=None, alias='X-Source-System'), fhir_version: str | None=Header(default=None, alias='X-FHIR-Version')):
    """
    Receive a FHIR Bundle and normalize it.

    Provenance is supplied through HTTP headers.
    The ingestion timestamp is generated by the API.
    """
    try:
        if bundle.get('resourceType') != 'Bundle':
            raise HTTPException(status_code=400, detail='Input must be a FHIR Bundle.')
        entries = bundle.get('entry', [])
        if not isinstance(entries, list):
            raise HTTPException(status_code=400, detail='FHIR Bundle entry must be a list.')
        resources: Dict[str, list[Dict[str, Any]]] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise HTTPException(status_code=400, detail='FHIR Bundle entry must be a valid object.')
            resource = entry.get('resource')
            if not isinstance(resource, dict):
                raise HTTPException(status_code=400, detail='FHIR Bundle entry must contain a valid resource.')
            resource_type = resource.get('resourceType')
            if not resource_type:
                raise HTTPException(status_code=400, detail='FHIR resourceType is missing.')
            resources.setdefault(resource_type, []).append(resource)
        provenance = {'source_system': source_system, 'source_format': 'FHIR', 'fhir_version': fhir_version, 'ingested_at': datetime.now(timezone.utc).isoformat()}
        normalized = normalize_bundle(resources, provenance=provenance)
        return {'status': 'success', 'message': 'FHIR Bundle ingested and normalized successfully.', 'data': normalized}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'FHIR normalization failed: {str(exc)}')

@app.post('/api/detection/candidates')
def detect_candidate_endpoint(normalized_patient: Dict[str, Any], triggers: list[Dict[str, Any]] | None=None):
    """
    Detect potential public-health candidates from normalized
    clinical data using configured structured triggers.
    """
    try:
        result = detect_candidates(normalized_patient=normalized_patient, triggers=triggers)
        return {'status': 'success', 'message': 'Candidate detection completed successfully.', 'data': result}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f'Candidate detection failed: {str(exc)}')
