# Pure typed chess piece domain model — no raw string tokens.
from enum import Enum, auto


class PieceType(Enum):
    KING   = auto()
    QUEEN  = auto()
    ROOK   = auto()
    BISHOP = auto()
    KNIGHT = auto()
    PAWN   = auto()


class Color(Enum):
    WHITE = auto()
    BLACK = auto()


class PieceState(Enum):
    IDLE     = auto()
    MOVING   = auto()
    CAPTURED = auto()


class Piece:
    # A chess piece identified by typed PieceType and Color enums.

    def __init__(self, piece_type: PieceType, color: Color) -> None:
        self._piece_type = piece_type
        self._color = color
        self.state = PieceState.IDLE

    @property
    def piece_type(self) -> PieceType:
        return self._piece_type

    @property
    def color(self) -> Color:
        return self._color

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Piece):
            return NotImplemented
        return self._piece_type == other._piece_type and self._color == other._color

    def __hash__(self) -> int:
        return hash((self._piece_type, self._color))

    def __repr__(self) -> str:
        return f"Piece({self._color.name}, {self._piece_type.name})"
