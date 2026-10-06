from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.config.demo import is_demo_case
from backend.app.models.candidate import Candidate
from backend.app.models.case import Case
from backend.app.demo.reset_service import store_demo_baseline

from .models import CaseAssemblyInput, SignalCase


def _to_signal_case(case: Case) -> SignalCase:
    return SignalCase(
        case_id=str(case.case_id),
        candidate_id=case.candidate_id,
        patient=case.patient,
        facility=case.facility,
        provider=case.provider,
        disease=case.disease,
        clinical_evidence=case.clinical_evidence,
        laboratory_evidence=case.laboratory_evidence,
        ai_evidence=case.ai_evidence,
        jurisdiction=case.jurisdiction,
        jurisdiction_status=case.jurisdiction_status,
        reportability_decision=case.reportability_decision,
        reportability_evidence_status=case.reportability_evidence_status,
        status=case.status,
        warnings=case.warnings,
        final_decision=case.final_decision,
        rule_id=case.rule_id,
        report_fields=case.report_fields or {},
    )


def assemble_case(
    data: CaseAssemblyInput,
    db: Session,
    existing_case_id: str | None = None,
) -> SignalCase:
    warnings = []

    if data.jurisdiction_status != "RESOLVED":
        warnings.append("Jurisdiction requires review.")

    if not data.patient:
        warnings.append("Patient information is missing.")

    if not data.disease:
        warnings.append("Disease information is missing.")

    final_decision = data.final_decision or data.reportability_decision
    status = final_decision
    missing_provider_fields = [
        name for name in ("name", "phone", "address")
        if not (data.provider or {}).get(name)
    ]
    if status != "HOLD" and data.jurisdiction_status != "RESOLVED":
        status = "NEEDS_REVIEW"
    if status != "HOLD" and (data.required_missing_fields or missing_provider_fields or not (data.facility or {}).get("name")):
        status = "NEEDS_REVIEW"
        if data.required_missing_fields:
            warnings.append(
                f"{len(data.required_missing_fields)} required reporting fields need human completion."
            )
        if missing_provider_fields:
            warnings.append("Provider information needs human completion.")
        if not (data.facility or {}).get("name"):
            warnings.append("Facility name needs human completion.")

    values = {
        "candidate_id": data.candidate_id,
        "patient": data.patient,
        "facility": data.facility,
        "provider": data.provider,
        "disease": data.disease,
        "clinical_evidence": data.clinical_evidence,
        "laboratory_evidence": data.laboratory_evidence,
        "ai_evidence": data.ai_evidence,
        "report_fields": data.report_fields,
        "jurisdiction": data.jurisdiction,
        "jurisdiction_status": data.jurisdiction_status,
        "reportability_decision": data.reportability_decision,
        "reportability_evidence_status": data.reportability_evidence_status,
        "status": status,
        "final_decision": final_decision,
        "rule_id": data.rule_id,
        "warnings": warnings,
    }
    if existing_case_id:
        case = db.query(Case).filter(
            Case.case_id == existing_case_id,
            Case.candidate_id == data.candidate_id,
        ).first()
        if case is None or not is_demo_case(case):
            raise ValueError("Only the linked SIGNAL demo case can be reassembled after demo reset.")
        for key, value in values.items():
            setattr(case, key, value)
    else:
        case = db.query(Case).filter(Case.candidate_id == data.candidate_id).first()
        if case is not None:
            return _to_signal_case(case)
        case = Case(**values)
        db.add(case)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            case = db.query(Case).filter(Case.candidate_id == data.candidate_id).first()
            if case is None:
                raise
            return _to_signal_case(case)

    candidate = db.query(Candidate).filter(Candidate.candidate_id == data.candidate_id).first()
    if is_demo_case(case):
        store_demo_baseline(db, case, candidate)
    db.commit()
    db.refresh(case)

    return _to_signal_case(case)
