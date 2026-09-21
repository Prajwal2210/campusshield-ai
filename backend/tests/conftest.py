"""
Pytest configuration: set required environment variables BEFORE any
backend module is imported during test collection.

These values are intentionally fake — unit tests that need a real DB
use in-memory SQLite directly (see test_tenant_isolation.py).
A live integration test suite should override these via a real .env.
"""
import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://test:test@localhost/campusshield_test",
)
os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test-secret-key-for-unit-tests-only-minimum-32-chars",
)
