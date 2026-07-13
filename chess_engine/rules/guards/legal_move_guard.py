# Guard: rejects destinations outside the piece's legal movement set.
from __future__ import annotations
from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.rules.movement import legal_destinations


def check(board: Board, source: Position, destination: Position) -> str | None:
    piece = board.get(source)
    if piece is None:
        return "empty_source"
    if destination not in legal_destinations(board, source, piece):
        return "illegal_piece_move"
    return None
