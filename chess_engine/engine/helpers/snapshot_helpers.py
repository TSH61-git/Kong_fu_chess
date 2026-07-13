# Pure helpers for building read-only board snapshots.
from __future__ import annotations

from typing import List, Optional

from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.engine.helpers.snapshot_models import GameSnapshot


def build_board_grid(board: Board) -> List[List[str]]:
    return [
        [board.get(Position(row, col)) for col in range(board.cols)]
        for row in range(board.rows)
    ]


def build_snapshot(
    board: Board,
    selected_cell: Optional[Position],
    game_over: bool,
) -> GameSnapshot:
    return GameSnapshot(
        board_width=board.cols,
        board_height=board.rows,
        board_grid=build_board_grid(board),
        selected_cell=selected_cell,
        game_over=game_over,
    )
