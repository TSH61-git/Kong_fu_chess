# Server-level Bus event vocabulary for room/match activity. Each chess_engine
# domain event (MoveAccepted, PieceCaptured, GameOver) is relayed onto one of
# these by game/engine_bridge.py's EngineEventRelay; RoomStateTick has no
# chess_engine analogue and is published directly by the match's tick loop.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from chess_engine.model.piece import Color, PieceType
from chess_engine.model.position import Position

from server.core.events import ServerEvent


@dataclass(frozen=True)
class RoomEvent(ServerEvent):
    room_id: str


@dataclass(frozen=True)
class RoomMoveAccepted(RoomEvent):
    color: Color
    piece_type: PieceType
    source: Position
    destination: Position
    is_capture: bool


@dataclass(frozen=True)
class RoomPieceCaptured(RoomEvent):
    piece_type: PieceType
    piece_color: Color
    captured_by: Color


@dataclass(frozen=True)
class RoomGameOver(RoomEvent):
    reason: str
    winner_username: Optional[str] = None


@dataclass(frozen=True)
class RoomMatchReady(RoomEvent):
    white_username: str
    black_username: str


@dataclass(frozen=True)
class RoomStateTick(RoomEvent):
    board_grid: list[list[Optional[str]]]
    active_motions: list[dict]
    cooldowns: list[dict]
    game_over: bool
