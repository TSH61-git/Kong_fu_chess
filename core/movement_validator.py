from typing import List, Tuple, Dict
from core.interfaces.i_movement_validator import IMovementValidator
from core.interfaces.i_movement_strategy import IMovementStrategy
from core.strategies.pawn_strategy import PawnStrategy


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
        if target_token != '.' and target_token[0] == piece[0]:
            return False

        piece_type = piece[1]
        dr = abs(r2 - r1)
        dc = abs(c2 - c1)

        strategy = self._registry.get(piece_type)
        if strategy is None:
            return False

        # Pawn has directional + occupancy rules that need more than (dr, dc)
        if piece_type == 'P':
            assert isinstance(strategy, PawnStrategy)
            return strategy.is_valid_pawn_move(piece[0], r1, r2, dc, target_token)

        if not strategy.is_shape_valid(dr, dc):
            return False

        # Line-of-sight blocker check for sliding pieces
        if strategy.needs_path_check:
            step_r = 1 if r2 > r1 else (-1 if r2 < r1 else 0)
            step_c = 1 if c2 > c1 else (-1 if c2 < c1 else 0)
            curr_r, curr_c = r1 + step_r, c1 + step_c
            while (curr_r, curr_c) != (r2, c2):
                if board[curr_r][curr_c] != '.':
                    return False
                curr_r += step_r
                curr_c += step_c

        return True
