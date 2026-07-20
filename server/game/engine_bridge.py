# Adapter — bridges chess_engine's synchronous EventManager onto the async
# Bus (EngineEventRelay), and fans a room's Bus events out to its connected
# sockets (RoomBroadcaster). The two are separate subscribers so a slow client
# socket write can never stall engine.request_move()/advance_time().
from __future__ import annotations

import time
from typing import Callable, Iterable, Optional

from chess_engine.engine.events import GameOver, MoveAccepted, PieceCaptured
from chess_engine.engine.game_engine import GameEngine
from chess_engine.wire.notation import position_to_square

from server.core.bus import Bus, Unsubscribe
from server.core.protocol import encode_broadcast
from server.game.events import (
    RoomGameOver,
    RoomMatchReady,
    RoomMoveAccepted,
    RoomPieceCaptured,
    RoomStateTick,
)
from server.network.session import ClientSession


class EngineEventRelay:
    # Constructed once per match/room, mirroring the MoveHistory/ScoreManager
    # "subscribe a helper at construction" convention already used inside
    # chess_engine.engine.game_engine.GameEngine.

    def __init__(
        self, engine: GameEngine, bus: Bus, room_id: str,
        winner_provider: Callable[[], Optional[str]] = lambda: None,
    ) -> None:
        self._bus = bus
        self._room_id = room_id
        self._winner_provider = winner_provider
        engine.events.subscribe(MoveAccepted, self._on_move_accepted)
        engine.events.subscribe(PieceCaptured, self._on_piece_captured)
        engine.events.subscribe(GameOver, self._on_game_over)

    def _on_move_accepted(self, event: MoveAccepted) -> None:
        self._publish(RoomMoveAccepted(
            ts=time.time(), room_id=self._room_id,
            color=event.color, piece_type=event.piece_type,
            source=event.source, destination=event.destination,
            is_capture=event.is_capture,
        ))

    def _on_piece_captured(self, event: PieceCaptured) -> None:
        self._publish(RoomPieceCaptured(
            ts=time.time(), room_id=self._room_id,
            piece_type=event.piece.piece_type, piece_color=event.piece.color,
            captured_by=event.captured_by,
        ))

    def _on_game_over(self, _event: GameOver) -> None:
        self._publish(RoomGameOver(
            ts=time.time(), room_id=self._room_id, reason="king_captured",
            winner_username=self._winner_provider(),
        ))

    def _publish(self, event: object) -> None:
        self._bus.publish(f"room:{self._room_id}", event)


class RoomBroadcaster:
    def __init__(
        self, bus: Bus, room_id: str, sessions: Callable[[], Iterable[ClientSession]],
    ) -> None:
        self._room_id = room_id
        self._sessions = sessions
        self._unsubscribe: Unsubscribe = bus.subscribe(f"room:{room_id}", self._on_room_event)

    async def _on_room_event(self, event: object) -> None:
        message = _encode_room_event(self._room_id, event)
        for session in self._sessions():
            await session.send(message)

    def close(self) -> None:
        self._unsubscribe()


def _encode_move_accepted(event: RoomMoveAccepted) -> tuple[str, dict]:
    return "move_accepted", {
        "color": event.color.name.lower(),
        "piece_type": event.piece_type.name.lower(),
        "source": position_to_square(event.source),
        "destination": position_to_square(event.destination),
        "is_capture": event.is_capture,
    }


def _encode_piece_captured(event: RoomPieceCaptured) -> tuple[str, dict]:
    return "piece_captured", {
        "piece_type": event.piece_type.name.lower(),
        "piece_color": event.piece_color.name.lower(),
        "captured_by": event.captured_by.name.lower(),
    }


def _encode_game_over(event: RoomGameOver) -> tuple[str, dict]:
    return "game_over", {"reason": event.reason, "winner_username": event.winner_username}


def _encode_state_tick(event: RoomStateTick) -> tuple[str, dict]:
    return "state_tick", {
        "board_grid": event.board_grid,
        "active_motions": event.active_motions,
        "cooldowns": event.cooldowns,
        "game_over": event.game_over,
    }


def _encode_match_ready(event: RoomMatchReady) -> tuple[str, dict]:
    return "match_ready", {"white_username": event.white_username, "black_username": event.black_username}


_ENCODERS: dict[type, Callable[[object], tuple[str, dict]]] = {
    RoomMoveAccepted: _encode_move_accepted,
    RoomPieceCaptured: _encode_piece_captured,
    RoomGameOver: _encode_game_over,
    RoomStateTick: _encode_state_tick,
    RoomMatchReady: _encode_match_ready,
}


def _encode_room_event(room_id: str, event: object) -> str:
    event_name, data = _ENCODERS[type(event)](event)
    return encode_broadcast(room_id, event_name, data)
