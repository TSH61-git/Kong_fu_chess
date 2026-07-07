from abc import ABC, abstractmethod


class IMovementStrategy(ABC):
    """
    Contract for a single piece's shape-validation logic.
    The validator calls is_shape_valid(); needs_path_check tells it
    whether to run the line-of-sight blocker loop afterward.
    """

    @abstractmethod
    def is_shape_valid(self, dr: int, dc: int) -> bool:
        """Return True if (dr, dc) is a legal geometric move for this piece."""

    @property
    def needs_path_check(self) -> bool:
        """Override to True for sliding pieces (R, B, Q)."""
        return False
