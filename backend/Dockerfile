# ── CampusShield AI — Backend ────────────────────────────────────────────────
# Build context: project root  (docker-compose sets context: .)
# Runtime: Python 3.11-slim + libpcap (required by scapy for PCAP uploads)
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim

# ---------------------------------------------------------------------------
# System dependencies
#   libpcap0.8  – runtime shared library required by scapy to read .pcap files
#   curl        – used only by the HEALTHCHECK instruction below; removed from
#                 the final image layer ordering is intentional (one RUN = one
#                 cache layer, keeping libpcap and curl together so they can be
#                 dropped together if scapy is ever removed)
# ---------------------------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpcap0.8 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Non-root application user
#   UID/GID 1001 avoids collision with common host UIDs
# ---------------------------------------------------------------------------
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid 1001 --no-create-home --shell /sbin/nologin appuser

# ---------------------------------------------------------------------------
# Python dependencies (installed as root before chown so pip cache stays clean)
# ---------------------------------------------------------------------------
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# ---------------------------------------------------------------------------
# Application code
# ---------------------------------------------------------------------------
COPY backend /app/backend

# ---------------------------------------------------------------------------
# Data directories
#   These are created and owned by appuser so the application can write
#   uploaded files, generated reports, and persisted model files at runtime.
#   The named volume in docker-compose is mounted at /app/backend/data, so
#   ownership must be set AFTER COPY (COPY resets ownership to root).
# ---------------------------------------------------------------------------
RUN mkdir -p \
        /app/backend/data/uploads \
        /app/backend/data/models \
        /app/backend/data/reports \
    && chown -R appuser:appgroup /app/backend/data

# ---------------------------------------------------------------------------
# Switch to non-root user for all subsequent instructions and at runtime
# ---------------------------------------------------------------------------
USER appuser

EXPOSE 8000

# ---------------------------------------------------------------------------
# Health check
#   Polls /health every 30 s; allows 5 s to respond; 3 consecutive failures
#   mark the container unhealthy.  Start period gives uvicorn time to boot.
# ---------------------------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
