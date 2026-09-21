"""Tenant-safe local artifact storage for generated reports and uploads."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from backend.config import REPORT_DIR, UPLOAD_DIR


class BaseStorageService(ABC):
    @abstractmethod
    def save_file(self, file_content: bytes, destination_name: str, category: str = "reports") -> str:
        pass

    @abstractmethod
    def get_file_path(self, relative_name: str, category: str = "reports") -> Optional[Path]:
        pass


class LocalStorageService(BaseStorageService):
    def save_file(self, file_content: bytes, destination_name: str, category: str = "reports") -> str:
        target_dir = REPORT_DIR if category == "reports" else UPLOAD_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / Path(destination_name).name
        path.write_bytes(file_content)
        return str(path)

    def get_file_path(self, relative_name: str, category: str = "reports") -> Optional[Path]:
        target_dir = REPORT_DIR if category == "reports" else UPLOAD_DIR
        path = target_dir / Path(relative_name).name
        return path if path.exists() else None


def get_storage_service() -> BaseStorageService:
    return LocalStorageService()
