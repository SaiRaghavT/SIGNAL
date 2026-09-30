import json
from pathlib import Path

from sqlalchemy.orm import Session

from backend.app.agents.audit_ledger.schemas import AuditEventCreate
from backend.app.agents.audit_ledger.service import AuditLedgerService

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
            audit_service = AuditLedgerService()

        print(
            "DEBUG: Agent 30 is recording CASE_ATTESTED audit event"
        )

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
                    "attestation_status": "PENDING"
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

        return AttestationResponse(
            case_reference=request.case_reference,
            reviewer_id=request.reviewer_id,
            reviewer_role=request.reviewer_role,
            attestation_status=request.attestation_status,
            authorized=True,
            message="Attestation accepted.",
            comments=request.comments,
        )