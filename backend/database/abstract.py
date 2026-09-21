"""
CampusShield AI — Abstract Repository Interface
===============================================
Abstract Data Access Object (DAO) interface defining clean database operations.
Decouples business logic from specific persistence implementations (SQLite vs. DynamoDB).
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any


class BaseRepository(ABC):
    """Abstract Repository interface for all database entities."""

    # Users & Tenants
    @abstractmethod
    def get_user_by_username(self, username: str) -> Optional[Any]:
        pass

    @abstractmethod
    def create_user(self, username: str, email: str, hashed_password: str, full_name: str = "", role: str = "analyst", tenant_id: str = "tenant-default") -> Any:
        pass

    @abstractmethod
    def list_users(self, tenant_id: Optional[str] = None) -> List[Any]:
        pass

    # Sessions
    @abstractmethod
    def create_session(self, name: str, source_type: str, user_id: Optional[int] = None, scenario: Optional[str] = None, file_path: Optional[str] = None, file_size_bytes: Optional[int] = None, tenant_id: str = "tenant-default") -> Any:
        pass

    @abstractmethod
    def get_session(self, session_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        pass

    @abstractmethod
    def list_sessions(self, limit: int = 50, offset: int = 0, tenant_id: Optional[str] = None) -> List[Any]:
        pass

    @abstractmethod
    def update_session_status(self, session_id: int, status: str, packet_count: Optional[int] = None, flow_count: Optional[int] = None, duration_seconds: Optional[float] = None, traffic_stats: Optional[dict] = None, error_message: Optional[str] = None, tenant_id: Optional[str] = None) -> None:
        pass

    # Alerts
    @abstractmethod
    def create_alert(self, session_id: int, title: str, severity: str, threat_score: float, threat_category: Optional[str] = None, description: Optional[str] = None, confidence: Optional[float] = None, tenant_id: str = "tenant-default", **kwargs) -> Any:
        pass

    @abstractmethod
    def get_alert(self, alert_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        pass

    @abstractmethod
    def list_alerts(self, severity: Optional[str] = None, status: Optional[str] = None, session_id: Optional[int] = None, limit: int = 100, offset: int = 0, tenant_id: Optional[str] = None) -> List[Any]:
        pass

    @abstractmethod
    def get_alert_stats(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        pass

    @abstractmethod
    def acknowledge_alert(self, alert_id: int, username: str, tenant_id: Optional[str] = None) -> Optional[Any]:
        pass

    # Reports
    @abstractmethod
    def create_report(self, session_id: int, file_path: str, generated_by: Optional[str] = None, file_size_bytes: Optional[int] = None, tenant_id: str = "tenant-default") -> Any:
        pass

    @abstractmethod
    def get_report(self, report_id: int, tenant_id: Optional[str] = None) -> Optional[Any]:
        pass

    @abstractmethod
    def list_reports(self, limit: int = 50, tenant_id: Optional[str] = None) -> List[Any]:
        pass
