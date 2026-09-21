

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
MODEL_DIR = DATA_DIR / "models"
REPORT_DIR = DATA_DIR / "reports"

for _dir in (DATA_DIR, UPLOAD_DIR, MODEL_DIR, REPORT_DIR):
    _dir.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must contain the Neon PostgreSQL connection string")
if not DATABASE_URL.startswith(("postgresql://", "postgresql+psycopg://")):
    raise RuntimeError("DATABASE_URL must use a PostgreSQL/Neon URL; SQLite is legacy data only")

# PostgreSQL/Neon and local JWT are the only active application providers.
APP_ENV = os.getenv("APP_ENV", "development").lower()
DB_PROVIDER = "postgresql"
AUTH_PROVIDER = "local"
STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").lower()
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY must be set to a long random secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("TOKEN_EXPIRE_MINUTES", "480"))

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173",
).split(",")

# ---------------------------------------------------------------------------
# Upload Limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024
ALLOWED_EXTENSIONS = {".pcap", ".pcapng", ".cap"}

# ---------------------------------------------------------------------------
# Detection Defaults
# ---------------------------------------------------------------------------
DEFAULT_CONTAMINATION = float(os.getenv("DEFAULT_CONTAMINATION", "0.05"))
MIN_CONTAMINATION = 0.001
MAX_CONTAMINATION = 0.5
DEFAULT_N_ESTIMATORS = int(os.getenv("N_ESTIMATORS", "200"))
DEFAULT_RANDOM_STATE = 42

# Feature extraction
WINDOW_SIZE_SECONDS = float(os.getenv("WINDOW_SIZE_SECONDS", "10.0"))
BURST_IAT_THRESHOLD = float(os.getenv("BURST_IAT_THRESHOLD", "0.001"))

# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
SEVERITY_THRESHOLDS = {
    "LOW": (0, 30),
    "MEDIUM": (31, 60),
    "HIGH": (61, 80),
    "CRITICAL": (81, 100),
}

SCORE_WEIGHTS = {
    "anomaly_score": 0.40,
    "feature_deviation": 0.40,
    "category_boost": 0.20,
}

# ---------------------------------------------------------------------------
# Simulation
# ---------------------------------------------------------------------------
SIMULATION_PACKET_COUNT = int(os.getenv("SIM_PACKET_COUNT", "2000"))
SIMULATION_SCENARIOS = [
    "normal",
    "ddos",
    "scan",
    "protocol_anomaly",
    "exfiltration",
    "botnet_c2",
    "dns_tunneling",
]


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------
WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))

# ---------------------------------------------------------------------------
# Authorized Users (Configured with Full Admin Privileges)
# ---------------------------------------------------------------------------
# Optional one-time bootstrap administrator.  No account is seeded unless all
# values are supplied through the deployment environment.
_bootstrap_admin = {
    "username": os.getenv("INITIAL_ADMIN_USERNAME", "").strip(),
    "password": os.getenv("INITIAL_ADMIN_PASSWORD", ""),
    "email": os.getenv("INITIAL_ADMIN_EMAIL", "").strip(),
    "full_name": os.getenv("INITIAL_ADMIN_FULLNAME", "").strip(),
}
DEMO_USERS = [{**_bootstrap_admin, "role": "admin"}] if all(_bootstrap_admin.values()) else []
