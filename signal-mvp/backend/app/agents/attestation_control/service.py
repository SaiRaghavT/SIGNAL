import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService
from backend.app.ecr.builder import build_ecr
from backend.app.models.case import Case
from backend.app.schemas.validation import validate_ecr
from backend.app.case.report_fields import missing_report_fields

from .schemas import (
    AttestationRequest,
    AttestationResponse,
)


class AttestationControlService:

    def __init__(self) -> None:
        self.config_path = (
            Path(__file__).resolve().parents[2]
            / "config"
            / "attestation_roles.json"
        )

    def _load_authorized_roles(self) -> set[str]:
        with self.config_path.open(
            "r",
            encoding="utf-8",
        ) as file:
            config = json.load(file)

        return {
            role.upper().strip()
            for role in config.get("authorized_roles", [])
        }

    def validate(
        self,
        request: AttestationRequest,
        db: Session,
    ) -> AttestationResponse:

        if not request.case_reference.strip():
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Case reference is required.",
                comments=request.comments,
            )

        if not request.reviewer_id.strip():
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Reviewer ID is required.",
                comments=request.comments,
            )

        if not request.reviewer_role.strip():
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Reviewer role is required.",
                comments=request.comments,
            )

        authorized_roles = self._load_authorized_roles()

        reviewer_role = request.reviewer_role.upper().strip()

        if reviewer_role not in authorized_roles:
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message=(
                    f"Reviewer role '{request.reviewer_role}' "
                    "is not authorized to attest."
                ),
                comments=request.comments,
            )

        if request.attestation_status.upper().strip() != "ATTESTED":
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Case has not been attested.",
                comments=request.comments,
            )

        try:
            case_id = UUID(request.case_reference.strip())
        except ValueError:
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="A persisted case UUID is required for attestation.",
                comments=request.comments,
            )

        case = db.query(Case).filter(Case.case_id == case_id).first()
        if case is None:
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Case was not found.",
                comments=request.comments,
            )

        if case.jurisdiction_status != "RESOLVED":
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Jurisdiction review must be resolved before attestation.",
                comments=request.comments,
            )

        if case.final_decision != "REPORT":
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Only a REPORT decision can be attested for submission.",
                comments=request.comments,
            )

        missing, required_missing = missing_report_fields(case.report_fields or {})
        ecr = build_ecr(case)
        # Attestation is the human review transition from NEEDS_REVIEW to
        # REPORT; validate the underlying evidence before that transition.
        ecr.status = "REPORT"
        validation = validate_ecr(
            ecr,
            SimpleNamespace(
                fields=case.report_fields or {},
                missing_fields=missing,
                required_missing_fields=required_missing,
            ),
        )
        if not validation.valid:
            tasks = validation.completion_required + validation.errors
            return AttestationResponse(
                case_reference=request.case_reference,
                reviewer_id=request.reviewer_id,
                reviewer_role=request.reviewer_role,
                attestation_status=request.attestation_status,
                authorized=False,
                message="Attestation is blocked: " + "; ".join(tasks),
                comments=request.comments,
            )

        case.status = "REPORT"
        db.commit()
        db.refresh(case)

        # Successful attestation is recorded in the audit ledger.
        audit_service = AuditLedgerService()

        audit_service.record_event(
            AuditEventCreate(
                entity_type="CASE",
                entity_id=request.case_reference.strip(),
                event_type="CASE_ATTESTED",
                actor_type="USER",
                actor_id=request.reviewer_id.strip(),
                source_agent="Agent-30",
                status="SUCCESS",
                description="Case attestation accepted.",
                previous_value={
                    "attestation_status": "PENDING",
                },
                new_value={
                    "attestation_status": "ATTESTED",
                    "reviewer_role": reviewer_role,
                },
                metadata={
                    "comments": request.comments,
                },
            ),
            db,
        )

        return AttestationResponse(
            case_reference=request.case_reference,
            reviewer_id=request.reviewer_id,
            reviewer_role=request.reviewer_role,
            attestation_status=request.attestation_status,
            authorized=True,
            message="Attestation accepted.",
            comments=request.comments,
        )
