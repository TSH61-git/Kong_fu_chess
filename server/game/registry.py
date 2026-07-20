# MatchRegistry — the sole strong-referencing owner of every live
# MatchSession. Exists only for the matchmaker to hand a fresh match off to
# (add) and clean up after (remove, wired as MatchSession's on_ended
# callback) — never consulted by the per-connection message loop, which
# finds a session's match via session.current_match instead.
from __future__ import annotations

from typing import Optional

from server.game.match import MatchSession


class MatchRegistry:
    def __init__(self) -> None:
        self._matches: dict[str, MatchSession] = {}

    def add(self, match: MatchSession) -> None:
        self._matches[match.room_id] = match

    def remove(self, match: MatchSession) -> None:
        self._matches.pop(match.room_id, None)

    def get(self, room_id: str) -> Optional[MatchSession]:
        return self._matches.get(room_id)

    def __len__(self) -> int:
        return len(self._matches)
