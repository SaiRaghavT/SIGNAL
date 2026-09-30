from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config.settings import settings


DATABASE_URL = (
    f"postgresql+psycopg2://"
    f"{settings.db_user}:{settings.db_password}"
    f"@{settings.db_host}:{settings.db_port}"
    f"/{settings.db_name}"
)

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()