from sqlalchemy.orm import Session

from backend.app.models.case import Case
from backend.app.smart_field_population.form_config import (
    TEXAS_MEASLES_FORM,
)

from .schemas import (
    ManualReportingRequest,
    ManualReportingResponse,
)


SUPPORTED_MANUAL_METHODS = {
    "FORM",
    "FAX",
    "PHONE",
    "SECURE_EMAIL",
}


class ManualReportingService:

    def prepare_manual_report(
        self,
        request: ManualReportingRequest,
        db: Session,
    ) -> ManualReportingResponse:

        # ---------------------------------------------------------
        # 1. Load the persisted Case
        # ---------------------------------------------------------
        case = (
            db.query(Case)
            .filter(Case.case_id == request.case_id)
            .first()
        )

        if case is None:
            raise ValueError(
                f"Case not found: {request.case_id}"
            )

        # ---------------------------------------------------------
        # 2. Validate reporting method
        # ---------------------------------------------------------
        reporting_method = request.reporting_method.strip().upper()

        if reporting_method not in SUPPORTED_MANUAL_METHODS:
            raise ValueError(
                f"Unsupported manual reporting method: "
                f"{request.reporting_method}"
            )

        # ---------------------------------------------------------
        # 3. Resolve the reporting form
        #
        # Agent 31 selects the configured form.
        # Agent 32 will render/populate the actual form.
        # ---------------------------------------------------------
        form_id = None
        form_version = None

        if (
            case.jurisdiction == TEXAS_MEASLES_FORM["jurisdiction"]
            and case.disease
            and case.disease.casefold()
            == TEXAS_MEASLES_FORM["disease"].casefold()
        ):
            form_id = TEXAS_MEASLES_FORM["form_id"]
            form_version = TEXAS_MEASLES_FORM["form_version"]
        else:
            raise ValueError(
                "No manual reporting form configured for "
                f"disease={case.disease}, "
                f"jurisdiction={case.jurisdiction}"
            )

        # ---------------------------------------------------------
        # 4. Build the reporting package
        # ---------------------------------------------------------
        report_data = {
            "case_id": str(case.case_id),
            "candidate_id": case.candidate_id,
            "patient": case.patient,
            "facility": case.facility,
            "provider": case.provider,
            "disease": case.disease,
            "clinical_evidence": case.clinical_evidence,
            "laboratory_evidence": case.laboratory_evidence,
            "ai_evidence": case.ai_evidence,
            "jurisdiction": case.jurisdiction,
            "jurisdiction_status": case.jurisdiction_status,
            "reportability_decision": (
                case.reportability_decision
            ),
            "reportability_evidence_status": (
                case.reportability_evidence_status
            ),
            "final_decision": case.final_decision,
            "rule_id": case.rule_id,
        }

        # ---------------------------------------------------------
        # 5. Identify basic missing information
        # ---------------------------------------------------------
        missing_fields: list[str] = []
        warnings: list[str] = []

        if not case.disease:
            missing_fields.append("disease")

        if not case.jurisdiction:
            missing_fields.append("jurisdiction")

        if not case.patient:
            missing_fields.append("patient")

        if not case.facility:
            missing_fields.append("facility")

        if not case.provider:
            missing_fields.append("provider")

        # ---------------------------------------------------------
        # 6. Check case status
        # ---------------------------------------------------------
        if case.status != "REPORT":
            warnings.append(
                f"Case status is {case.status}; "
                "manual reporting requires review."
            )

        # Include any warnings already recorded on the Case.
        if case.warnings:
            warnings.extend(case.warnings)

        # ---------------------------------------------------------
        # 7. Determine package status
        # ---------------------------------------------------------
        if missing_fields:
            status = "NEEDS_REVIEW"
        else:
            status = "READY_FOR_RENDERING"

        # ---------------------------------------------------------
        # 8. Return package for Agent 32
        # ---------------------------------------------------------
        return ManualReportingResponse(
            case_id=str(case.case_id),
            status=status,
            reporting_method=reporting_method,
            jurisdiction=case.jurisdiction,
            disease=case.disease,
            form_id=form_id,
            form_version=form_version,
            report_data=report_data,
            missing_fields=missing_fields,
            warnings=warnings,
            notes=request.notes,
        )