# Requirements Document

## Introduction

CampusShield AI is an AI-powered cyber threat detection system for unidirectional IP traffic (SIH26145). The project runs on a React + Vite frontend, a FastAPI backend, and SQLAlchemy as the ORM. This feature configures Neon PostgreSQL as the sole active database, replacing a legacy SQLite setup that had a schema mismatch (`users.tenant_id` column missing). All application features — JWT authentication, multi-tenancy, the detection pipeline, alerts, reports, and WebSocket notifications — must continue to function correctly against the new PostgreSQL-backed persistence layer. The legacy SQLite file (`backend/data/campusshield.db`) is preserved as a read-only artefact and is never used at runtime.

## Glossary

- **System**: The CampusShield AI FastAPI application.
- **Config_Module**: `backend/config.py` — the module that validates required environment variables at Python import time.
- **Database_Layer**: The set of SQLAlchemy models (`backend/database/models.py`), engine factory (`backend/database/connection.py`), and CRUD helpers (`backend/database/crud.py`).
- **Neon_DB**: The Neon serverless PostgreSQL instance identified by the `DATABASE_URL` environment variable.
- **DATABASE_URL**: The PostgreSQL connection string stored in `.env`; must use the `postgresql+psycopg://` scheme.
- **JWT_SECRET_KEY**: A cryptographically random secret stored in `.env` used to sign and verify JWTs.
- **dotenv_file**: The `.env` file at the project root, loaded by `python-dotenv` before any backend module is imported.
- **init_db**: The `init_db()` function in `backend/database/connection.py` that calls `Base.metadata.create_all()`.
- **seed_demo_users**: The `seed_demo_users()` function in `backend/auth/security.py` that creates the default tenant and a bootstrap admin on first run.
- **Tenant**: A row in the `tenants` table representing an isolated organisational workspace.
- **INITIAL_ADMIN_***: The four optional environment variables (`INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_FULLNAME`) that trigger bootstrap admin seeding when all four are non-empty.
- **conftest_py**: `backend/tests/conftest.py` — the pytest configuration file that sets required environment variables before test collection.
- **Detection_Pipeline**: The Isolation Forest + rule-based anomaly detection components that produce `DetectionResult`, `ContributingFactor`, and `Alert` rows.
- **Legacy_SQLite**: `backend/data/campusshield.db` — the old local SQLite database file that must remain unmodified.

## Requirements

---

### Requirement 1: Environment Variable Validation at Startup

**User Story:** As a system operator, I want the application to validate required environment variables before any component initialises, so that I receive a clear, actionable error message when configuration is missing instead of a silent failure or a cryptic traceback.

#### Acceptance Criteria

1. WHEN the application process starts and `DATABASE_URL` is absent or empty in the environment, THEN THE Config_Module SHALL raise a `RuntimeError` with the message `"DATABASE_URL must contain the Neon PostgreSQL connection string"` before any route handler, database session, or lifespan hook executes.

2. WHEN the application process starts and `DATABASE_URL` is set to a non-PostgreSQL URL (e.g., an `sqlite://` prefix), THEN THE Config_Module SHALL raise a `RuntimeError` with the message `"DATABASE_URL must use a PostgreSQL/Neon URL; SQLite is legacy data only"`.

3. WHEN the application process starts and `JWT_SECRET_KEY` is absent or empty in the environment, THEN THE Config_Module SHALL raise a `RuntimeError` with the message `"JWT_SECRET_KEY must be set to a long random secret"`.

4. WHEN `DATABASE_URL` starts with `postgresql://` or `postgresql+psycopg://` AND `JWT_SECRET_KEY` is a non-empty string, THEN THE Config_Module SHALL import successfully without raising any exception, and the module-level constants `DATABASE_URL` and `SECRET_KEY` SHALL be populated with the provided values.

5. WHEN the dotenv_file exists at the project root and contains `DATABASE_URL` and `JWT_SECRET_KEY`, THEN THE System SHALL load those values into the process environment via `load_dotenv()` before THE Config_Module is imported, so that no `RuntimeError` is raised.

---

### Requirement 2: PostgreSQL Schema Initialisation

**User Story:** As a system operator, I want the application to create the complete PostgreSQL schema automatically on startup, so that I do not need to run manual migration scripts when connecting to a fresh Neon database.

#### Acceptance Criteria

1. WHEN `init_db()` is called and Neon_DB contains no tables, THE Database_Layer SHALL create all nine tables — `tenants`, `users`, `traffic_sessions`, `detection_results`, `contributing_factors`, `alerts`, `detection_config`, `audit_logs`, `reports` — without raising any exception.

2. WHEN `init_db()` is called and Neon_DB already contains those tables with existing rows, THE Database_Layer SHALL leave all existing rows and all table definitions unchanged (idempotent `CREATE TABLE IF NOT EXISTS` semantics).

3. THE Database_Layer SHALL use `pool_pre_ping=True` on the SQLAlchemy engine so that stale connections to Neon_DB are detected and recycled before any query is executed.

4. WHEN the application lifespan `startup` event fires, THE System SHALL call `init_db()` before calling `seed_demo_users()`, ensuring the schema exists before any insert is attempted.

---

### Requirement 3: Bootstrap Admin Seeding

**User Story:** As a system operator, I want a bootstrap admin account to be created automatically on first startup when I supply the four `INITIAL_ADMIN_*` environment variables, so that I can log in immediately without using the public signup endpoint.

#### Acceptance Criteria

1. WHEN all four `INITIAL_ADMIN_*` variables are non-empty AND no user with the given username exists in Neon_DB, THEN THE System SHALL create exactly one admin user under `tenant-default` during the lifespan startup event.

2. WHEN `seed_demo_users()` is called on a database that already contains the bootstrap admin user, THE System SHALL NOT create a duplicate user row and SHALL NOT raise any exception.

3. WHEN any one of the four `INITIAL_ADMIN_*` variables is absent or empty, THE System SHALL seed zero users and SHALL log a message indicating that no bootstrap admin was configured.

4. WHEN `seed_demo_users()` creates a bootstrap admin user, THE System SHALL also ensure the `tenant-default` tenant row exists in the `tenants` table before inserting the user, satisfying the foreign-key constraint on `users.tenant_id`.

---

### Requirement 4: JWT Authentication Against PostgreSQL

**User Story:** As a registered user, I want to log in with my username and password and receive a JWT, so that I can access all protected API endpoints using the PostgreSQL-backed user store.

#### Acceptance Criteria

1. WHEN `POST /api/auth/login` is called with valid credentials, THE System SHALL authenticate the user against the `users` table in Neon_DB, return HTTP 200, and include a signed JWT containing the `sub` (username), `role`, and `tenant_id` claims.

2. WHEN `POST /api/auth/login` is called with an unrecognised username or incorrect password, THE System SHALL return HTTP 401 with the detail `"Incorrect username or password"`.

3. WHEN `POST /api/auth/signup` is called with a unique username and email, THE System SHALL create a new `Tenant` row and an analyst `User` row in Neon_DB, then return HTTP 201 and a signed JWT.

4. WHEN `POST /api/auth/signup` is called with a username that already exists in Neon_DB, THE System SHALL return HTTP 409 with a detail message identifying the duplicate username.

5. WHEN a protected endpoint receives an `Authorization: Bearer <token>` header with a valid JWT, THE System SHALL extract the `tenant_id` claim and apply it to all CRUD queries for that request so that only rows belonging to that tenant are returned.

---

### Requirement 5: Multi-Tenancy and Data Isolation

**User Story:** As a security analyst, I want my organisation's data to be completely isolated from other tenants' data, so that alerts, sessions, and reports belonging to one tenant are never visible to another tenant.

#### Acceptance Criteria

1. WHEN `GET /api/alerts` is called with a valid JWT containing `tenant_id = T1`, THE System SHALL return only `Alert` rows where `alerts.tenant_id = T1` and SHALL NOT include any row where `alerts.tenant_id ≠ T1`.

2. WHEN `GET /api/sessions` is called with a valid JWT containing `tenant_id = T1`, THE System SHALL return only `TrafficSession` rows where `traffic_sessions.tenant_id = T1`.

3. WHEN `POST /api/auth/register` is called by an authenticated admin with `tenant_id = T1`, THE System SHALL create the new user under `T1` and SHALL NOT allow the caller to assign the new user to a different tenant.

4. FOR ALL pairs of distinct tenant IDs `(T1, T2)`, CRUD queries filtered by `T1` SHALL NOT return any row whose `tenant_id` column contains `T2`.

---

### Requirement 6: Detection Pipeline Persistence to PostgreSQL

**User Story:** As a security analyst, I want the Isolation Forest and rule-based anomaly detection results to be persisted to PostgreSQL, so that I can review historical detections, contributing factors, and generated alerts after a session completes.

#### Acceptance Criteria

1. WHEN a traffic simulation or PCAP upload completes analysis, THE Detection_Pipeline SHALL persist one `DetectionResult` row per analysis window to Neon_DB, with `session_id`, `tenant_id`, `is_anomaly`, `anomaly_score`, `normalized_score`, `threat_category`, `severity`, and `confidence` columns populated.

2. WHEN a `DetectionResult` is flagged as anomalous (`is_anomaly = true`), THE Detection_Pipeline SHALL persist one or more `ContributingFactor` rows referencing that result's `id`, each recording `feature_name`, `observed_value`, `baseline_value`, `deviation_pct`, `contribution_rank`, and `direction`.

3. WHEN a `DetectionResult` exceeds the alerting threshold, THE System SHALL persist exactly one `Alert` row per unique (`tenant_id`, `session_id`, `detection_result_id`) combination, and SHALL NOT create duplicate alerts for the same detection window.

4. WHILE a traffic analysis session is in `"processing"` status, THE System SHALL stream progress events over WebSocket to connected clients before the final `DetectionResult` rows are committed.

---

### Requirement 7: Alert Persistence and Incident Feed

**User Story:** As a security analyst, I want all generated alerts to be persisted in PostgreSQL and retrievable via the Incident Feed, so that I can acknowledge, filter, and review threats across multiple sessions.

#### Acceptance Criteria

1. WHEN `GET /api/alerts` is called with optional query parameters (`severity`, `status`, `session_id`, `limit`, `offset`), THE System SHALL return only alerts matching the supplied filters for the authenticated tenant, ordered by `created_at` descending.

2. WHEN `PATCH /api/alerts/{id}/acknowledge` is called by an authenticated user, THE System SHALL set the alert's `status` to `"acknowledged"`, record `acknowledged_by` and `acknowledged_at`, and return the updated alert.

3. WHEN `GET /api/alerts/stats` is called, THE System SHALL return aggregate counts grouped by `severity`, `status`, and `threat_category` for the authenticated tenant's alerts.

4. IF an acknowledgement request is made for an `alert_id` that does not exist or belongs to a different tenant, THEN THE System SHALL return HTTP 404.

---

### Requirement 8: WebSocket Real-Time Notifications

**User Story:** As a security analyst, I want real-time alert notifications pushed to my browser dashboard via WebSocket, so that I am immediately informed when a new threat is detected without needing to poll.

#### Acceptance Criteria

1. WHEN a WebSocket client connects to `/ws/alerts?token=<JWT>` with a valid token, THE System SHALL accept the connection and send a `{"type": "connected"}` message confirming the session.

2. WHEN a WebSocket client connects with an invalid or absent token, THE System SHALL reject the connection and close the WebSocket without sending any data.

3. WHEN a new `Alert` row is committed to Neon_DB, THE System SHALL broadcast the alert payload to all authenticated WebSocket clients belonging to the same tenant within 2 seconds of the commit.

4. WHEN a connected WebSocket client sends the text `"ping"`, THE System SHALL respond with `{"type": "pong"}` to allow keep-alive detection.

5. WHEN a WebSocket client disconnects, THE System SHALL remove the connection from the active pool without affecting other connected clients.

---

### Requirement 9: Report Generation and Authenticated Download

**User Story:** As a security analyst, I want to generate a PDF report for a completed analysis session and download it securely, so that I can share findings with stakeholders.

#### Acceptance Criteria

1. WHEN `POST /api/reports/{session_id}` is called with a valid JWT and the referenced session belongs to the authenticated tenant, THE System SHALL generate a PDF report using ReportLab, persist a `Report` row to Neon_DB with `session_id`, `tenant_id`, `file_path`, `file_size_bytes`, and `generated_by` populated, and return HTTP 200 with the report metadata.

2. WHEN `GET /api/reports/{report_id}/download` is called with a valid JWT and the report belongs to the authenticated tenant, THE System SHALL return the PDF file as a binary response with `Content-Type: application/pdf`.

3. IF `GET /api/reports/{report_id}/download` is called with a JWT whose `tenant_id` does not match the report's `tenant_id`, THEN THE System SHALL return HTTP 404.

4. WHEN `GET /api/reports` is called with a valid JWT, THE System SHALL return a list of all `Report` rows belonging to the authenticated tenant, ordered by `created_at` descending.

---

### Requirement 10: Legacy SQLite Preservation

**User Story:** As a system operator, I want the legacy SQLite database file to remain on disk unmodified, so that historical data is available for forensic reference without risking accidental data loss.

#### Acceptance Criteria

1. WHILE the application is running with Neon_DB as the active database, THE System SHALL NOT open, read from, or write to `backend/data/campusshield.db`.

2. THE System SHALL retain `backend/data/campusshield.db` on the filesystem unmodified, regardless of application start, stop, or schema initialisation operations.

3. IF the `DATABASE_URL` environment variable is changed to an `sqlite://` path at runtime, THEN THE Config_Module SHALL raise `RuntimeError` and prevent the application from starting, enforcing PostgreSQL as the exclusive active database.

---

### Requirement 11: Test Suite Compatibility

**User Story:** As a developer, I want the automated test suite to run without a live Neon connection for unit and property-based tests, so that CI passes reliably without needing production credentials.

#### Acceptance Criteria

1. WHEN `pytest` collects test modules in `backend/tests/`, THE System SHALL NOT raise any `RuntimeError` from THE Config_Module, because `conftest_py` sets `DATABASE_URL` and `JWT_SECRET_KEY` in the process environment before any backend module is imported.

2. WHEN unit tests that do not exercise the live database run, THE System SHALL use in-memory SQLite (or a mocked database session) rather than connecting to Neon_DB, ensuring test execution completes without network access.

3. WHEN property-based tests for tenant isolation run, THE System SHALL generate random pairs of distinct tenant IDs and assert that CRUD queries for one tenant never return rows owned by the other, using an in-memory SQLite engine to avoid live Neon connections.

4. WHERE a live Neon connection is required for integration tests, THE System SHALL skip those tests automatically when `DATABASE_URL` points to the fake test value set by `conftest_py`, unless a real Neon URL is explicitly supplied via the environment.

---

### Requirement 12: URL Inspection Feature

**User Story:** As a security analyst, I want to submit individual URLs for threat inspection, so that I can determine whether a URL is associated with known malicious patterns.

#### Acceptance Criteria

1. WHEN `POST /api/inspect/url` is called with a valid JWT and a URL string, THE System SHALL classify the URL using the threat intelligence module and return a response containing `threat_score`, `threat_category`, `severity`, and `confidence`.

2. WHEN `POST /api/inspect/url` is called with a malformed or empty URL string, THE System SHALL return HTTP 422 with a descriptive validation error.

3. WHEN a URL inspection result is generated, THE System SHALL persist an `AuditLog` row recording the inspection action, the `user_id`, and the inspected URL as part of the `details` payload.

---

### Requirement 13: Completed Sessions and Dashboard

**User Story:** As a security analyst, I want to view all completed analysis sessions on the dashboard with their summary statistics, so that I can track detection history and identify trends over time.

#### Acceptance Criteria

1. WHEN `GET /api/sessions` is called with a valid JWT, THE System SHALL return all `TrafficSession` rows for the authenticated tenant, ordered by `created_at` descending, with `status`, `packet_count`, `flow_count`, `duration_seconds`, and `traffic_stats` included in each response item.

2. WHEN `GET /api/sessions/{session_id}` is called with a valid JWT and the session belongs to the authenticated tenant, THE System SHALL return the full session detail including all associated `DetectionResult` rows and `Alert` rows.

3. WHEN `GET /api/dashboard/stats` is called with a valid JWT, THE System SHALL return aggregate statistics — total sessions, total alerts by severity, and recent anomaly count — for the authenticated tenant, derived from live queries against Neon_DB.

4. IF `GET /api/sessions/{session_id}` is called with a JWT whose `tenant_id` does not match the session's `tenant_id`, THEN THE System SHALL return HTTP 404.
