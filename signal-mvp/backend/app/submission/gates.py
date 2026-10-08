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
    from backend.app.case.report_fields import (
        available_case_report_fields,
        missing_report_fields,
    )

    # Validate the same merged field values shown in Reporting Data. Values
    # may come from patient/clinical/lab records even when no form edit saved
    # them explicitly into case.report_fields yet.
    fields = available_case_report_fields(case)
    missing, required_missing = missing_report_fields(fields)
    return SimpleNamespace(
        fields=fields,
        missing_fields=missing,
        required_missing_fields=required_missing,
    )
