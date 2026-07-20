# All server tunables in one place — no magic numbers scattered through the
# codebase. Later phases append their own settings here, never redefine these.
from __future__ import annotations

HOST = "localhost"
PORT = 8765
TICK_MS = 50
