from uuid import uuid4

from .schemas import (
    CaseAssemblyRequest,
    CaseAssemblyResponse,
)


class CaseAssemblyService:

    def assemble(
        self,
        request: CaseAssemblyRequest,
    ) -> CaseAssemblyResponse:

        case_reference = f"CASE-{uuid4().hex[:8].upper()}"

        assembled_data = {
            "patient_id": request.patient_id,
            "candidate_signals": request.candidate_signals,
            "reportability_decision": request.reportability_decision,
            "jurisdiction": request.jurisdiction,
            "reporting_deadline": request.reporting_deadline,
        }

        return CaseAssemblyResponse(
            case_reference=case_reference,
            patient_id=request.patient_id,
            status="ASSEMBLED",
            jurisdiction=request.jurisdiction,
            candidate_signals=request.candidate_signals,
            reportability_decision=request.reportability_decision,
            reporting_deadline=request.reporting_deadline,
            assembled_data=assembled_data,
        )