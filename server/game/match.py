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
from server.game.events import (
    RoomGameOver,
    RoomMatchReady,
    RoomOpponentDisconnected,
    RoomOpponentReconnected,
    RoomStateTick,
)
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
        disconnect_grace_seconds: float = config.DISCONNECT_GRACE_SECONDS,
    ) -> None:
        self.room_id = str(uuid.uuid4())
        self.stack: EngineStack = build_game_stack()
        self.bus = bus
        self.clock = clock
        self.auth_service = auth_service
        self._matches_repo = matches_repo
        self.tick_ms = tick_ms
        self._on_ended = on_ended
        self._disconnect_grace_seconds = disconnect_grace_seconds
        self.status = MatchStatus.ACTIVE
        self.white: Optional[ClientSession] = None
        self.black: Optional[ClientSession] = None
        self._winner_color: Optional[Color] = None
        # Populated once per seat by try_seat and never cleared, so forfeit/
        # Elo bookkeeping (and reconnect lookup) survives a seat's live
        # ClientSession being released on disconnect.
        self._seat_user_ids: dict[Role, Optional[int]] = {}
        self._seat_usernames: dict[Role, Optional[str]] = {}
        # True whenever either seat is mid disconnect-grace-period: freezes
        # the tick loop (game clock/cooldowns) and rejects moves, so the
        # connected player gets no advantage while the other is away.
        self._frozen = False
        self._disconnect_task: Optional[asyncio.Task] = None
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

    @property
    def is_frozen(self) -> bool:
        return self._frozen

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
            self._seat_user_ids[Role.WHITE] = session.user_id
            self._seat_usernames[Role.WHITE] = session.username
        elif self.black is None:
            self.black = session
            session.role = Role.BLACK
            session.current_match = self
            self._seat_user_ids[Role.BLACK] = session.user_id
            self._seat_usernames[Role.BLACK] = session.username
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

    def handle_disconnect(self, session: ClientSession) -> None:
        role = session.role
        if role is None:
            return
        self.release(session)
        if self.status is MatchStatus.ENDED:
            return

        other_seat = self.black if role is Role.WHITE else self.white
        if other_seat is None:
            # Both seats are now empty (simultaneous or overlapping
            # disconnects) — no one to auto-resign to. Cancel any pending
            # single-disconnect timer so it can't fire after end() tears the
            # match down, and end the match as a no-contest (scored as a
            # draw by _record_result's white_won=None path).
            if self._disconnect_task is not None:
                self._disconnect_task.cancel()
                self._disconnect_task = None
            self._frozen = False
            self.end(reason="both_disconnected")
            return

        self._frozen = True
        self.bus.publish(
            f"room:{self.room_id}", RoomOpponentDisconnected(
                ts=self.clock.now(), room_id=self.room_id,
                role=role.name.lower(), countdown_seconds=self._disconnect_grace_seconds,
            ),
        )
        self._disconnect_task = asyncio.create_task(self._disconnect_timeout(role))

    async def _disconnect_timeout(self, role: Role) -> None:
        try:
            await asyncio.sleep(self._disconnect_grace_seconds)
        except asyncio.CancelledError:
            return
        if self.status is MatchStatus.ENDED:
            return
        seat = self.white if role is Role.WHITE else self.black
        if seat is not None:
            return  # reconnected before the grace period ran out
        self._winner_color = Color.BLACK if role is Role.WHITE else Color.WHITE
        self.end(reason="disconnect_timeout")

    def reconnect(self, user_id: int, session: ClientSession) -> Optional[Role]:
        if self.status is MatchStatus.ENDED:
            return None
        for role in (Role.WHITE, Role.BLACK):
            seat = self.white if role is Role.WHITE else self.black
            if seat is not None or self._seat_user_ids.get(role) != user_id:
                continue
            if role is Role.WHITE:
                self.white = session
            else:
                self.black = session
            session.role = role
            session.current_match = self
            self._seat_usernames[role] = session.username

            if self._disconnect_task is not None:
                self._disconnect_task.cancel()
                self._disconnect_task = None
            self._frozen = False
            self.bus.publish(
                f"room:{self.room_id}", RoomOpponentReconnected(
                    ts=self.clock.now(), room_id=self.room_id, role=role.name.lower(),
                ),
            )
            self._publish_state_tick()
            return role
        return None

    def is_awaiting_reconnect(self, user_id: int) -> bool:
        if self.status is MatchStatus.ENDED:
            return False
        for role in (Role.WHITE, Role.BLACK):
            seat = self.white if role is Role.WHITE else self.black
            if seat is None and self._seat_user_ids.get(role) == user_id:
                return True
        return False

    def end(self, reason: str) -> None:
        if self.status is MatchStatus.ENDED:
            return
        self.status = MatchStatus.ENDED
        _logger.info("Match %s ended: %s", self.room_id, reason)
        if reason != "king_captured":
            # The king-capture path already gets a RoomGameOver broadcast
            # from EngineEventRelay reacting to chess_engine's own GameOver
            # event; every other ending (disconnect forfeit, no-contest) has
            # no engine-side event to react to, so it's published here instead.
            self.bus.publish(
                f"room:{self.room_id}", RoomGameOver(
                    ts=self.clock.now(), room_id=self.room_id,
                    reason=reason, winner_username=self._winner_username(),
                ),
            )
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
        if self._disconnect_task is not None:
            self._disconnect_task.cancel()
            self._disconnect_task = None
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
        # Reads persisted seat identity rather than the (possibly already
        # None, e.g. after a disconnect) white/black session parameters, so
        # a forfeited match still records a result and updates Elo. Skips
        # silently only for a guest match: a fully passive, never-
        # authenticated player had their king captured without ever moving
        # (pieces act independently here, no turns, so that's a real case).
        white_user_id = self._seat_user_ids.get(Role.WHITE)
        black_user_id = self._seat_user_ids.get(Role.BLACK)
        if white_user_id is None or black_user_id is None:
            return

        winner_user_id: Optional[int] = None
        if self._winner_color is Color.WHITE:
            winner_user_id = white_user_id
        elif self._winner_color is Color.BLACK:
            winner_user_id = black_user_id
        await self._matches_repo.record_result(white_user_id, black_user_id, winner_user_id, reason)

        users_repo = self.auth_service.users_repo
        white_user = await users_repo.get_by_id(white_user_id)
        black_user = await users_repo.get_by_id(black_user_id)
        white_won = None if winner_user_id is None else winner_user_id == white_user_id
        new_white_elo, new_black_elo = elo.update_ratings(white_user.elo, black_user.elo, white_won)
        await users_repo.update_elo(white_user_id, new_white_elo)
        await users_repo.update_elo(black_user_id, new_black_elo)

    def _on_piece_captured(self, event: PieceCaptured) -> None:
        if event.piece.piece_type is PieceType.KING:
            self._winner_color = event.captured_by

    def _winner_username(self) -> Optional[str]:
        # Read from persisted seat identity rather than the live self.white/
        # self.black sessions, which may already be None by the time this is
        # read (e.g. a disconnect-timeout forfeit reads it after the losing
        # seat has already been released).
        role = {Color.WHITE: Role.WHITE, Color.BLACK: Role.BLACK}.get(self._winner_color)
        return self._seat_usernames.get(role) if role is not None else None

    def _on_game_over(self, _event: GameOver) -> None:
        self.end(reason="king_captured")

    async def _run_tick_loop(self) -> None:
        try:
            while self.status is MatchStatus.ACTIVE:
                await asyncio.sleep(self.tick_ms / 1000)
                if self._frozen:
                    continue
                self.stack.engine.advance_time(self.tick_ms)
                self._publish_state_tick()
        except asyncio.CancelledError:
            pass

    def _publish_state_tick(self) -> None:
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
