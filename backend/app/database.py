from collections.abc import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args=connect_args,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_lightweight_migrations()


def _apply_lightweight_migrations() -> None:
    inspector = inspect(engine)

    if inspector.has_table("issue_summaries"):
        existing_columns = {column["name"] for column in inspector.get_columns("issue_summaries")}
        additions = {
            "importance": "VARCHAR(20)",
            "key_points_json": "TEXT",
            "research_value": "TEXT",
            "tracking_keywords_json": "TEXT",
        }
        for column_name, column_type in additions.items():
            if column_name in existing_columns:
                continue
            with engine.begin() as connection:
                connection.exec_driver_sql(
                    f"ALTER TABLE issue_summaries ADD COLUMN {column_name} {column_type}"
                )
