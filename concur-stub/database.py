from __future__ import annotations

"""
database.py
-----------
SQLAlchemy engine, shared metadata, session factory, and the FastAPI
dependency that injects a database session into route handlers.

Design notes:
- Uses SQLAlchemy 2.x with SQLite.
- check_same_thread=False is required for SQLite when used with FastAPI's
  threaded request handling.
- The `get_db` dependency yields a session and guarantees it is closed
  after the request completes, even on error.
- All SQLAlchemy model Table objects must be imported before
  Base.metadata.create_all() is called — this is done in main.py lifespan.
"""

from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from config import settings


# ------------------------------------------------------------------ #
# Engine                                                               #
# ------------------------------------------------------------------ #

engine = create_engine(
    f"sqlite:///{settings.db_path}",
    connect_args={"check_same_thread": False},
    # Echo SQL statements in development — set to False in production.
    echo=False,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    """
    Enable WAL mode and foreign key enforcement for every new SQLite connection.

    WAL (Write-Ahead Logging) improves concurrent read performance.
    Foreign keys are NOT enforced by SQLite by default — this pragma enables them.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# ------------------------------------------------------------------ #
# Session factory                                                      #
# ------------------------------------------------------------------ #

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ------------------------------------------------------------------ #
# Declarative base                                                     #
# ------------------------------------------------------------------ #

class Base(DeclarativeBase):
    """
    Shared declarative base for all SQLAlchemy ORM models.
    All model files import this Base and define their Table via it.
    """
    pass


# ------------------------------------------------------------------ #
# FastAPI dependency                                                   #
# ------------------------------------------------------------------ #

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a SQLAlchemy Session per request.

    Usage in a route handler:
        def my_route(db: Session = Depends(get_db)):
            ...

    The session is always closed in the finally block, guaranteeing
    no connection leaks even when an exception is raised.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
