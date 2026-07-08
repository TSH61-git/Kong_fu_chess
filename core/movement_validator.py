from typing import List, Tuple, Dict
from core.interfaces.i_movement_validator import IMovementValidator
from core.interfaces.i_movement_strategy import IMovementStrategy
from core.constants import EMPTY_CELL


class MovementValidator(IMovementValidator):
    def __init__(self, registry: Dict[str, IMovementStrategy]) -> None:
        self._registry = registry

    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        r1, c1 = from_pos
        r2, c2 = to_pos

        if r1 == r2 and c1 == c2:
            return True

        target_token = board[r2][c2]

        # Friendly-fire guard
        if target_token != EMPTY_CELL and target_token[0] == piece[0]:
            return False

        strategy = self._registry.get(piece[1])
        if strategy is None:
            return False

        return strategy.is_valid_move(board, piece, from_pos, to_pos)
