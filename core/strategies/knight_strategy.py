from typing import List, Tuple
from core.interfaces.i_movement_strategy import IMovementStrategy


class KnightStrategy(IMovementStrategy):
    def is_shape_valid(self, dr: int, dc: int) -> bool:
        return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)

    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        r1, c1 = from_pos
        r2, c2 = to_pos
        return self.is_shape_valid(abs(r2 - r1), abs(c2 - c1))
