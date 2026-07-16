# Domain events published by GameEngine — the vocabulary components subscribe to.
from __future__ import annotations

from dataclasses import dataclass

from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position


@dataclass(frozen=True)
class MoveAccepted:
    color: Color
    piece_type: PieceType
    source: Position
    destination: Position
    is_capture: bool


@dataclass(frozen=True)
class PieceCaptured:
    piece: Piece
    captured_by: Color


@dataclass(frozen=True)
class GameOver:
    pass
