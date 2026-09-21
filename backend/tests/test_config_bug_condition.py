"""
Bug Condition Exploration Tests (Task 1 / Property 1).

These tests surface the three concrete failing cases that demonstrate the
root-cause bug: backend.config raises RuntimeError at import time when
DATABASE_URL or JWT_SECRET_KEY are absent or invalid.

After conftest.py sets the env vars, importlib.reload(backend.config) can
be used within a patched environment to verify the exact error messages.

NOTE: The tests in this file VALIDATE the fix — they assert that:
  - Valid env vars → no exception
  - Missing DATABASE_URL → RuntimeError
  - SQLite DATABASE_URL → RuntimeError
  - Missing JWT_SECRET_KEY → RuntimeError
"""

import importlib
import os
from unittest.mock import patch

import pytest


def _reload_config(env: dict):
    """
    Reload backend.config inside a clean patched environment.
    Returns the reloaded module or re-raises the exception.
    """
    import backend.config as cfg_module
    with patch.dict(os.environ, env, clear=True):
        return importlib.reload(cfg_module)


class TestConfigBugCondition:
    """Property 1: Config Import Fails Without Required Environment Variables."""

    def test_valid_env_does_not_raise(self):
        """Bug fix: valid DATABASE_URL + JWT_SECRET_KEY must not raise."""
        env = {
            "DATABASE_URL": "postgresql+psycopg://user:pass@host/db?sslmode=require",
            "JWT_SECRET_KEY": "a-sufficiently-long-random-secret-value-here",
        }
        # Should not raise
        _reload_config(env)

    def test_missing_database_url_raises_runtime_error(self):
        """Defect 1.1 / 1.2: Missing DATABASE_URL → RuntimeError at import time."""
        env = {
            "JWT_SECRET_KEY": "a-sufficiently-long-random-secret-value-here",
            # DATABASE_URL absent
        }
        with pytest.raises(RuntimeError, match="DATABASE_URL must contain the Neon PostgreSQL connection string"):
            _reload_config(env)

    def test_sqlite_url_raises_runtime_error(self):
        """Defect 1.4: SQLite DATABASE_URL → RuntimeError with clear rejection message."""
        env = {
            "DATABASE_URL": "sqlite:///./dev.db",
            "JWT_SECRET_KEY": "a-sufficiently-long-random-secret-value-here",
        }
        with pytest.raises(RuntimeError, match="SQLite is legacy data only"):
            _reload_config(env)

    def test_missing_jwt_secret_raises_runtime_error(self):
        """Defect 1.3: Missing JWT_SECRET_KEY → RuntimeError at import time."""
        env = {
            "DATABASE_URL": "postgresql+psycopg://user:pass@host/db?sslmode=require",
            "JWT_SECRET_KEY": "",
        }
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY must be set to a long random secret"):
            _reload_config(env)

    @pytest.mark.parametrize("url", [
        "postgresql://user:pass@host/db",
        "postgresql+psycopg://user:pass@host/db?sslmode=require",
        "postgresql+psycopg://user:pass@ep-xxx.us-east-2.aws.neon.tech/neondb?sslmode=require",
    ])
    def test_all_valid_postgresql_schemes_accepted(self, url):
        """Property 1 extended: any valid postgresql:// or postgresql+psycopg:// URL is accepted."""
        env = {
            "DATABASE_URL": url,
            "JWT_SECRET_KEY": "a-sufficiently-long-random-secret-value-here",
        }
        _reload_config(env)  # must not raise

    @pytest.mark.parametrize("url", [
        "mysql://user:pass@host/db",
        "sqlite:///./campusshield.db",
        "mongodb://user:pass@host/db",
        "",
    ])
    def test_non_postgresql_urls_are_rejected(self, url):
        """Property 1 extended: any non-postgresql URL must raise RuntimeError."""
        env = {
            "DATABASE_URL": url,
            "JWT_SECRET_KEY": "a-sufficiently-long-random-secret-value-here",
        }
        with pytest.raises(RuntimeError):
            _reload_config(env)
