"""
CampusShield AI — Database Connection
======================================
Engine creation, session factory, and table initialization.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from backend.config import DATABASE_URL
from backend.database.models import Base


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_pre_ping=True,
)


# ---------------------------------------------------------------------------
# Session Factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db():
    """
    FastAPI dependency that yields a database session and ensures
    proper cleanup regardless of success or failure.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_db_context() -> Session:
    """
    Context manager for non-FastAPI usage (background tasks, CLI, tests).
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------
def init_db():
    """Create the PostgreSQL schema from the current SQLAlchemy models."""
    Base.metadata.create_all(bind=engine)


def drop_db():
    """Drop all tables — use only in tests."""
    Base.metadata.drop_all(bind=engine)
