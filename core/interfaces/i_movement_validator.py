from abc import ABC, abstractmethod
from typing import List, Tuple


class IMovementValidator(ABC):

    @abstractmethod
    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        """Full move legality check: shape + path + capture rules."""
