# All server tunables in one place — no magic numbers scattered through the
# codebase. Later phases append their own settings here, never redefine these.
from __future__ import annotations

HOST = "localhost"
PORT = 8765
TICK_MS = 50

DB_PATH = "server/kfchess.db"
PBKDF2_ITERATIONS = 200_000
ELO_K_FACTOR = 32

QUEUE_ELO_RANGE = 100
QUEUE_POLL_INTERVAL_SECONDS = 1.0
QUEUE_TIMEOUT_SECONDS = 60.0

DISCONNECT_GRACE_SECONDS = 20.0
