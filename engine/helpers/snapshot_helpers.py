"""Pure helpers for building read-only board snapshots."""
from __future__ import annotations

from typing import List, Optional

from model.board import Board
from model.position import Position
from engine.helpers.snapshot_models import GameSnapshot


def build_board_grid(board: Board) -> List[List[str]]:
    """Return a deep-copied 2-D token matrix for the current board state."""
    return [
        [board.get(Position(row, col)) for col in range(board.cols)]
        for row in range(board.rows)
    ]


def build_snapshot(
    board: Board,
    selected_cell: Optional[Position],
    game_over: bool,
) -> GameSnapshot:
    """Construct an immutable snapshot DTO from the live board state."""
    return GameSnapshot(
        board_width=board.cols,
        board_height=board.rows,
        board_grid=build_board_grid(board),
        selected_cell=selected_cell,
        game_over=game_over,
    )
