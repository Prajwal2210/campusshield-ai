"""
CampusShield AI — Database Repository Factory
=============================================
Repository factory for the active PostgreSQL-backed SQLAlchemy implementation.
"""

from sqlalchemy.orm import Session

from backend.database.abstract import BaseRepository
from backend.database.sqlite_repository import SQLiteRepository


def get_repository(db_session: Session) -> BaseRepository:
    """
    Return the SQLAlchemy repository used with Neon PostgreSQL.  The class's
    historical name is retained only to avoid a pointless import-breaking move.
    """
    return SQLiteRepository(db_session)
