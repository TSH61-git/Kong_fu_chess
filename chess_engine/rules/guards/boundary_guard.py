# Guard: verifies both source and destination are within board boundaries.
from __future__ import annotations
from chess_engine.model.board import Board
from chess_engine.model.position import Position


def check(board: Board, source: Position, destination: Position) -> str | None:
    if not board.is_inside(source) or not board.is_inside(destination):
        return "outside_board"
    return None
