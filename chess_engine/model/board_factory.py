# Board construction helpers — standard starting positions.
from __future__ import annotations

from chess_engine.model.board import Board
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position

BOARD_SIZE = 8

_BACK_RANK = [
    PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
    PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK,
]


def standard_board() -> Board:
    # Build a standard 8×8 starting position board using typed Piece objects.
    board = Board(rows=BOARD_SIZE, cols=BOARD_SIZE)
    for col, piece_type in enumerate(_BACK_RANK):
        board.set(Position(0, col), Piece(piece_type, Color.BLACK))
        board.set(Position(1, col), Piece(PieceType.PAWN, Color.BLACK))
        board.set(Position(6, col), Piece(PieceType.PAWN, Color.WHITE))
        board.set(Position(7, col), Piece(piece_type, Color.WHITE))
    return board
