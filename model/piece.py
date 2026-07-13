"""Piece — chess piece with a pure IDLE/MOVING/CAPTURED lifecycle state."""
from enum import Enum, auto


class PieceState(Enum):
    """Lifecycle state of a piece. Exactly three values — nothing more."""
    IDLE     = auto()
    MOVING   = auto()
    CAPTURED = auto()


class Piece:
    """A chess piece identified by its token (e.g. 'wR', 'bK')."""

    def __init__(self, token: str) -> None:
        self.token = token
        self.state = PieceState.IDLE
