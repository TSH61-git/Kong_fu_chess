# ClientSession — one per WebSocket connection. `role` is assigned exactly
# once, at construction, by server-side join logic (see game/match.py's
# try_seat); it is never derived from or mutated by an inbound client message.
# game/commands.py's authorization gate depends on that invariant.
from __future__ import annotations

from enum import Enum, auto

from websockets.asyncio.server import ServerConnection


class Role(Enum):
    WHITE = auto()
    BLACK = auto()


class ClientSession:
    def __init__(self, session_id: str, websocket: ServerConnection, role: Role) -> None:
        self.session_id = session_id
        self.websocket = websocket
        self.role = role

    async def send(self, message: str) -> None:
        await self.websocket.send(message)
