# Test-only board-from-tokens parser, owned by chess_engine's own test suite
# so engine tests never depend on a gateway module (app_gateways.text_cli
# owns an equivalent parser for its own CLI input, kept separate on purpose).
from __future__ import annotations

from chess_engine.model.board import Board
from chess_engine.model.piece import Color, Piece, PieceType
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


def _token_to_piece(token: str) -> Piece | None:
    if token == ".":
        return None
    if token not in _VALID_TOKENS:
        raise ValueError(f"Unknown token: '{token}'.")
    return Piece(_TYPE_MAP[token[1]], _COLOR_MAP[token[0]])


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
            board.set(Position(r, c), _token_to_piece(tok))
    return board
