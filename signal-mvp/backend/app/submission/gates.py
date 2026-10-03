from types import SimpleNamespace

from sqlalchemy.orm import Session

from backend.app.models.audit_event import AuditEvent


def case_has_current_attestation(db: Session, case) -> bool:
    if case.status != "REPORT":
        return False
    return (
        db.query(AuditEvent)
        .filter(
            AuditEvent.entity_type == "CASE",
            AuditEvent.entity_id == str(case.case_id),
            AuditEvent.event_type == "CASE_ATTESTED",
            AuditEvent.status == "SUCCESS",
        )
        .first()
        is not None
    )


def smart_fields_for_case(case):
    from backend.app.case.report_fields import missing_report_fields

    fields = getattr(case, "report_fields", {}) or {}
    missing, required_missing = missing_report_fields(fields)
    return SimpleNamespace(
        fields=fields,
        missing_fields=missing,
        required_missing_fields=required_missing,
    )
