# Implementation Plan

## Overview

This task list implements the fix for the CampusShield PostgreSQL migration startup failure. The bug is that `backend/config.py` raises `RuntimeError` at import time when `DATABASE_URL` or `JWT_SECRET_KEY` are absent. The fix requires three code changes: adding `python-dotenv` to dependencies, calling `load_dotenv()` at the top of `backend/main.py`, and creating `backend/tests/conftest.py` to set env vars before pytest collection. The operator must also create a `.env` file from `.env.example` with real Neon PostgreSQL credentials.

## Task Dependency Graph

```json
{
  "waves": [
    { "wave": 1, "tasks": ["1", "2"] },
    { "wave": 2, "tasks": ["3.1"] },
    { "wave": 3, "tasks": ["3.2", "3.3", "3.4"] },
    { "wave": 4, "tasks": ["3.5", "3.6"] },
    { "wave": 5, "tasks": ["4"] }
  ]
}
```

## Tasks

- [ ] 1. Write bug condition exploration test
  - **Property 1: Bug Condition** - Config Import Fails Without Environment Variables
  - **CRITICAL**: This test MUST FAIL on unfixed code — failure confirms the bug exists
  - **DO NOT attempt to fix the test or the code when it fails**
  - **NOTE**: This test encodes the expected behavior — it will validate the fix when it passes after implementation
  - **GOAL**: Surface counterexamples that demonstrate that `backend.config` raises `RuntimeError` at import time when `DATABASE_URL` or `JWT_SECRET_KEY` are absent
  - **Scoped PBT Approach**: Scope the property to the three concrete failing cases for reproducibility:
    1. Both variables absent from `os.environ`
    2. `DATABASE_URL` set to an SQLite path (`sqlite:///./dev.db`), `JWT_SECRET_KEY` set
    3. `DATABASE_URL` valid, `JWT_SECRET_KEY` empty string
  - Create `backend/tests/test_config_bug_condition.py` using `pytest` + `hypothesis` (or `pytest.mark.parametrize` if hypothesis is unavailable)
  - For each case, use `unittest.mock.patch.dict(os.environ, {...}, clear=True)` to isolate the environment, then assert that `importlib.reload(backend.config)` raises `RuntimeError` with the expected message substring
  - The test assertions match the Expected Behavior from design: valid env → no RuntimeError; invalid/missing env → RuntimeError with descriptive message
  - Run test on UNFIXED code (before adding `load_dotenv()` and `conftest.py`)
  - **EXPECTED OUTCOME**: Test FAILS (proves the bug exists — `backend.config` raises on first import, before the patched reload can even run, because the module is already cached or was never loaded cleanly)
  - Document counterexamples found (e.g., "importing `backend.config` in a shell without `.env` raises `RuntimeError: DATABASE_URL must contain the Neon PostgreSQL connection string`")
  - Mark task complete when test is written, run, and failure is documented
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 2. Write preservation property tests (BEFORE implementing fix)
  - **Property 2: Preservation** - Non-Config Module Behaviors Are Unchanged
  - **IMPORTANT**: Follow observation-first methodology
  - Observe behavior on UNFIXED code (without `.env`) for modules that do NOT import `backend.config`:
    - `backend.features.extractor` — no config dependency, all tests in `test_features.py` pass today
    - `backend.detection.isolation_forest` — no config dependency, all tests in `test_detection.py` pass today
    - `backend.classification.categorizer` — no config dependency, `test_categorization.py` passes today
    - `backend.database.crud` + `backend.database.models` — used with in-memory SQLite in `test_tenant_isolation.py`, passes today
  - Record observed behaviors:
    - Feature extraction on empty packet list returns all-zero dict with exactly `len(FEATURE_NAMES)` keys
    - `AnomalyDetector` trained on normal traffic scores attack traffic lower than normal traffic
    - Tenant A records are never returned to Tenant B queries via CRUD layer
  - Write property-based tests in `backend/tests/test_preservation.py` capturing these invariants:
    - **Property 2a**: For all non-empty lists of packet dicts, `extract_features_from_window` returns a dict with exactly `len(FEATURE_NAMES)` float values and never raises
    - **Property 2b**: For all pairs of distinct tenant IDs, CRUD queries for one tenant never return rows belonging to the other (extending `test_tenant_isolation.py` pattern with hypothesis-generated tenant ID strings)
  - Run tests on UNFIXED code (no `.env` present)
  - **EXPECTED OUTCOME**: Tests PASS on unfixed code (confirms baseline behavior to preserve — these modules do not depend on `backend.config`)
  - Mark task complete when tests are written, run, and passing on unfixed code
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [ ] 3. Fix: add `load_dotenv()` entrypoint call, `python-dotenv` dependency, and `conftest.py`

  - [ ] 3.1 Add `python-dotenv` to `backend/requirements.txt`
    - Open `backend/requirements.txt`
    - Add `python-dotenv>=1.0.0` under the `# Utilities` section
    - Run `pip install python-dotenv` (or `pip install -r backend/requirements.txt`) to install it
    - _Bug_Condition: isBugCondition(env) where `DATABASE_URL` or `JWT_SECRET_KEY` absent — the `.env` file is never read because `load_dotenv()` is never called_
    - _Expected_Behavior: `load_dotenv()` reads `.env` into `os.environ` before `backend.config` is imported, satisfying both required variables_
    - _Preservation: `requirements.txt` changes do not affect any existing module behavior_
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.2 Add `load_dotenv()` call as the very first lines of `backend/main.py`
    - Open `backend/main.py`
    - Insert the following two lines **before** all other imports (as the first executable lines in the file):
      ```python
      from dotenv import load_dotenv
      load_dotenv()  # loads .env from the project root into os.environ
      ```
    - Verify by reading the file that these lines appear before `import logging` and all `from backend.*` imports
    - _Bug_Condition: isBugCondition(env) — `backend.config` is imported by `backend.database.connection` which is imported by `backend.main`; without `load_dotenv()` first, the env vars are never set_
    - _Expected_Behavior: `load_dotenv()` injects `DATABASE_URL` and `JWT_SECRET_KEY` into `os.environ` before `backend.config` module-level validation runs_
    - _Preservation: No existing route, lifespan hook, or middleware is modified; `load_dotenv()` is a no-op when env vars are already set in the process environment_
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.3 Create `backend/tests/conftest.py` to guard pytest collection
    - Create the file `backend/tests/conftest.py` with the following content:
      ```python
      """
      Pytest configuration: set required environment variables BEFORE any
      backend module is imported during test collection.
      These values are intentionally fake — unit tests that need a real DB
      use in-memory SQLite directly (see test_tenant_isolation.py).
      """
      import os

      os.environ.setdefault(
          "DATABASE_URL",
          "postgresql+psycopg://test:test@localhost/campusshield_test",
      )
      os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only-minimum-32-chars")
      ```
    - The `setdefault` calls ensure real environment variables (e.g., from a CI `.env`) are never overwritten
    - This file is executed by pytest before any test module is imported, preventing the `RuntimeError` from `backend.config` at collection time
    - _Bug_Condition: isBugCondition(env) — without `conftest.py`, pytest imports test modules which transitively import `backend.config`, triggering `RuntimeError` before any test function runs_
    - _Expected_Behavior: `conftest.py` sets the two required env vars before collection; all existing unit tests that use in-memory SQLite or mock the DB continue to pass_
    - _Preservation: Tests in `test_tenant_isolation.py` that create their own SQLite engine are unaffected; the fake `DATABASE_URL` is never used to open a real connection in those tests_
    - _Requirements: 2.7, 1.7_

  - [ ] 3.4 Document `.env` creation for operators
    - Verify `.env.example` exists at the project root (it does — confirmed in repo)
    - Add a `## Quick Start` section to the project `README.md` (or create one if absent) documenting the following steps:
      1. Copy template: `copy .env.example .env` (Windows) / `cp .env.example .env` (Linux/macOS)
      2. Set `DATABASE_URL` to the Neon PostgreSQL connection string (scheme must be `postgresql+psycopg://`)
      3. Generate `JWT_SECRET_KEY`: `python -c "import secrets; print(secrets.token_hex(32))"`
      4. Optionally set `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_FULLNAME` for first-run admin seeding
      5. Start: `uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`
    - _Requirements: 2.1, 2.5_

  - [ ] 3.5 Verify bug condition exploration test now passes
    - **Property 1: Expected Behavior** - Config Import Succeeds With Valid Environment Variables
    - **IMPORTANT**: Re-run the SAME test from task 1 — do NOT write a new test
    - The test from task 1 uses `patch.dict(os.environ, valid_env, clear=True)` + `importlib.reload(backend.config)` to assert no exception is raised
    - With `conftest.py` in place, pytest collection no longer fails; with `load_dotenv()` in `main.py`, the real application path also works
    - Run: `pytest backend/tests/test_config_bug_condition.py -v`
    - **EXPECTED OUTCOME**: Test PASSES (confirms bug is fixed — `backend.config` accepts valid env vars without raising)
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ] 3.6 Verify preservation tests still pass
    - **Property 2: Preservation** - Non-Config Module Behaviors Are Unchanged
    - **IMPORTANT**: Re-run the SAME tests from task 2 — do NOT write new tests
    - Run the full test suite:
      ```
      pytest backend/tests/test_features.py
      pytest backend/tests/test_detection.py
      pytest backend/tests/test_categorization.py
      pytest backend/tests/test_scoring.py
      pytest backend/tests/test_tenant_isolation.py
      pytest backend/tests/test_unidirectional.py
      pytest backend/tests/test_preservation.py
      ```
    - **EXPECTED OUTCOME**: All tests PASS (confirms no regressions — the `conftest.py` and `load_dotenv()` changes do not alter any module logic)
    - Confirm zero failures and zero collection errors

- [ ] 4. Checkpoint — Ensure all tests pass and the application starts
  - Run the complete test suite: `pytest backend/tests/ -v`
  - Confirm zero failures and zero errors
  - After the operator has created `.env` with valid Neon credentials, verify the backend starts:
    - `uvicorn backend.main:app --port 8000` starts without errors
    - Startup log shows: `Database initialized`, `Demo users seeded (admin/analyst)`, `CampusShield AI ready`
    - `GET /health` returns HTTP 200 `{"status": "healthy"}`
    - Neon dashboard Tables tab shows all 9 tables: `tenants`, `users`, `traffic_sessions`, `detection_results`, `contributing_factors`, `alerts`, `detection_config`, `audit_logs`, `reports`
  - Verify full feature checklist after login with `INITIAL_ADMIN_*` credentials:
    - `POST /api/auth/login` → HTTP 200 + JWT
    - `GET /api/alerts` with JWT → HTTP 200
    - `POST /api/detection/simulate` with JWT → HTTP 200, session created
    - `POST /api/reports/{session_id}` with JWT → HTTP 200, PDF generated
    - WebSocket `ws://localhost:8000/ws/alerts?token=JWT` → connection accepted, `{"type": "connected"}` received
    - Frontend build proxies `/api` and `/ws` to `http://localhost:8000` correctly
  - Ask the user if any questions arise

## Notes

- Tasks 1 and 2 are standalone exploration/preservation tests that run **before** any fix is applied. They confirm the bug exists (task 1 fails) and baseline behavior is stable (task 2 passes).
- Tasks 3.1–3.4 are the actual fix steps, each independently verifiable.
- Tasks 3.5 and 3.6 re-run the same tests from tasks 1 and 2 to confirm the fix works and introduces no regressions.
- The operator `.env` creation step (3.4) is a prerequisite for the live startup verification in task 4, but NOT for the automated pytest suite — `conftest.py` provides fake-but-valid env vars for unit tests.
- All existing tests that use in-memory SQLite (`test_tenant_isolation.py`) are unaffected by these changes.
- `python-dotenv` is a new dependency; add it to `backend/requirements.txt` before running the test suite.
