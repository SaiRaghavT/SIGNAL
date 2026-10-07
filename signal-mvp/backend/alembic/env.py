from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from backend.app.config.settings import settings
from backend.app.models.base import Base
from backend.app.models import (
    Patient,
    Encounter,
    Condition,
    Observation,
    LabResult,
    ClinicalDocument,
    Case,
    Submission,
    AuditEvent,
    DeadlineEscalation,
    Candidate,
    CaseWorkflowRecord,
    Report,
    Acknowledgement,
    SubmissionAttempt,
    DemoCaseBaseline,
)

# Alembic Config object
config = context.config


# Configure logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# Register all SIGNAL models with SQLAlchemy metadata.
#
# Importing the models above ensures that their tables
# are registered in Base.metadata before Alembic runs.
target_metadata = Base.metadata


def get_database_url() -> str:
    """
    Build the PostgreSQL connection URL from SIGNAL settings.
    """

    return (
        f"postgresql+psycopg2://"
        f"{settings.db_user}:"
        f"{settings.db_password}@"
        f"{settings.db_host}:"
        f"{settings.db_port}/"
        f"{settings.db_name}"
    )


def run_migrations_offline() -> None:
    """
    Run migrations without creating a database connection.
    """

    url = get_database_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations using an active database connection.
    """

    configuration = config.get_section(
        config.config_ini_section,
        {},
    )

    configuration["sqlalchemy.url"] = get_database_url()

    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
