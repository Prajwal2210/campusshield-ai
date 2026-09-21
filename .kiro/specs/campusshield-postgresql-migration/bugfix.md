# Bugfix Requirements Document

## Introduction

CampusShield AI is migrating from a local SQLite database to Neon PostgreSQL as its active database. The legacy SQLite database (`backend/data/campusshield.db`) had a schema mismatch — specifically, the `users` table was missing the `tenant_id` column along with other multi-tenancy columns present in the current SQLAlchemy models. Rather than patching the old SQLite schema, the fix is to establish Neon PostgreSQL as the sole active database with the full, correct schema derived from the current SQLAlchemy models. The application cannot start at all without a `.env` file containing a valid `DATABASE_URL` pointing to the Neon PostgreSQL instance and a `JWT_SECRET_KEY`, making the entire application inoperable.

## Bug Analysis

### Current Behavior (Defect)

1.1 WHEN the application starts without a `.env` file present THEN the system raises `RuntimeError: DATABASE_URL must contain the Neon PostgreSQL connection string` and refuses to start, making every feature (login, dashboard, detection, alerts, reports) inaccessible.

1.2 WHEN `DATABASE_URL` is absent or empty in the environment THEN the system fails at import time in `backend/config.py` before any route handler, database session, or startup hook can execute.

1.3 WHEN `JWT_SECRET_KEY` is absent or empty in the environment THEN the system raises `RuntimeError: JWT_SECRET_KEY must be set to a long random secret` and refuses to start, blocking all JWT-protected endpoints.

1.4 WHEN `DATABASE_URL` is set to an SQLite path (e.g., `sqlite:///...`) THEN the system raises `RuntimeError: DATABASE_URL must use a PostgreSQL/Neon URL; SQLite is legacy data only`, correctly rejecting it but leaving the operator without a working database.

1.5 WHEN a valid Neon PostgreSQL `DATABASE_URL` is provided but the PostgreSQL schema has never been created THEN `init_db()` is called at startup and `Base.metadata.create_all()` runs, but if the Neon database is empty it succeeds silently — however no seed tenant (`tenant-default`) or bootstrap admin user is present, causing any login attempt to return HTTP 401 with no way to create an account unless the signup endpoint is used.

1.6 WHEN the application runs with Neon PostgreSQL connected and a user attempts to register via `POST /api/auth/signup` THEN the system creates a new tenant and user correctly, but the `INITIAL_ADMIN_*` environment variables are not set, so `DEMO_USERS` is empty and no pre-seeded admin account exists for initial access.

1.7 WHEN tests in `backend/tests/test_tenant_isolation.py` run THEN the system uses an in-memory SQLite engine for isolation, which passes; but integration tests that import `backend.config` fail immediately if the environment variables `DATABASE_URL` and `JWT_SECRET_KEY` are not set in the test execution environment.

### Expected Behavior (Correct)

2.1 WHEN a `.env` file exists at the project root with a valid `DATABASE_URL` (postgresql+psycopg scheme) and `JWT_SECRET_KEY` THEN the system SHALL start successfully, connect to Neon PostgreSQL, create all tables via `Base.metadata.create_all()`, and seed the default tenant.

2.2 WHEN `DATABASE_URL` is absent or empty THEN the system SHALL provide a clear, actionable error message instructing the operator to copy `.env.example` to `.env` and fill in the Neon connection string, rather than failing silently.

2.3 WHEN `JWT_SECRET_KEY` is absent or empty THEN the system SHALL provide a clear, actionable error message instructing the operator to generate and set a long random secret.

2.4 WHEN a valid `DATABASE_URL` pointing to an empty Neon database is provided THEN the system SHALL create the full PostgreSQL schema (tenants, users, traffic_sessions, detection_results, contributing_factors, alerts, detection_config, audit_logs, reports) idempotently on every startup without dropping or altering existing data.

2.5 WHEN `INITIAL_ADMIN_USERNAME`, `INITIAL_ADMIN_PASSWORD`, `INITIAL_ADMIN_EMAIL`, and `INITIAL_ADMIN_FULLNAME` are all set in the environment THEN the system SHALL seed a single admin user under `tenant-default` on first run, enabling immediate login without requiring self-signup.

2.6 WHEN `POST /api/auth/login` is called with valid credentials THEN the system SHALL authenticate against the Neon PostgreSQL `users` table (which includes the `tenant_id` column), return a signed JWT containing `sub`, `role`, and `tenant_id` claims, and respond with HTTP 200.

2.7 WHEN tests run THEN the system SHALL allow unit/integration tests that do not touch the live database to pass by either using in-memory SQLite (for pure unit tests) or by mocking the database dependency, without requiring a live Neon connection in CI unless explicitly configured.

### Unchanged Behavior (Regression Prevention)

3.1 WHEN a valid JWT is presented to any protected endpoint THEN the system SHALL CONTINUE TO validate it via `LocalJWTAuthProvider.verify_token`, extract `sub` and `tenant_id`, and enforce tenant isolation on all CRUD operations.

3.2 WHEN `POST /api/auth/signup` is called with unique username/email THEN the system SHALL CONTINUE TO create a new tenant, create an analyst user under that tenant, and return a JWT token.

3.3 WHEN `POST /api/auth/register` is called by an authenticated admin THEN the system SHALL CONTINUE TO add a new user under the admin's own tenant without allowing cross-tenant user creation.

3.4 WHEN traffic simulation or PCAP upload triggers the detection pipeline THEN the system SHALL CONTINUE TO run the Isolation Forest and rule-based anomaly detection, persist `DetectionResult` and `ContributingFactor` rows to PostgreSQL, and create `Alert` rows for anomalies above the threshold.

3.5 WHEN `GET /api/alerts` is called with a valid tenant JWT THEN the system SHALL CONTINUE TO return only alerts belonging to that tenant, enforcing `Alert.tenant_id` filtering.

3.6 WHEN a WebSocket client connects to `/ws/alerts?token=JWT` with a valid token THEN the system SHALL CONTINUE TO accept the connection and push real-time alert events.

3.7 WHEN `POST /api/reports/{session_id}` is called THEN the system SHALL CONTINUE TO generate a PDF report using ReportLab, persist a `Report` row, and make the file available for authenticated download.

3.8 WHEN the application is running THEN `backend/data/campusshield.db` SHALL CONTINUE TO exist unmodified as a legacy/reference file and SHALL NOT be used as the active database.

3.9 WHEN `GET /health` is called THEN the system SHALL CONTINUE TO return HTTP 200 with `{"status": "healthy"}` regardless of authentication state.

3.10 WHEN the frontend Vite dev server is running THEN it SHALL CONTINUE TO proxy `/api` and `/ws` requests to `http://localhost:8000`, with no changes to `vite.config.js` required.
