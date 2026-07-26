# Guard: verifies both source and destination are within board boundaries.
from __future__ import annotations
from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.rules.reasons import MoveRejectReason


def check(board: Board, source: Position, destination: Position) -> str | None:
    if not board.is_inside(source) or not board.is_inside(destination):
        return MoveRejectReason.OUTSIDE_BOARD
    return None
