# Shared test helpers — not a test module itself (no test_ functions).
# Builds a fresh in-memory-SQLite-backed AuthService/MatchesRepository pair,
# the same shape server/main.py wires from a real on-disk connection.
from __future__ import annotations

from server.auth.service import AuthService
from server.db.connection import create_connection
from server.db.matches_repository import MatchesRepository
from server.db.schema import init_schema
from server.db.users_repository import UsersRepository


def build_test_repos() -> tuple[AuthService, MatchesRepository]:
    conn = create_connection(":memory:")
    init_schema(conn)
    return AuthService(UsersRepository(conn)), MatchesRepository(conn)
