# Material score bookkeeping — the engine's single source of truth for
# "who captured what," so the GUI only ever displays pre-computed numbers.
from __future__ import annotations

import time
from dataclasses import dataclass

from chess_engine.model.piece import Color, Piece, PieceType

_DEFAULT = 5

PIECE_VALUES: dict[PieceType, int] = {
    PieceType.QUEEN:  9,
    PieceType.ROOK:   5,
    PieceType.BISHOP: 3,
    PieceType.KNIGHT: 3,
    PieceType.PAWN:   1,
    PieceType.KING:   10,
}


@dataclass(frozen=True)
class CapturedEntry:
    piece: Piece
    captured_by: Color
    timestamp: float


class ScoreManager:
    def __init__(self) -> None:
        self._entries: list[CapturedEntry] = []

    def record_capture(self, piece: Piece, captured_by: Color) -> None:
        self._entries.append(CapturedEntry(
            piece=piece, captured_by=captured_by, timestamp=time.time(),
        ))

    def get_captured(self, color: Color) -> list[CapturedEntry]:
        return [e for e in self._entries if e.captured_by == color]

    def get_scores(self) -> dict[Color, int]:
        return {
            color: sum(PIECE_VALUES[e.piece.piece_type] for e in self.get_captured(color))
            for color in (Color.WHITE, Color.BLACK)
        }
