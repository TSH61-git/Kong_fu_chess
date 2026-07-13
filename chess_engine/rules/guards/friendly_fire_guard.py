# Guard: rejects moves where the destination holds a friendly piece.
from __future__ import annotations
from chess_engine.model.board import Board
from chess_engine.model.position import Position


def check(board: Board, source: Position, destination: Position) -> str | None:
    src = board.get(source)
    dst = board.get(destination)
    if src is not None and dst is not None and dst.color == src.color:
        return "friendly_destination"
    return None
