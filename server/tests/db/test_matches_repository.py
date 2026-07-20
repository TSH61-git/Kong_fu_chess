import asyncio

from server.db.connection import create_connection
from server.db.matches_repository import MatchesRepository
from server.db.schema import init_schema
from server.db.users_repository import UsersRepository


def _run(coro):
    return asyncio.run(coro)


def test_record_result_persists_a_row():
    conn = create_connection(":memory:")
    init_schema(conn)
    users = UsersRepository(conn)
    matches = MatchesRepository(conn)

    white = _run(users.create("white_player", "hash", "salt"))
    black = _run(users.create("black_player", "hash", "salt"))

    _run(matches.record_result(white.id, black.id, white.id, "king_captured"))

    row = conn.execute("SELECT * FROM matches").fetchone()
    assert row["white_user_id"] == white.id
    assert row["black_user_id"] == black.id
    assert row["winner_user_id"] == white.id
    assert row["reason"] == "king_captured"


def test_record_result_allows_a_null_winner_for_a_draw():
    conn = create_connection(":memory:")
    init_schema(conn)
    users = UsersRepository(conn)
    matches = MatchesRepository(conn)

    white = _run(users.create("white_player", "hash", "salt"))
    black = _run(users.create("black_player", "hash", "salt"))

    _run(matches.record_result(white.id, black.id, None, "draw"))

    row = conn.execute("SELECT * FROM matches").fetchone()
    assert row["winner_user_id"] is None
