from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.models.case import Case
from backend.app.case.report_fields import missing_report_fields
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
        reporting_method = (
            request.reporting_method.strip().upper()
        )

        if reporting_method not in SUPPORTED_MANUAL_METHODS:
            raise ValueError(
                f"Unsupported manual reporting method: "
                f"{request.reporting_method}"
            )

        # ---------------------------------------------------------
        # 3. Resolve the reporting form
        #
        # Agent 31 selects the configured form.
        # Agent 32 renders/populates the actual form.
        # ---------------------------------------------------------
        form_id = None
        form_version = None

        if (
            case.jurisdiction
            == TEXAS_MEASLES_FORM["jurisdiction"]
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
            **(case.report_fields or {}),
            **{key: value for key, value in (case.patient or {}).items() if key in {"first_name", "last_name", "address", "city", "county", "zip", "phone", "date_of_birth"}},
            **{f"provider.{key}": value for key, value in (case.provider or {}).items() if key in {"name", "phone", "address"}},
            **{f"facility.{key}": value for key, value in (case.facility or {}).items() if key == "name"},
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

        for field in ("name", "phone", "address"):
            if not (case.provider or {}).get(field):
                missing_fields.append(f"provider.{field}")

        _, required_missing = missing_report_fields(case.report_fields or {})
        missing_fields.extend(name for name in required_missing if name not in missing_fields)

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
        # 8. Record manual reporting preparation in audit ledger
        # ---------------------------------------------------------
        AuditLedgerService().record_event(
            AuditEventCreate(
                entity_type="CASE",
                entity_id=str(case.case_id),
                event_type="CASE_MANUAL_REPORT_PREPARED",
                actor_type="SYSTEM",
                actor_id="SIGNAL",
                source_agent="Agent-31",
                status="SUCCESS",
                description=(
                    "Manual reporting package prepared "
                    "for downstream reporting."
                ),
                new_value={
                    "status": status,
                    "reporting_method": reporting_method,
                    "form_id": form_id,
                    "form_version": form_version,
                },
                metadata={
                    "notes": request.notes,
                    "missing_fields": missing_fields,
                },
            ),
            db,
        )

        # ---------------------------------------------------------
        # 9. Return package for Agent 32
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
