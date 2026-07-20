# Idempotent DDL, run once at process startup by the composition root.
from __future__ import annotations

import sqlite3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    elo INTEGER NOT NULL DEFAULT 1200,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    white_user_id INTEGER NOT NULL REFERENCES users(id),
    black_user_id INTEGER NOT NULL REFERENCES users(id),
    winner_user_id INTEGER REFERENCES users(id),
    reason TEXT NOT NULL,
    ended_at REAL NOT NULL
);
"""


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()
