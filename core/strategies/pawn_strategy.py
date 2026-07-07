from core.interfaces.i_movement_strategy import IMovementStrategy


class PawnStrategy(IMovementStrategy):
    """
    Pawn shape cannot be reduced to (dr, dc) alone — it depends on color,
    signed row direction, and whether the target cell is occupied.
    is_shape_valid is intentionally unused for pawns; the validator calls
    is_valid_pawn_move() directly after detecting piece_type == 'P'.
    """

    def is_shape_valid(self, dr: int, dc: int) -> bool:
        # Not used by the validator for pawns; kept to satisfy the ABC.
        return False

    def is_valid_pawn_move(
        self, color: str, r1: int, r2: int, dc: int, target_token: str
    ) -> bool:
        allowed_row_diff = -1 if color == 'w' else 1
        if (r2 - r1) != allowed_row_diff:
            return False
        if dc == 0:
            return target_token == '.'
        if dc == 1:
            return target_token != '.'
        return False
