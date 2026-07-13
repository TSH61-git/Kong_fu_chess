# Guard: rejects moves where the source cell holds no piece.
from __future__ import annotations
from chess_engine.model.board import Board
from chess_engine.model.position import Position


def check(board: Board, source: Position, destination: Position) -> str | None:
    if board.get(source) is None:
        return "empty_source"
    return None
