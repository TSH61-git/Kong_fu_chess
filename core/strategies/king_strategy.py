from typing import List, Tuple
from core.interfaces.i_movement_strategy import IMovementStrategy


class KingStrategy(IMovementStrategy):
    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        r1, c1 = from_pos
        r2, c2 = to_pos
        return max(abs(r2 - r1), abs(c2 - c1)) == 1
