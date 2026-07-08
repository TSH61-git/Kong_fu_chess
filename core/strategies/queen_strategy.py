from typing import List, Tuple
from core.interfaces.i_movement_strategy import IMovementStrategy
from core.constants import EMPTY_CELL


class QueenStrategy(IMovementStrategy):
    def is_shape_valid(self, dr: int, dc: int) -> bool:
        return dr == 0 or dc == 0 or dr == dc

    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        r1, c1 = from_pos
        r2, c2 = to_pos
        dr, dc = abs(r2 - r1), abs(c2 - c1)
        if not self.is_shape_valid(dr, dc):
            return False
        step_r = 0 if r1 == r2 else (1 if r2 > r1 else -1)
        step_c = 0 if c1 == c2 else (1 if c2 > c1 else -1)
        curr_r, curr_c = r1 + step_r, c1 + step_c
        while (curr_r, curr_c) != (r2, c2):
            if board[curr_r][curr_c] != EMPTY_CELL:
                return False
            curr_r += step_r
            curr_c += step_c
        return True
