# Container preparation

CampusShield runs as a React/Vite frontend, FastAPI backend, and externally
managed Neon PostgreSQL database. It does not provision cloud infrastructure.

1. Copy `.env.example` to `.env` and provide a Neon PostgreSQL connection URL
   plus a long random `JWT_SECRET_KEY`.
2. Run `docker compose up --build`.
3. Open `http://localhost:5173`; the frontend proxies `/api` and `/ws` to the
   backend container, which is also exposed at `http://localhost:8000`.

The Compose file intentionally has no database service: Neon is the active
database, and the legacy SQLite file remains untouched as reference data.
