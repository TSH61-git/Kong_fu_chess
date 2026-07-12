"""
Piece — represents a chess piece with a pure lifecycle state.

PieceState is a strict 3-value Enum: IDLE, MOVING, CAPTURED.
It carries NO path, destination, speed, or timing information.
"""
from enum import Enum, auto


class PieceState(Enum):
    """Lifecycle state of a piece. Exactly three values — nothing more."""
    IDLE     = auto()
    MOVING   = auto()
    CAPTURED = auto()


class Piece:
    """
    A chess piece identified by its token (e.g. 'wR', 'bK').

    Attributes:
        token: Two-character string — color prefix + piece type (e.g. 'wR').
        state: Current lifecycle state. Defaults to PieceState.IDLE.
    """

    def __init__(self, token: str) -> None:
        self.token = token
        self.state = PieceState.IDLE
