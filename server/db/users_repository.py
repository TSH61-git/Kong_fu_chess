# Repository Pattern: sqlite3/SQL never appear outside this file. Every
# public method is async, wrapping a sync body via asyncio.to_thread so
# callers (auth/service.py, game/match.py) never block the event loop.
from __future__ import annotations

import asyncio
import sqlite3
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class UserRecord:
    id: int
    username: str
    password_hash: str
    salt: str
    elo: int


class UsernameTakenError(Exception):
    pass


class UsersRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    async def create(self, username: str, password_hash: str, salt: str, elo: int = 1200) -> UserRecord:
        return await asyncio.to_thread(self._create_sync, username, password_hash, salt, elo)

    def _create_sync(self, username: str, password_hash: str, salt: str, elo: int) -> UserRecord:
        try:
            cursor = self._conn.execute(
                "INSERT INTO users (username, password_hash, salt, elo, created_at) VALUES (?, ?, ?, ?, ?)",
                (username, password_hash, salt, elo, time.time()),
            )
            self._conn.commit()
        except sqlite3.IntegrityError as exc:
            raise UsernameTakenError(username) from exc
        return UserRecord(id=cursor.lastrowid, username=username, password_hash=password_hash, salt=salt, elo=elo)

    async def get_by_username(self, username: str) -> Optional[UserRecord]:
        return await asyncio.to_thread(self._get_by_username_sync, username)

    def _get_by_username_sync(self, username: str) -> Optional[UserRecord]:
        row = self._conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return _row_to_record(row) if row is not None else None

    async def get_by_id(self, user_id: int) -> Optional[UserRecord]:
        return await asyncio.to_thread(self._get_by_id_sync, user_id)

    def _get_by_id_sync(self, user_id: int) -> Optional[UserRecord]:
        row = self._conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return _row_to_record(row) if row is not None else None

    async def update_elo(self, user_id: int, elo: int) -> None:
        await asyncio.to_thread(self._update_elo_sync, user_id, elo)

    def _update_elo_sync(self, user_id: int, elo: int) -> None:
        self._conn.execute("UPDATE users SET elo = ? WHERE id = ?", (elo, user_id))
        self._conn.commit()


def _row_to_record(row: sqlite3.Row) -> UserRecord:
    return UserRecord(
        id=row["id"], username=row["username"], password_hash=row["password_hash"],
        salt=row["salt"], elo=row["elo"],
    )
