"""Add three clearly synthetic canonical patients for the demo worklist."""

from datetime import date
from uuid import UUID

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "a74c8d1e2f30"
down_revision = "f13d9a2c6b80"
branch_labels = None
depends_on = None

PATIENTS = (
    {
        "patient_id": UUID("fbe3a1e0-0000-4000-8000-000000000001"),
        "source_patient_id": "SIGNAL-DEMO-CANONICAL-001",
        "first_name": "Olivia",
        "last_name": "Chen",
        "date_of_birth": date(1998, 1, 15),
        "sex": "unknown",
        "source": "SIGNAL_DEMO",
        "source_resource": "Patient",
    },
    {
        "patient_id": UUID("fbe3a1e0-0000-4000-8000-000000000002"),
        "source_patient_id": "SIGNAL-DEMO-CANONICAL-002",
        "first_name": "Priya",
        "last_name": "Shah",
        "date_of_birth": date(2004, 6, 21),
        "sex": "unknown",
        "source": "SIGNAL_DEMO",
        "source_resource": "Patient",
    },
    {
        "patient_id": UUID("fbe3a1e0-0000-4000-8000-000000000003"),
        "source_patient_id": "SIGNAL-DEMO-CANONICAL-003",
        "first_name": "Ethan",
        "last_name": "Brooks",
        "date_of_birth": date(1976, 11, 9),
        "sex": "unknown",
        "source": "SIGNAL_DEMO",
        "source_resource": "Patient",
    },
)


def upgrade() -> None:
    connection = op.get_bind()
    patients = sa.Table("patients", sa.MetaData(), autoload_with=connection)
    connection.execute(
        postgresql.insert(patients).values(PATIENTS).on_conflict_do_nothing()
    )


def downgrade() -> None:
    connection = op.get_bind()
    patients = sa.Table("patients", sa.MetaData(), autoload_with=connection)
    connection.execute(
        sa.delete(patients).where(
            patients.c.source == "SIGNAL_DEMO",
            patients.c.source_patient_id.in_(
                [row["source_patient_id"] for row in PATIENTS]
            ),
        )
    )
