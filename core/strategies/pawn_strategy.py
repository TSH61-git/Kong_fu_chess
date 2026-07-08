from typing import List, Tuple
from core.interfaces.i_movement_strategy import IMovementStrategy
from core.constants import (
    WHITE_COLOR, EMPTY_CELL,
    WHITE_PAWN_INIT_ROW_OFFSET, BLACK_PAWN_INIT_ROW,
    WHITE_PAWN, BLACK_PAWN, WHITE_QUEEN, BLACK_QUEEN,
)


class PawnStrategy(IMovementStrategy):
    def __init__(self, total_rows: int = 8) -> None:
        self._total_rows = total_rows

    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        r1, c1 = from_pos
        r2, c2 = to_pos
        color = piece[0]
        dc = abs(c2 - c1)
        target_token = board[r2][c2]
        direction = -1 if color == WHITE_COLOR else 1
        row_diff = r2 - r1

        if row_diff == direction:
            if dc == 0:
                return target_token == EMPTY_CELL
            if dc == 1:
                return target_token != EMPTY_CELL
            return False

        if row_diff == 2 * direction and dc == 0:
            init_row = (
                self._total_rows - WHITE_PAWN_INIT_ROW_OFFSET
                if color == WHITE_COLOR
                else BLACK_PAWN_INIT_ROW
            )
            mid_r = (r1 + r2) // 2
            return (
                r1 == init_row
                and target_token == EMPTY_CELL
                and board[mid_r][c1] == EMPTY_CELL
            )

        return False

    def on_land(
        self,
        board: List[List[str]],
        piece: str,
        to_pos: Tuple[int, int],
    ) -> str:
        row = to_pos[0]
        if piece == WHITE_PAWN and row == 0:
            return WHITE_QUEEN
        if piece == BLACK_PAWN and row == self._total_rows - 1:
            return BLACK_QUEEN
        return piece

    # Backward-compatible alias kept for existing tests
    def is_valid_pawn_move(
        self, color: str, r1: int, r2: int, dc: int, target_token: str
    ) -> bool:
        direction = -1 if color == WHITE_COLOR else 1
        row_diff = r2 - r1
        if row_diff == direction:
            if dc == 0:
                return target_token == EMPTY_CELL
            if dc == 1:
                return target_token != EMPTY_CELL
            return False
        return False
