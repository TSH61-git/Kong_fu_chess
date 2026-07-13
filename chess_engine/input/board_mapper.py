# Pixel-to-grid coordinate adapter for the input layer.
from __future__ import annotations

from typing import Optional

from chess_engine.model.board import Board
from chess_engine.model.position import Position
from config import CELL_SIZE


class BoardMapper:
    def __init__(self, board: Board) -> None:
        self._board = board

    def pixel_to_cell(self, x: int, y: int) -> Optional[Position]:
        if x < 0 or y < 0:
            return None
        pos = Position(row=y // CELL_SIZE, col=x // CELL_SIZE)
        return pos if self._board.is_inside(pos) else None
