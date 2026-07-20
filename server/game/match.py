# MatchSession — the fixed two-slot match abstraction used through Phases 1-4.
# No viewer roster: that belongs to game/rooms.py from Phase 5 onward, which
# generalizes this class rather than replacing it. Since Phase 3, many
# MatchSessions can be alive at once (one per matchmaker pairing), so
# room_id is a per-instance UUID, not a shared class attribute.
from __future__ import annotations

import asyncio
import logging
import uuid
from enum import Enum, auto
from typing import Callable, Optional

from chess_engine.engine.events import GameOver, PieceCaptured
from chess_engine.model.piece import Color, PieceType
from chess_engine.wire.notation import serialize_board
from chess_engine.wire.state import serialize_cooldowns, serialize_motions

from server import config
from server.auth.service import AuthService
from server.core.bus import Bus
from server.core.clock import Clock
from server.db.matches_repository import MatchesRepository
from server.game.engine_bridge import EngineEventRelay, RoomBroadcaster
from server.game.engine_factory import EngineStack, build_game_stack
from server.game.events import RoomMatchReady, RoomStateTick
from server.network.session import ClientSession, Role
from server.rating import elo

_logger = logging.getLogger("kfchess.match")


class MatchStatus(Enum):
    ACTIVE = auto()
    ENDED = auto()


class MatchSession:
    def __init__(
        self,
        bus: Bus,
        clock: Clock,
        auth_service: AuthService,
        matches_repo: MatchesRepository,
        tick_ms: int = config.TICK_MS,
        on_ended: Optional[Callable[["MatchSession"], None]] = None,
    ) -> None:
        self.room_id = str(uuid.uuid4())
        self.stack: EngineStack = build_game_stack()
        self.bus = bus
        self.clock = clock
        self.auth_service = auth_service
        self._matches_repo = matches_repo
        self.tick_ms = tick_ms
        self._on_ended = on_ended
        self.status = MatchStatus.ACTIVE
        self.white: Optional[ClientSession] = None
        self.black: Optional[ClientSession] = None
        self._winner_color: Optional[Color] = None
        # Exposed so callers (mainly tests) can await actual completion of
        # end()'s background work instead of sleeping a guessed duration.
        self.teardown_task: Optional[asyncio.Task] = None
        self.record_result_task: Optional[asyncio.Task] = None

        self._broadcaster = RoomBroadcaster(bus, self.room_id, self._sessions)
        EngineEventRelay(self.stack.engine, bus, self.room_id, winner_provider=self._winner_username)
        self.stack.engine.events.subscribe(PieceCaptured, self._on_piece_captured)
        self.stack.engine.events.subscribe(GameOver, self._on_game_over)
        self._tick_task = asyncio.create_task(self._run_tick_loop())

    def _sessions(self) -> list[ClientSession]:
        return [session for session in (self.white, self.black) if session is not None]

    def try_seat(self, session: ClientSession) -> bool:
        # Seats the 1st already-authenticated session as White, the 2nd as
        # Black, refuses a 3rd — the only place a session's role is ever
        # assigned. Callers (server/auth/commands.py) only invoke this after
        # a successful register/login, so RoomMatchReady only ever fires
        # once two *authenticated* players hold the two seats.
        if self.white is None:
            self.white = session
            session.role = Role.WHITE
            session.current_match = self
        elif self.black is None:
            self.black = session
            session.role = Role.BLACK
            session.current_match = self
            self.bus.publish(
                f"room:{self.room_id}", RoomMatchReady(
                    ts=self.clock.now(), room_id=self.room_id,
                    white_username=self.white.username, black_username=self.black.username,
                ),
            )
        else:
            return False
        return True

    def release(self, session: ClientSession) -> None:
        if self.white is session:
            self.white = None
        elif self.black is session:
            self.black = None
        else:
            return
        session.role = None
        session.current_match = None

    def end(self, reason: str) -> None:
        if self.status is MatchStatus.ENDED:
            return
        self.status = MatchStatus.ENDED
        _logger.info("Match %s ended: %s", self.room_id, reason)
        # Snapshotted once, synchronously, and threaded into both tasks as
        # parameters: _teardown() releases these same seats (nulling
        # self.white/self.black), and since it has no await points it can
        # run to completion before _record_result() ever starts — reading
        # self.white/self.black inside _record_result() would then see None.
        white, black = self.white, self.black
        # Scheduled rather than awaited here: this may be called from inside
        # the tick loop's own coroutine (a king-capture GameOver fires while
        # _run_tick_loop is mid-iteration), and a task cannot safely cancel
        # and await itself.
        self.teardown_task = asyncio.create_task(self._teardown(white, black))
        self.record_result_task = asyncio.create_task(self._record_result(reason, white, black))

    async def _teardown(self, white: Optional[ClientSession], black: Optional[ClientSession]) -> None:
        self._tick_task.cancel()
        self._broadcaster.close()
        if white is not None:
            self.release(white)
        if black is not None:
            self.release(black)
        if self._on_ended is not None:
            self._on_ended(self)

    async def _record_result(
        self, reason: str, white: Optional[ClientSession], black: Optional[ClientSession],
    ) -> None:
        # Skips silently for a guest match: either seat disconnected before
        # the game ended, or a fully passive, never-authenticated player had
        # their king captured without ever moving (pieces act independently
        # here, no turns, so that's a real case, not just a race).
        if white is None or black is None or white.user_id is None or black.user_id is None:
            return

        winner_user_id: Optional[int] = None
        if self._winner_color is Color.WHITE:
            winner_user_id = white.user_id
        elif self._winner_color is Color.BLACK:
            winner_user_id = black.user_id
        await self._matches_repo.record_result(white.user_id, black.user_id, winner_user_id, reason)

        users_repo = self.auth_service.users_repo
        white_user = await users_repo.get_by_id(white.user_id)
        black_user = await users_repo.get_by_id(black.user_id)
        white_won = None if winner_user_id is None else winner_user_id == white.user_id
        new_white_elo, new_black_elo = elo.update_ratings(white_user.elo, black_user.elo, white_won)
        await users_repo.update_elo(white.user_id, new_white_elo)
        await users_repo.update_elo(black.user_id, new_black_elo)

    def _on_piece_captured(self, event: PieceCaptured) -> None:
        if event.piece.piece_type is PieceType.KING:
            self._winner_color = event.captured_by

    def _winner_username(self) -> Optional[str]:
        # Read by EngineEventRelay at GameOver time, once _winner_color has
        # already been set by _on_piece_captured above (the king-capture
        # PieceCaptured always fires before the GameOver it triggers).
        session = {Color.WHITE: self.white, Color.BLACK: self.black}.get(self._winner_color)
        return session.username if session is not None else None

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
