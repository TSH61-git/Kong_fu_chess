# Translation between chess_engine domain types and wire-protocol strings:
# algebraic squares <-> Position, "WQe2e5"-style move commands, and the
# board-token scheme used to serialize/deserialize a Board for the network.
# Shared, neutral ground between the server and any client (network gateway
# or GUI) — neither side owns this module, both depend on chess_engine.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from chess_engine.model.board import Board
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position

_FILES = "abcdefgh"
_BOARD_SIZE = 8

_COLOR_LETTERS: dict[str, Color] = {"W": Color.WHITE, "B": Color.BLACK}
_PIECE_LETTERS: dict[str, PieceType] = {
    "K": PieceType.KING, "Q": PieceType.QUEEN, "R": PieceType.ROOK,
    "B": PieceType.BISHOP, "N": PieceType.KNIGHT, "P": PieceType.PAWN,
}
_COLOR_TO_TOKEN_LETTER: dict[Color, str] = {Color.WHITE: "w", Color.BLACK: "b"}
_TOKEN_LETTER_TO_COLOR: dict[str, Color] = {v: k for k, v in _COLOR_TO_TOKEN_LETTER.items()}
_PIECE_TYPE_TO_TOKEN_LETTER: dict[PieceType, str] = {v: k for k, v in _PIECE_LETTERS.items()}
_TOKEN_LETTER_TO_PIECE_TYPE: dict[str, PieceType] = _PIECE_LETTERS


class MalformedMoveCommandError(Exception):
    pass


@dataclass(frozen=True)
class ParsedMoveCommand:
    color: Color
    piece_type: PieceType
    source: Position
    destination: Position


def square_to_position(square: str) -> Position:
    if len(square) != 2 or square[0] not in _FILES or not square[1].isdigit():
        raise MalformedMoveCommandError(f"invalid square: {square!r}")
    rank = int(square[1])
    if not 1 <= rank <= _BOARD_SIZE:
        raise MalformedMoveCommandError(f"invalid square: {square!r}")
    return Position(row=_BOARD_SIZE - rank, col=_FILES.index(square[0]))


def position_to_square(position: Position) -> str:
    return f"{_FILES[position.col]}{_BOARD_SIZE - position.row}"


def parse_move_command(raw: str) -> ParsedMoveCommand:
    # Fixed 6-character format: color letter, piece letter, source square,
    # destination square — e.g. "WQe2e5". Only supports standard 8x8 boards.
    if len(raw) != 6:
        raise MalformedMoveCommandError(f"expected a 6-character move command, got {raw!r}")
    color_letter, piece_letter = raw[0], raw[1]
    if color_letter not in _COLOR_LETTERS:
        raise MalformedMoveCommandError(f"unknown color letter: {color_letter!r}")
    if piece_letter not in _PIECE_LETTERS:
        raise MalformedMoveCommandError(f"unknown piece letter: {piece_letter!r}")
    return ParsedMoveCommand(
        color=_COLOR_LETTERS[color_letter],
        piece_type=_PIECE_LETTERS[piece_letter],
        source=square_to_position(raw[2:4]),
        destination=square_to_position(raw[4:6]),
    )


def build_move_command(color: Color, piece_type: PieceType, source: Position, destination: Position) -> str:
    return (
        _COLOR_TO_TOKEN_LETTER[color].upper()
        + _PIECE_TYPE_TO_TOKEN_LETTER[piece_type]
        + position_to_square(source)
        + position_to_square(destination)
    )


def piece_to_wire_token(piece: Optional[Piece]) -> Optional[str]:
    if piece is None:
        return None
    return _COLOR_TO_TOKEN_LETTER[piece.color] + _PIECE_TYPE_TO_TOKEN_LETTER[piece.piece_type]


def wire_token_to_piece(token: Optional[str]) -> Optional[Piece]:
    if token is None:
        return None
    return Piece(_TOKEN_LETTER_TO_PIECE_TYPE[token[1]], _TOKEN_LETTER_TO_COLOR[token[0]])


def serialize_board(board: Board) -> list[list[Optional[str]]]:
    return [
        [piece_to_wire_token(board.get(Position(row, col))) for col in range(board.cols)]
        for row in range(board.rows)
    ]


def refresh_board(board: Board, wire_grid: list[list[Optional[str]]]) -> None:
    # Overwrites every cell of an existing Board in place from a wire grid —
    # used by network clients to keep a persistent mirror in sync, rather
    # than reconstructing a fresh Board (and rebinding every reference to
    # it) on every update.
    for row, row_tokens in enumerate(wire_grid):
        for col, token in enumerate(row_tokens):
            board.set(Position(row, col), wire_token_to_piece(token))
