# MatchSession — the fixed two-slot match abstraction used through Phases 1-4.
# No room ID, no viewer roster: those belong to game/rooms.py from Phase 5
# onward, which generalizes this class rather than replacing it.
from __future__ import annotations

import asyncio
import logging
from enum import Enum, auto
from typing import Optional

from chess_engine.engine.events import GameOver
from chess_engine.wire.notation import serialize_board
from chess_engine.wire.state import serialize_cooldowns, serialize_motions
from websockets.asyncio.server import ServerConnection

from server import config
from server.core.bus import Bus
from server.core.clock import Clock
from server.game.engine_bridge import EngineEventRelay, RoomBroadcaster
from server.game.engine_factory import EngineStack, build_game_stack
from server.game.events import RoomMatchReady, RoomStateTick
from server.network.session import ClientSession, Role

_logger = logging.getLogger("kfchess.match")


class MatchStatus(Enum):
    ACTIVE = auto()
    ENDED = auto()


class MatchSession:
    room_id = "default"

    def __init__(self, bus: Bus, clock: Clock, tick_ms: int = config.TICK_MS) -> None:
        self.stack: EngineStack = build_game_stack()
        self.bus = bus
        self.clock = clock
        self.tick_ms = tick_ms
        self.status = MatchStatus.ACTIVE
        self.white: Optional[ClientSession] = None
        self.black: Optional[ClientSession] = None

        self._broadcaster = RoomBroadcaster(bus, self.room_id, self._sessions)
        EngineEventRelay(self.stack.engine, bus, self.room_id)
        self.stack.engine.events.subscribe(GameOver, self._on_game_over)
        self._tick_task = asyncio.create_task(self._run_tick_loop())

    def _sessions(self) -> list[ClientSession]:
        return [session for session in (self.white, self.black) if session is not None]

    def try_seat(self, session_id: str, websocket: ServerConnection) -> Optional[ClientSession]:
        # Seats the 1st connection as White, the 2nd as Black, refuses a 3rd —
        # the only place a session's role is ever assigned.
        if self.white is None:
            role = Role.WHITE
        elif self.black is None:
            role = Role.BLACK
        else:
            return None
        session = ClientSession(session_id, websocket, role)
        if role is Role.WHITE:
            self.white = session
        else:
            self.black = session
            self.bus.publish(
                f"room:{self.room_id}", RoomMatchReady(ts=self.clock.now(), room_id=self.room_id),
            )
        return session

    def release(self, session: ClientSession) -> None:
        if self.white is session:
            self.white = None
        elif self.black is session:
            self.black = None

    def end(self, reason: str) -> None:
        if self.status is MatchStatus.ENDED:
            return
        self.status = MatchStatus.ENDED
        _logger.info("Match %s ended: %s", self.room_id, reason)
        # Scheduled rather than awaited here: this may be called from inside
        # the tick loop's own coroutine (a king-capture GameOver fires while
        # _run_tick_loop is mid-iteration), and a task cannot safely cancel
        # and await itself.
        asyncio.create_task(self._teardown())

    async def _teardown(self) -> None:
        self._tick_task.cancel()
        self._broadcaster.close()

    def _on_game_over(self, _event: GameOver) -> None:
        self.end(reason="king_captured")

    async def _run_tick_loop(self) -> None:
        try:
            while self.status is MatchStatus.ACTIVE:
                await asyncio.sleep(self.tick_ms / 1000)
                self.stack.engine.advance_time(self.tick_ms)
                self.bus.publish(
                    f"room:{self.room_id}",
                    RoomStateTick(
                        ts=self.clock.now(),
                        room_id=self.room_id,
                        board_grid=serialize_board(self.stack.board),
                        active_motions=serialize_motions(self.stack.arbiter.get_active_motions()),
                        cooldowns=serialize_cooldowns(self.stack.arbiter.get_cooldowns()),
                        game_over=self.status is MatchStatus.ENDED,
                    ),
                )
        except asyncio.CancelledError:
            pass
