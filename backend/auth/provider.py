"""JWT verification boundary for CampusShield's local/Neon deployment."""

from abc import ABC, abstractmethod
from typing import Any
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from backend.config import ALGORITHM, SECRET_KEY

class BaseAuthProvider(ABC):
    @abstractmethod
    def verify_token(self, token: str, db: Session) -> dict[str, Any]:
        """Validate a token and return its trusted claims."""

class LocalJWTAuthProvider(BaseAuthProvider):
    def verify_token(self, token: str, db: Session) -> dict[str, Any]:
        try:
            claims = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except JWTError as exc:
            raise ValueError("JWT verification failed") from exc
        if not claims.get("sub") or not claims.get("tenant_id"):
            raise ValueError("JWT is missing required identity claims")
        return claims

def get_auth_provider() -> BaseAuthProvider:
    return LocalJWTAuthProvider()
