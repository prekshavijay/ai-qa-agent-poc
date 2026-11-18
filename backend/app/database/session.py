"""SQLAlchemy engine and session setup.

Uses SQLite for the local POC. Swap DATABASE_URL to a PostgreSQL DSN
(e.g. postgresql+psycopg2://...) when migrating — no code changes required
beyond installing the appropriate DB driver.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def _build_engine_kwargs() -> dict:
    kwargs: dict = {"echo": settings.debug}
    if settings.is_sqlite:
        # Required for SQLite + FastAPI (multi-threaded request handling)
        kwargs["connect_args"] = {"check_same_thread": False}
    return kwargs


engine = create_engine(settings.database_url, **_build_engine_kwargs())


if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and closes it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables. Safe to call on startup for the local POC."""
    # Import models so metadata is registered before create_all
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    logger.info("Database initialized (%s)", "sqlite" if settings.is_sqlite else "other")
