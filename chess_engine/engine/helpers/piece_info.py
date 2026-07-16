# Lightweight, immutable stand-in for "a piece's identity for display
# purposes" — used at engine -> GUI boundaries instead of the real Piece,
# so callers can't reach for mutable state (.state) or Piece internals
# that have nothing to do with rendering.
from __future__ import annotations

from dataclasses import dataclass

from chess_engine.model.piece import Color, Piece, PieceType


@dataclass(frozen=True)
class PieceInfo:
    piece_type: PieceType
    color: Color

    @classmethod
    def from_piece(cls, piece: Piece) -> "PieceInfo":
        return cls(piece_type=piece.piece_type, color=piece.color)
