# Mutable motion state for a single in-flight piece movement.
from __future__ import annotations
from dataclasses import dataclass
from chess_engine.model.piece import Piece
from chess_engine.model.position import Position


@dataclass(eq=False)
class Motion:
    # Mutable state for a single in-flight piece movement.
    piece: Piece
    source: Position
    destination: Position
    elapsed_ms: int = 0
    duration_ms: int = 0
