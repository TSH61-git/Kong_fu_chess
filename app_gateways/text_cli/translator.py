# Translator — sole boundary between raw text tokens and typed Piece objects.
from __future__ import annotations
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.model.board import Board
from chess_engine.model.position import Position

_VALID_TOKENS = frozenset({
    "wK", "bK", "wR", "bR", "wB", "bB",
    "wQ", "bQ", "wN", "bN", "wP", "bP", ".",
})

_COLOR_MAP: dict[str, Color] = {"w": Color.WHITE, "b": Color.BLACK}
_TYPE_MAP: dict[str, PieceType] = {
    "K": PieceType.KING,   "Q": PieceType.QUEEN,  "R": PieceType.ROOK,
    "B": PieceType.BISHOP, "N": PieceType.KNIGHT, "P": PieceType.PAWN,
}
_TYPE_CHAR: dict[PieceType, str] = {v: k for k, v in _TYPE_MAP.items()}
_COLOR_CHAR: dict[Color, str] = {v: k for k, v in _COLOR_MAP.items()}


def token_to_piece(token: str) -> Piece | None:
    # Parse a raw token string into a typed Piece, or None for empty cells.
    if token == ".":
        return None
    if token not in _VALID_TOKENS:
        raise ValueError(f"Unknown token: '{token}'.")
    return Piece(_TYPE_MAP[token[1]], _COLOR_MAP[token[0]])


def piece_to_token(piece: Piece | None) -> str:
    # Serialize a typed Piece back to its raw token string, or "." for None.
    if piece is None:
        return "."
    return _COLOR_CHAR[piece.color] + _TYPE_CHAR[piece.piece_type]


def is_valid_token(token: str) -> bool:
    return token in _VALID_TOKENS


def board_from_token_lines(lines: list[str]) -> Board:
    # Build a typed Board from a list of token-row strings.
    rows_data = [line.split() for line in lines if line.strip()]
    if not rows_data:
        raise ValueError("Board input is empty — no valid rows found.")
    expected_width = len(rows_data[0])
    for row in rows_data:
        if len(row) != expected_width:
            raise ValueError(
                f"Row width mismatch: expected {expected_width}, got {len(row)}."
            )
    board = Board(rows=len(rows_data), cols=expected_width)
    for r, row in enumerate(rows_data):
        for c, tok in enumerate(row):
            board.set(Position(r, c), token_to_piece(tok))
    return board


def board_to_token_lines(board: Board) -> list[str]:
    # Serialize a typed Board back to a list of token-row strings.
    return [
        " ".join(piece_to_token(board.get(Position(r, c))) for c in range(board.cols))
        for r in range(board.rows)
    ]
