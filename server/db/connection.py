# SQLite connection factory. check_same_thread=False because repository
# methods run their sync bodies via asyncio.to_thread, which may hand
# consecutive calls to different worker threads.
from __future__ import annotations

import sqlite3


def create_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
