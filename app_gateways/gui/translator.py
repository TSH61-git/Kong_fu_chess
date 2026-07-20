from __future__ import annotations
import pathlib

from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.model.board import Board
from chess_engine.model.position import Position

PIECE_SET = "pieces_mine"

_TYPE_TO_FOLDER: dict[PieceType, str] = {
    PieceType.KING:   "K",
    PieceType.QUEEN:  "Q",
    PieceType.ROOK:   "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
    PieceType.PAWN:   "P",
}

_COLOR_TO_FOLDER: dict[Color, str] = {
    Color.WHITE: "W",
    Color.BLACK: "B",
}


def piece_to_asset_folder(piece: Piece) -> str:
    """Return the asset folder name for a piece, e.g. Piece(KING, WHITE) → 'KW'."""
    return _TYPE_TO_FOLDER[piece.piece_type] + _COLOR_TO_FOLDER[piece.color]


def piece_dir(piece: Piece, assets_dir: pathlib.Path, piece_set: str = PIECE_SET) -> pathlib.Path:
    """Return the full path to the piece's animation directory."""
    return assets_dir / piece_set / piece_to_asset_folder(piece)


def board_to_grid(board: Board) -> list[list[Piece | None]]:
    """Return a 2-D grid of Piece | None directly from the live board."""
    return [
        [board.get(Position(row, col)) for col in range(board.cols)]
        for row in range(board.rows)
    ]
