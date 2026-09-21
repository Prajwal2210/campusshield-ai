# CampusShield PostgreSQL Migration — Bugfix Design

## Overview

The application cannot start because `backend/config.py` raises `RuntimeError` at import time when `DATABASE_URL` or `JWT_SECRET_KEY` are absent from the process environment. These values are loaded exclusively from a `.env` file at the project root via `python-dotenv`, which is never loaded automatically — it must be explicitly called before the module is imported, or the file must exist before the process starts.

The fix is entirely **operational / configuration**: create a `.env` file from the provided `.env.example` template, populate it with the Neon PostgreSQL connection string and a strong JWT secret, and (optionally) the four `INITIAL_ADMIN_*` variables to bootstrap an admin account. No code changes are required. The application code is correct and complete; only the runtime environment is missing.

This document formalizes the bug condition, defines the expected behavior, traces the startup sequence that is blocked, and specifies the verification checklist that confirms the fix is effective.

---

## Glossary

- **Bug_Condition (C)**: The condition that triggers the bug — the process environment is missing `DATABASE_URL` or `JWT_SECRET_KEY` when `backend/config.py` is imported.
- **Property (P)**: The desired behavior when the condition is met — the application starts, connects to Neon, creates the PostgreSQL schema, and seeds the admin account.
- **Preservation**: All behaviors present before the migration (JWT validation, tenant isolation, detection pipeline, alerts, reports, WebSocket) that must remain unchanged after the `.env` file is created.
- **`backend/config.py`**: Module-level validation of required environment variables. Raises `RuntimeError` immediately on import if either variable is missing or invalid.
- **`python-dotenv`**: The library (via `load_dotenv()`) that reads a `.env` file and injects its key-value pairs into `os.environ` before any application module reads `os.getenv()`.
- **`init_db()`**: Function in `backend/database/connection.py` that calls `Base.metadata.create_all(bind=engine)` to create all PostgreSQL tables idempotently.
- **`seed_demo_users()`**: Function in `backend/auth/security.py` that creates `tenant-default` and a bootstrap admin user on first run.
- **`DEMO_USERS`**: Config-level list populated from `INITIAL_ADMIN_*` env vars; empty list means no admin is seeded.
- **`conftest.py`**: Pytest fixture file that must set `DATABASE_URL` and `JWT_SECRET_KEY` in the environment **before** any test imports `backend.config`, enabling unit tests to run without a live Neon connection.
- **Neon PostgreSQL**: The serverless PostgreSQL provider targeted by `DATABASE_URL`; URL scheme is `postgresql+psycopg://`.

---

## Bug Details

### Bug Condition

The bug manifests at Python import time. When any code path that imports `backend.config` (directly or transitively through `backend.database.connection`, `backend.auth.security`, `backend.main`, etc.) executes in a process where `DATABASE_URL` or `JWT_SECRET_KEY` are absent from `os.environ`, Python raises a `RuntimeError` and the entire process terminates before any route, database session, lifespan hook, or test can execute.

**Formal Specification:**

```
FUNCTION isBugCondition(env)
  INPUT: env — the process environment (os.environ) at import time
  OUTPUT: boolean

  database_url  := env.get("DATABASE_URL", "").strip()
  jwt_secret    := env.get("JWT_SECRET_KEY", "").strip()

  missing_db    := (database_url == "")
  invalid_db    := NOT (database_url.startswith("postgresql://") OR
                        database_url.startswith("postgresql+psycopg://"))
  missing_jwt   := (jwt_secret == "")

  RETURN missing_db OR invalid_db OR missing_jwt
END FUNCTION
```

### Examples

| Scenario | `DATABASE_URL` | `JWT_SECRET_KEY` | Result |
|---|---|---|---|
| No `.env` file | *(absent)* | *(absent)* | `RuntimeError: DATABASE_URL must contain the Neon PostgreSQL connection string` |
| `.env` exists, `DATABASE_URL` empty | `""` | `"mysecret"` | `RuntimeError: DATABASE_URL must contain…` |
| SQLite URL provided | `"sqlite:///./dev.db"` | `"mysecret"` | `RuntimeError: DATABASE_URL must use a PostgreSQL/Neon URL; SQLite is legacy data only` |
| Valid DB URL, JWT missing | `"postgresql+psycopg://…"` | `""` | `RuntimeError: JWT_SECRET_KEY must be set to a long random secret` |
| Both valid | `"postgresql+psycopg://…"` | `"long-secret"` | App starts, schema created, seeding attempted |

---

## Expected Behavior

### Preservation Requirements

The following behaviors are already implemented correctly and must remain unchanged after the fix is applied:

**Unchanged Behaviors:**
- `POST /api/auth/login` authenticates against the Neon `users` table, returns a signed JWT containing `sub`, `role`, and `tenant_id`.
- `POST /api/auth/signup` creates a new tenant and analyst user; works without `INITIAL_ADMIN_*` vars.
- `POST /api/auth/register` (admin-only) adds a user under the admin's own tenant.
- JWT validation via `LocalJWTAuthProvider.verify_token` extracts `sub` and `tenant_id`, enforcing tenant isolation on all CRUD operations.
- All CRUD functions in `backend/database/crud.py` filter by `tenant_id` on every query.
- The detection pipeline (Isolation Forest + rule-based classification) persists `DetectionResult`, `ContributingFactor`, and `Alert` rows to PostgreSQL.
- `GET /api/alerts` returns only alerts for the authenticated user's tenant.
- WebSocket `/ws/alerts?token=JWT` accepts connections and streams real-time alerts.
- `POST /api/reports/{session_id}` generates a PDF and persists a `Report` row.
- `backend/data/campusshield.db` remains untouched as a legacy reference file.
- `GET /health` returns HTTP 200 with `{"status": "healthy"}` without authentication.
- The Vite frontend proxies `/api` and `/ws` to `http://localhost:8000` unchanged.

**Scope:**
All inputs that do NOT involve the missing `.env` configuration (i.e., any request to a running application) are completely unaffected by this fix.

---

## Hypothesized Root Cause

The root cause is a single missing file: `.env` at the project root. The following chain explains why this alone blocks the entire application:

1. **`python-dotenv` must be invoked before any module import**: `load_dotenv()` reads `.env` and injects vars into `os.environ`. If this never runs (because there is no `.env` and no explicit call), `os.getenv()` returns empty strings.

2. **`backend/config.py` validates at module level, not at call time**: The `RuntimeError` guards are at the top-level module scope, not inside a function. This means the error fires the instant Python imports the module — before any FastAPI app object, lifespan, or route handler is created.

3. **The import chain is wide**: `backend/main.py` → `backend/database/connection.py` → `backend/config.py`. Any test that does `from backend.detection.xxx import ...` without also importing `backend.config` may appear to work, but any test importing `backend.database.connection`, `backend.auth.security`, or `backend.main` will fail immediately.

4. **`conftest.py` is absent**: There is no `conftest.py` that sets the required environment variables before the test collection phase. Pytest collects tests by importing them; this triggers `backend.config` import, which raises before any test function runs.

5. **`.env.example` exists but is never automatically copied**: The template is present but requires a manual operator action. No startup script, Makefile target, or CI step performs this copy automatically.

---

## Correctness Properties

Property 1: Bug Condition — Config Import Succeeds With Valid Environment

_For any_ process environment where `DATABASE_URL` is a non-empty string starting with `postgresql://` or `postgresql+psycopg://` and `JWT_SECRET_KEY` is a non-empty string, importing `backend.config` SHALL NOT raise any exception, and the module-level constants `DATABASE_URL`, `SECRET_KEY`, and `DEMO_USERS` SHALL be populated with the provided values.

**Validates: Requirements 2.1, 2.2, 2.3**

Property 2: Bug Condition — Schema Creation Is Idempotent

_For any_ PostgreSQL (or SQLite in-memory) database, calling `init_db()` one or more times SHALL create all nine tables (`tenants`, `users`, `traffic_sessions`, `detection_results`, `contributing_factors`, `alerts`, `detection_config`, `audit_logs`, `reports`) on the first call and SHALL NOT raise an exception, drop any table, or alter any existing row on subsequent calls.

**Validates: Requirements 2.4**

Property 3: Bug Condition — Admin Seeding Is Conditional and Idempotent

_For any_ combination of `INITIAL_ADMIN_*` environment variables, `seed_demo_users()` SHALL seed exactly one admin user when all four variables (`INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_FULLNAME`) are non-empty, and SHALL seed zero users when any of the four is absent or empty. Calling `seed_demo_users()` multiple times on the same database SHALL NOT create duplicate users.

**Validates: Requirements 2.5, 1.6**

Property 4: Preservation — Non-Config Behaviors Are Unchanged

_For any_ request to a running application where the bug condition does NOT hold (i.e., a valid `.env` is present and the application has started), every existing behavior — authentication, tenant isolation, detection, alerts, reports, WebSocket, health check — SHALL produce the same result as documented in the bugfix.md Unchanged Behavior clauses 3.1–3.10.

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10**

---

## Fix Implementation

### Changes Required

This is a **configuration-only fix**. No Python source files need to be modified.

---

**File**: `.env` (create at project root by copying `.env.example`)

**Action**: Create this file with real values before starting the application.

**Specific Steps:**

1. **Copy the template**
   ```
   cp .env.example .env        # Linux / macOS / Git Bash
   copy .env.example .env      # Windows CMD
   ```

2. **Set `DATABASE_URL`** — obtain the connection string from the Neon dashboard:
   - Project → Connection Details → Connection string
   - Format: `postgresql+psycopg://USER:PASSWORD@ep-xxx.region.aws.neon.tech/DBNAME?sslmode=require`
   - Replace the placeholder in `.env`

3. **Set `JWT_SECRET_KEY`** — generate a cryptographically strong secret:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Paste the output as the value in `.env`.

4. **Set `INITIAL_ADMIN_*` (optional but recommended for first login)**:
   ```dotenv
   INITIAL_ADMIN_USERNAME=admin
   INITIAL_ADMIN_PASSWORD=ChangeMe2024!
   INITIAL_ADMIN_EMAIL=admin@campusshield.local
   INITIAL_ADMIN_FULLNAME=CampusShield Administrator
   ```
   If these are omitted, the admin account will not be seeded and the operator must use `POST /api/auth/signup` to create the first account.

5. **Ensure `python-dotenv` is installed** and loaded before startup:
   ```bash
   pip install python-dotenv
   ```
   Verify that `backend/main.py` or the application entry point calls `load_dotenv()` before importing any backend module, or use `uvicorn` with an `.env` file loader, or ensure the variables are set in the shell environment directly.

   > **Note**: If `load_dotenv()` is not already called at the entry point, add the following as the very first lines of `backend/main.py` (before all other imports):
   > ```python
   > from dotenv import load_dotenv
   > load_dotenv()  # loads .env from the project root
   > ```

6. **Verify `conftest.py` for tests** — create `backend/tests/conftest.py` to set env vars before pytest imports backend modules:
   ```python
   import os
   os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost/test")
   os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
   ```
   This allows all tests that only import non-database modules (features, detection, scoring) to run without a live connection. Tests that need a real database session should use the existing in-memory SQLite pattern from `test_tenant_isolation.py`.

---

## Testing Strategy

### Validation Approach

The testing strategy follows a two-phase approach: first, surface counterexamples that demonstrate the bug on an environment without `.env`, then verify the fix works correctly and preserves all existing behavior after `.env` is created.

---

### Exploratory Bug Condition Checking

**Goal**: Surface counterexamples that demonstrate the bug BEFORE creating `.env`. Confirm the root cause analysis: `backend/config.py` raises `RuntimeError` at import time.

**Test Plan**: In a clean shell with no `DATABASE_URL` or `JWT_SECRET_KEY` in the environment, attempt to import `backend.config` and observe the exception. Attempt `pytest` without `conftest.py` and observe collection-time failures.

**Test Cases**:

1. **Missing DATABASE_URL** (will fail without `.env`):
   ```bash
   python -c "import backend.config"
   # Expected: RuntimeError: DATABASE_URL must contain the Neon PostgreSQL connection string
   ```

2. **SQLite URL rejection** (will fail without valid PostgreSQL URL):
   ```bash
   DATABASE_URL=sqlite:///./dev.db JWT_SECRET_KEY=x python -c "import backend.config"
   # Expected: RuntimeError: DATABASE_URL must use a PostgreSQL/Neon URL; SQLite is legacy data only
   ```

3. **Missing JWT_SECRET_KEY** (will fail without secret):
   ```bash
   DATABASE_URL=postgresql+psycopg://u:p@host/db JWT_SECRET_KEY="" python -c "import backend.config"
   # Expected: RuntimeError: JWT_SECRET_KEY must be set to a long random secret
   ```

4. **pytest without conftest.py** (will fail at collection time):
   ```bash
   pytest backend/tests/test_detection.py
   # Expected: ERROR collecting — RuntimeError during import of backend.config
   ```

**Expected Counterexamples**:
- The `RuntimeError` from `backend/config.py` surfaces at import time, not at test function execution time.
- Possible causes confirmed: missing `.env` file, no `conftest.py` setting env vars before collection.

---

### Fix Checking

**Goal**: Verify that for all inputs where the bug condition holds (missing/invalid env vars), the corrected environment (`.env` file present with valid values) produces the expected behavior.

**Pseudocode:**

```
FOR ALL env WHERE isBugCondition(env) DO
  fix := create_env_file_with_valid_values()
  result := import_backend_config_with(fix)
  ASSERT result.DATABASE_URL starts with "postgresql"
  ASSERT result.SECRET_KEY is non-empty
  ASSERT no RuntimeError raised
END FOR
```

---

### Preservation Checking

**Goal**: Verify that for all inputs where the bug condition does NOT hold (valid `.env` present, application running), the application produces the same results as all Unchanged Behavior clauses (3.1–3.10).

**Pseudocode:**

```
FOR ALL request WHERE NOT isBugCondition(env) DO
  ASSERT behavior(request, fixed_app) == behavior(request, pre_migration_spec)
END FOR
```

**Testing Approach**: Property-based testing is recommended for preservation checking because:
- It generates many test cases automatically across the tenant, user, and traffic input space.
- It catches edge cases (e.g., empty tenant ID, large PCAP files, concurrent WebSocket connections) that manual tests miss.
- It provides strong guarantees that all `tenant_id` filtering invariants hold across random inputs.

**Test Plan**: Confirm each preservation behavior individually after creating `.env`, then write property-based tests for the tenant isolation invariant (already partially covered by `test_tenant_isolation.py`).

**Test Cases**:

1. **JWT Authentication Preservation**: POST to `/api/auth/login` with seeded admin credentials returns HTTP 200 and a valid JWT.
2. **Tenant Isolation Preservation**: Alerts/sessions created by Tenant A are never returned to Tenant B queries (existing `test_tenant_isolation.py` covers this).
3. **Health Check Preservation**: `GET /health` returns `{"status": "healthy"}` with no authentication.
4. **Schema Idempotency**: Start the application twice; `create_all()` on second startup does not drop or corrupt data from the first run.

---

### Unit Tests

- Test that `backend.config` imports without exception when all required env vars are set (mock `os.environ` in test).
- Test that `DEMO_USERS` is empty when any `INITIAL_ADMIN_*` variable is missing.
- Test that `DEMO_USERS` contains exactly one admin entry when all four `INITIAL_ADMIN_*` variables are set.
- Test `init_db()` idempotency using an in-memory SQLite engine (same pattern as `test_tenant_isolation.py`).
- Test `seed_demo_users()` does not create duplicate users when called twice on the same session.

### Property-Based Tests

- Generate random valid PostgreSQL URL strings and assert `backend.config` accepts them without raising.
- Generate random non-PostgreSQL URL strings (SQLite, MySQL, blank) and assert `backend.config` raises `RuntimeError`.
- Generate random `INITIAL_ADMIN_*` combinations (all set, one missing, all missing) and assert `DEMO_USERS` length is 0 or 1 accordingly.
- Generate random pairs of tenant IDs and assert CRUD queries for Tenant A never return rows belonging to Tenant B (extending existing property tests in `test_tenant_isolation.py`).

### Integration Tests

- Full startup test: with a valid `.env` pointing to a test Neon instance (or a local PostgreSQL container), start the application and assert `GET /health` returns HTTP 200.
- Schema creation test: after `init_db()`, query `information_schema.tables` and assert all nine expected tables exist.
- Admin seeding integration test: with `INITIAL_ADMIN_*` set, call `seed_demo_users()` and then `POST /api/auth/login` with those credentials; assert HTTP 200 and JWT returned.
- Idempotency integration test: call `init_db()` and `seed_demo_users()` twice in sequence; assert no duplicate tenant or user rows, no exceptions.

---

## .env Setup Instructions for Operators

### Step 1: Copy the Template

```bash
# From the project root:
cp .env.example .env
```

### Step 2: Obtain Neon PostgreSQL Connection String

1. Log into [console.neon.tech](https://console.neon.tech).
2. Select your project (or create a new one).
3. Go to **Connection Details** and copy the **Connection string**.
4. It should look like:
   ```
   postgresql://username:password@ep-xxx-yyy.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
5. Change the scheme to `postgresql+psycopg` (required by SQLAlchemy with the `psycopg` driver):
   ```
   postgresql+psycopg://username:password@ep-xxx-yyy.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
6. Paste this as the value of `DATABASE_URL` in `.env`.

### Step 3: Generate a JWT Secret

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Paste the output as `JWT_SECRET_KEY` in `.env`. It must be at least 32 characters long.

### Step 4: Set Bootstrap Admin (Recommended)

Uncomment and fill in the four `INITIAL_ADMIN_*` lines in `.env`:

```dotenv
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=YourStrongPassword123!
INITIAL_ADMIN_EMAIL=admin@yourdomain.com
INITIAL_ADMIN_FULLNAME=CampusShield Administrator
```

If omitted, use `POST /api/auth/signup` after startup to create the first account (it will be an analyst; upgrade via DB or admin endpoint).

### Step 5: Ensure `load_dotenv()` Is Called

Verify that `backend/main.py` begins with:

```python
from dotenv import load_dotenv
load_dotenv()
```

These two lines must appear **before** any import of `backend.config` or any other backend module.

### Step 6: Start the Application

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

On first start, the log will show:
```
Database initialized
Demo users seeded (admin/analyst)
CampusShield AI ready
```

---

## Verification Checklist

After creating `.env` and starting the application, verify the following endpoints in order:

| # | Test | Expected Result |
|---|------|----------------|
| 1 | `GET /health` | HTTP 200, `{"status": "healthy"}` |
| 2 | `GET /` | HTTP 200, returns API name and version |
| 3 | `GET /docs` | HTTP 200, Swagger UI loads |
| 4 | `POST /api/auth/login` with `INITIAL_ADMIN_*` credentials | HTTP 200, JWT returned |
| 5 | `GET /api/alerts` with JWT in `Authorization: Bearer` header | HTTP 200, empty list `[]` (no alerts yet) |
| 6 | `POST /api/detection/simulate` with JWT | HTTP 200, detection session created |
| 7 | `GET /api/alerts` with JWT | HTTP 200, list contains alerts from simulation |
| 8 | `POST /api/reports/{session_id}` with JWT | HTTP 200, PDF report generated |
| 9 | WebSocket `ws://localhost:8000/ws/alerts?token=JWT` | Connection accepted, `{"type": "connected"}` message received |
| 10 | Check Neon dashboard Tables tab | All 9 tables present: `tenants`, `users`, `traffic_sessions`, `detection_results`, `contributing_factors`, `alerts`, `detection_config`, `audit_logs`, `reports` |
| 11 | Run `pytest backend/tests/` | All existing tests pass (unit/property tests use in-memory SQLite or mocks) |

---

## Config File Reference

**File**: `.kiro/specs/campusshield-postgresql-migration/.config.kiro`

```json
{"specId": "2e25a563-dc72-4a00-b80e-09cfe2e190f3", "workflowType": "requirements-first", "specType": "bugfix"}
```
