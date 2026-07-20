# ClientSession — one per WebSocket connection. A connection starts
# unseated (`role=None`, `current_match=None`) and unauthenticated
# (`user_id=None`). `role`/`current_match` are mutated together, exactly
# once per seating: only game/match.py's `try_seat` sets them (called only
# by the matchmaker, once a session is authenticated and paired), and only
# `release` clears them (both back to `None` together). Never derived from
# or mutated by any other inbound client message — game/commands.py's
# authorization gate depends on that invariant.
from __future__ import annotations

from enum import Enum, auto
from typing import TYPE_CHECKING, Optional

from websockets.asyncio.server import ServerConnection

if TYPE_CHECKING:
    from server.game.match import MatchSession


class Role(Enum):
    WHITE = auto()
    BLACK = auto()


class ClientSession:
    def __init__(self, session_id: str, websocket: ServerConnection, role: Optional[Role] = None) -> None:
        self.session_id = session_id
        self.websocket = websocket
        self.role: Optional[Role] = role
        self.user_id: Optional[int] = None
        self.username: Optional[str] = None
        self.current_match: Optional["MatchSession"] = None

    async def send(self, message: str) -> None:
        await self.websocket.send(message)
