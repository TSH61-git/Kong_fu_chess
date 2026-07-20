# Repository Pattern, same async-wraps-sync split as users_repository.py.
from __future__ import annotations

import asyncio
import sqlite3
import time
from typing import Optional


class MatchesRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    async def record_result(
        self, white_user_id: int, black_user_id: int, winner_user_id: Optional[int], reason: str,
    ) -> None:
        await asyncio.to_thread(self._record_result_sync, white_user_id, black_user_id, winner_user_id, reason)

    def _record_result_sync(
        self, white_user_id: int, black_user_id: int, winner_user_id: Optional[int], reason: str,
    ) -> None:
        self._conn.execute(
            "INSERT INTO matches (white_user_id, black_user_id, winner_user_id, reason, ended_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (white_user_id, black_user_id, winner_user_id, reason, time.time()),
        )
        self._conn.commit()
