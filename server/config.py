# All server tunables in one place — no magic numbers scattered through the
# codebase. Later phases append their own settings here, never redefine these.
# Every value is overridable via an env var of the same name so the same
# image runs unmodified across local dev (docker-compose) and later phases.
from __future__ import annotations

import os

HOST = os.environ.get("HOST", "localhost")
PORT = int(os.environ.get("PORT", "8765"))
TICK_MS = int(os.environ.get("TICK_MS", "50"))

DB_PATH = os.environ.get("DB_PATH", "server/kfchess.db")
PBKDF2_ITERATIONS = int(os.environ.get("PBKDF2_ITERATIONS", "200000"))
ELO_K_FACTOR = int(os.environ.get("ELO_K_FACTOR", "32"))

QUEUE_ELO_RANGE = int(os.environ.get("QUEUE_ELO_RANGE", "100"))
QUEUE_POLL_INTERVAL_SECONDS = float(os.environ.get("QUEUE_POLL_INTERVAL_SECONDS", "1.0"))
QUEUE_TIMEOUT_SECONDS = float(os.environ.get("QUEUE_TIMEOUT_SECONDS", "60.0"))

DISCONNECT_GRACE_SECONDS = float(os.environ.get("DISCONNECT_GRACE_SECONDS", "20.0"))

# Infra endpoints used by the containerized services (deploy/docker-compose.yml).
# Unused by the local (non-docker) monolith entrypoint, server/main.py.
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9090"))
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://kfchess:kfchess@localhost:5432/kfchess")
