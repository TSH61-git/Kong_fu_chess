# ClientSession — one per WebSocket connection. A connection starts
# unseated (`role=None`) and unauthenticated (`user_id=None`). Both are
# mutated exactly once, together, post-construction: only
# game/match.py::try_seat sets `role`, and only server/auth/commands.py
# calls try_seat, and only after a successful register/login. Never derived
# from or mutated by any other inbound client message —
# game/commands.py's authorization gate depends on that invariant.
from __future__ import annotations

from enum import Enum, auto
from typing import Optional

from websockets.asyncio.server import ServerConnection


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

    async def send(self, message: str) -> None:
        await self.websocket.send(message)
