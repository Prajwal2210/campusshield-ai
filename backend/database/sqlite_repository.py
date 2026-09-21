"""
CampusShield AI — SQLite Repository Implementation
===================================================
Implementation of BaseRepository for local development using SQLAlchemy & SQLite.
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from backend.database.abstract import BaseRepository
from backend.database import crud


class SQLiteRepository(BaseRepository):
    """Local SQLite repository wrapper around SQLAlchemy CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    # Users & Tenants
    def get_user_by_username(self, username: str) -> Optional[Any]:
        return crud.get_user_by_username(self.db, username)

    def create_user(self, username: str, email: str, hashed_password: str, full_name: str = "", role: str = "analyst", tenant_id: str = "tenant-default") -> Any:
        return crud.create_user(self.db, username, email, hashed_password, full_name, role, tenant_id)

    def list_users(self, tenant_id: Optional[str] = None) -> List[Any]:
        return crud.list_users(self.db, tenant_id)

    # Sessions
    def create_session(self, name: str, source_type: str, user_id: Optional[int] = None, scenario: Optional[str] = None, file_path: Optional[str] = None, file_size_bytes: Optional[int] = None, tenant_id: str = "tenant-default") -> Any:
        return crud.create_session(self.db, name, source_type, user_id, scenario, file_path, file_size_bytes, tenant_id)

    def get_session(self, session_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        return crud.get_session(self.db, session_id, tenant_id)

    def list_sessions(self, limit: int = 50, offset: int = 0, tenant_id: Optional[str] = None) -> List[Any]:
        return crud.list_sessions(self.db, limit, offset, tenant_id)

    def update_session_status(self, session_id: int, status: str, packet_count: Optional[int] = None, flow_count: Optional[int] = None, duration_seconds: Optional[float] = None, traffic_stats: Optional[dict] = None, error_message: Optional[str] = None, tenant_id: Optional[str] = None) -> None:
        crud.update_session_status(self.db, session_id, status, packet_count, flow_count, duration_seconds, traffic_stats, error_message, tenant_id)

    # Alerts
    def create_alert(self, session_id: int, title: str, severity: str, threat_score: float, threat_category: Optional[str] = None, description: Optional[str] = None, confidence: Optional[float] = None, tenant_id: str = "tenant-default", **kwargs) -> Any:
        return crud.create_alert(
            self.db,
            session_id=session_id,
            title=title,
            severity=severity,
            threat_score=threat_score,
            threat_category=threat_category,
            description=description,
            confidence=confidence,
            tenant_id=tenant_id,
            **kwargs
        )

    def get_alert(self, alert_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        return crud.get_alert(self.db, alert_id, tenant_id)

    def list_alerts(self, severity: Optional[str] = None, status: Optional[str] = None, session_id: Optional[int] = None, limit: int = 100, offset: int = 0, tenant_id: Optional[str] = None) -> List[Any]:
        return crud.list_alerts(self.db, severity, status, session_id, limit, offset, tenant_id)

    def get_alert_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        return crud.get_alert_stats(self.db, tenant_id)

    def acknowledge_alert(self, alert_id: int, username: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        return crud.acknowledge_alert(self.db, alert_id, username, tenant_id)

    # Reports
    def create_report(self, session_id: int, file_path: str, generated_by: Optional[str] = None, file_size_bytes: Optional[int] = None, tenant_id: str = "tenant-default") -> Any:
        return crud.create_report(self.db, session_id=session_id, file_path=file_path, generated_by=generated_by, file_size_bytes=file_size_bytes, tenant_id=tenant_id)

    def get_report(self, report_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        return crud.get_report(self.db, report_id, tenant_id)

    def list_reports(self, limit: int = 50, tenant_id: Optional[str] = None) -> List[Any]:
        return crud.list_reports(self.db, limit, tenant_id)
