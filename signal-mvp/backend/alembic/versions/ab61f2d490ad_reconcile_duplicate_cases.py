"""Reconcile repeated Case rows per persisted Candidate.

Revision ID: ab61f2d490ad
Revises: d9f78a6e2c11
"""

from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "ab61f2d490ad"
down_revision: Union[str, Sequence[str], None] = "d9f78a6e2c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _counts(connection, table_name: str, column_name: str, case_ids: list[str]) -> dict[str, int]:
    if not case_ids:
        return {}
    table = sa.table(table_name, sa.column(column_name, sa.String()))
    rows = connection.execute(
        sa.select(table.c[column_name], sa.func.count())
        .where(table.c[column_name].in_(case_ids))
        .group_by(table.c[column_name])
    )
    return {str(case_id): int(count) for case_id, count in rows}


def _workflow_states(connection, case_ids: list[str]) -> dict[str, list[tuple[str, str]]]:
    if not case_ids:
        return {}
    records = sa.table(
        "case_workflow_records",
        sa.column("case_id", sa.String()),
        sa.column("record_type", sa.String()),
        sa.column("status", sa.String()),
    )
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    rows = connection.execute(
        sa.select(records.c.case_id, records.c.record_type, records.c.status)
        .where(records.c.case_id.in_(case_ids))
    )
    for case_id, record_type, status in rows:
        grouped[str(case_id)].append((str(record_type).upper(), str(status).upper()))
    return grouped


def _submission_states(connection, case_ids: list[str]) -> dict[str, list[str]]:
    if not case_ids:
        return {}
    submissions = sa.table(
        "submissions",
        sa.column("case_id", sa.String()),
        sa.column("status", sa.String()),
    )
    grouped: dict[str, list[str]] = defaultdict(list)
    rows = connection.execute(
        sa.select(submissions.c.case_id, submissions.c.status)
        .where(submissions.c.case_id.in_(case_ids))
    )
    for case_id, status in rows:
        grouped[str(case_id)].append(str(status).upper())
    return grouped


def _has_patient_and_condition_identity(case_rows: list[dict]) -> bool:
    identities = set()
    for row in case_rows:
        patient = row["patient"] if isinstance(row["patient"], dict) else {}
        patient_id = patient.get("patient_id") or patient.get("id")
        disease = str(row["disease"] or "").strip().casefold()
        identities.add((str(patient_id or ""), disease))
    return len(identities) == 1 and bool(next(iter(identities))[0])


def _canonical_score(
    row: dict,
    linked_case_id: str | None,
    workflow: dict[str, list[tuple[str, str]]],
    submissions: dict[str, list[str]],
    dependency_counts: dict[str, dict[str, int]],
) -> tuple:
    case_id = str(row["case_id"])
    workflow_rows = workflow.get(case_id, [])
    submission_statuses = submissions.get(case_id, [])
    valid_workflow = sum(
        record_type == "VALIDATION" and status == "VALID"
        for record_type, status in workflow_rows
    )
    approved_reviews = sum(
        record_type == "REVIEW" and status in {"APPROVE", "APPROVED"}
        for record_type, status in workflow_rows
    )
    attestations = sum(
        record_type == "ATTESTATION" and status == "ATTESTED"
        for record_type, status in workflow_rows
    )
    ready_records = sum(
        record_type == "SUBMISSION_READINESS" and status == "READY"
        for record_type, status in workflow_rows
    )
    successful_submissions = sum(status in {"SUBMITTED", "ACKNOWLEDGED"} for status in submission_statuses)
    submitted_state = str(row["status"] or "").upper() in {"SUBMITTED", "ACKNOWLEDGED"}
    decision_state = str(row["final_decision"] or "").upper() == "REPORT"
    dep_total = sum(counts.get(case_id, 0) for counts in dependency_counts.values())
    patient = row["patient"] if isinstance(row["patient"], dict) else {}
    completeness = sum(bool(row.get(field)) for field in ("disease", "jurisdiction", "rule_id"))
    completeness += sum(bool(patient.get(field)) for field in ("patient_id", "first_name", "last_name", "date_of_birth"))
    completeness += sum(bool(row.get(field)) for field in ("facility", "provider", "clinical_evidence", "laboratory_evidence", "ai_evidence", "report_fields"))
    status_rank = {
        "ACKNOWLEDGED": 7,
        "SUBMITTED": 6,
        "REPORT": 5,
        "UNDER_INVESTIGATION": 4,
        "NEEDS_REVIEW": 3,
        "HOLD": 2,
        "DUPLICATE": 1,
    }.get(str(row["status"] or "").upper(), 0)
    return (
        case_id == linked_case_id,
        successful_submissions,
        ready_records,
        valid_workflow,
        approved_reviews,
        attestations,
        submitted_state,
        decision_state,
        dep_total,
        completeness,
        status_rank,
        row["updated_at"],
        row["created_at"],
    )


def upgrade() -> None:
    connection = op.get_bind()
    cases = sa.table(
        "cases",
        sa.column("case_id", sa.Uuid()),
        sa.column("candidate_id", sa.String()),
        sa.column("patient", sa.JSON()),
        sa.column("disease", sa.String()),
        sa.column("status", sa.String()),
        sa.column("final_decision", sa.String()),
        sa.column("jurisdiction", sa.String()),
        sa.column("rule_id", sa.String()),
        sa.column("facility", sa.JSON()),
        sa.column("provider", sa.JSON()),
        sa.column("clinical_evidence", sa.JSON()),
        sa.column("laboratory_evidence", sa.JSON()),
        sa.column("ai_evidence", sa.JSON()),
        sa.column("report_fields", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    rows = [dict(row._mapping) for row in connection.execute(sa.select(cases))]
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        groups[str(row["candidate_id"])].append(row)

    workflow_table = sa.table(
        "case_workflow_records",
        sa.column("case_id", sa.String()),
        sa.column("record_type", sa.String()),
        sa.column("status", sa.String()),
    )
    submission_table = sa.table(
        "submissions",
        sa.column("case_id", sa.String()),
        sa.column("status", sa.String()),
    )
    candidate_table = sa.table(
        "candidates",
        sa.column("candidate_id", sa.String()),
        sa.column("case_id", sa.String()),
    )
    dependency_tables = {
        "workflow": ("case_workflow_records", "case_id"),
        "reports": ("reports", "case_id"),
        "submissions": ("submissions", "case_id"),
        "followups": ("follow_ups", "case_id"),
        "deadlines": ("deadline_escalations", "case_id"),
        "audit": ("audit_events", "entity_id"),
        "baselines": ("demo_case_baselines", "case_id"),
    }

    for candidate_id, case_rows in groups.items():
        if len(case_rows) < 2:
            continue
        if not _has_patient_and_condition_identity(case_rows):
            raise RuntimeError(
                "Refusing to reconcile Cases with one candidate_id but different patient/condition identities: "
                f"{candidate_id}"
            )

        case_ids = [str(row["case_id"]) for row in case_rows]
        link = connection.execute(
            sa.select(candidate_table.c.case_id).where(candidate_table.c.candidate_id == candidate_id)
        ).scalar_one_or_none()
        linked_case_id = str(link) if link else None
        if linked_case_id not in case_ids:
            linked_case_id = None

        workflow = _workflow_states(connection, case_ids)
        submissions = _submission_states(connection, case_ids)
        dependency_counts = {
            key: _counts(connection, table_name, column_name, case_ids)
            for key, (table_name, column_name) in dependency_tables.items()
        }
        if dependency_counts["audit"]:
            audit = sa.table(
                "audit_events",
                sa.column("entity_id", sa.String()),
                sa.column("entity_type", sa.String()),
            )
            audit_rows = connection.execute(
                sa.select(audit.c.entity_id, sa.func.count())
                .where(audit.c.entity_type == "CASE", audit.c.entity_id.in_(case_ids))
                .group_by(audit.c.entity_id)
            )
            dependency_counts["audit"] = {str(case_id): int(count) for case_id, count in audit_rows}

        canonical = max(
            case_rows,
            key=lambda row: _canonical_score(
                row, linked_case_id, workflow, submissions, dependency_counts
            ),
        )
        canonical_id = str(canonical["case_id"])
        duplicates = [case_id for case_id in case_ids if case_id != canonical_id]

        baseline = sa.table("demo_case_baselines", sa.column("case_id", sa.String()))
        canonical_baseline = connection.execute(
            sa.select(baseline.c.case_id).where(baseline.c.case_id == canonical_id)
        ).first()
        duplicate_baselines = connection.execute(
            sa.select(baseline.c.case_id).where(baseline.c.case_id.in_(duplicates))
        ).all()
        if canonical_baseline and duplicate_baselines:
            raise RuntimeError(
                "Refusing to discard multiple demo baselines while reconciling Case "
                f"{canonical_id}."
            )

        for table_name, column_name in (
            ("case_workflow_records", "case_id"),
            ("reports", "case_id"),
            ("submissions", "case_id"),
            ("follow_ups", "case_id"),
            ("deadline_escalations", "case_id"),
        ):
            table = sa.table(table_name, sa.column(column_name, sa.String()))
            connection.execute(
                table.update().where(table.c[column_name].in_(duplicates)).values({column_name: canonical_id})
            )

        audit_events = sa.table(
            "audit_events",
            sa.column("entity_id", sa.String()),
            sa.column("entity_type", sa.String()),
        )
        connection.execute(
            audit_events.update()
            .where(audit_events.c.entity_type == "CASE", audit_events.c.entity_id.in_(duplicates))
            .values(entity_id=canonical_id)
        )
        connection.execute(
            candidate_table.update()
            .where(candidate_table.c.candidate_id == candidate_id)
            .values(case_id=canonical_id)
        )
        if duplicate_baselines:
            connection.execute(
                baseline.update().where(baseline.c.case_id.in_(duplicates)).values(case_id=canonical_id)
            )
        connection.execute(cases.delete().where(cases.c.case_id.in_(duplicates)))

    duplicate_candidate = connection.execute(
        sa.select(cases.c.candidate_id)
        .group_by(cases.c.candidate_id)
        .having(sa.func.count() > 1)
        .limit(1)
    ).first()
    if duplicate_candidate:
        raise RuntimeError(f"Case reconciliation left duplicate candidate_id {duplicate_candidate[0]}.")

    op.create_unique_constraint("uq_cases_candidate_id", "cases", ["candidate_id"])


def downgrade() -> None:
    op.drop_constraint("uq_cases_candidate_id", "cases", type_="unique")
