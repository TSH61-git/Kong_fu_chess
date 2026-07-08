from abc import ABC, abstractmethod
from typing import List, Tuple


class IMovementStrategy(ABC):
    """
    Unified contract for a piece's full move-legality logic.
    Each strategy owns its complete validation: shape, path, and occupancy rules.
    """

    @abstractmethod
    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        """Return True if moving piece from from_pos to to_pos is geometrically legal."""

    def on_land(
        self,
        board: List[List[str]],
        piece: str,
        to_pos: Tuple[int, int],
    ) -> str:
        """Called when a piece arrives. Returns the token to place on the board.
        Override to implement landing transformations such as pawn promotion.
        """
        return piece
