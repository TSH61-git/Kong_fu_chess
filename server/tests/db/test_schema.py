from server.db.connection import create_connection
from server.db.schema import init_schema


def test_init_schema_creates_users_and_matches_tables():
    conn = create_connection(":memory:")
    init_schema(conn)

    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    }
    assert "users" in tables
    assert "matches" in tables


def test_init_schema_is_idempotent():
    conn = create_connection(":memory:")
    init_schema(conn)
    init_schema(conn)  # must not raise
