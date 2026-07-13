# Typed chess board — stores Piece objects or None, fully string-blind.
from __future__ import annotations
from typing import List, Optional
from chess_engine.model.position import Position
from chess_engine.model.piece import Piece


class Board:
    # Logical chess board; cells store Piece | None.

    def __init__(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._grid: List[List[Optional[Piece]]] = [
            [None] * cols for _ in range(rows)
        ]

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    def is_inside(self, pos: Position) -> bool:
        return 0 <= pos.row < self._rows and 0 <= pos.col < self._cols

    def get(self, pos: Position) -> Optional[Piece]:
        self._require_inside(pos)
        return self._grid[pos.row][pos.col]

    def set(self, pos: Position, piece: Optional[Piece]) -> None:
        self._require_inside(pos)
        self._grid[pos.row][pos.col] = piece

    def _require_inside(self, pos: Position) -> None:
        if not self.is_inside(pos):
            raise ValueError(
                f"Position {pos} is outside the board ({self._rows}×{self._cols})."
            )
