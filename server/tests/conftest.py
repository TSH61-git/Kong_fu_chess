# Production uses 200_000 PBKDF2 iterations (server/config.py); every test
# that registers/logs in a user pays that cost synchronously, which dominates
# the whole suite's runtime. Tests don't need production-grade hashing
# strength, so drop it here — real security is exercised by hashing.py's own
# tests, not by every call site that happens to need *a* hashed password.
from server import config

config.PBKDF2_ITERATIONS = 1_000
