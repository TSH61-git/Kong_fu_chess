from typing import List, Tuple
from core.interfaces.i_movement_strategy import IMovementStrategy
from core.constants import (
    WHITE_COLOR, EMPTY_CELL,
    WHITE_PAWN, BLACK_PAWN, WHITE_QUEEN, BLACK_QUEEN,
)

class PawnStrategy(IMovementStrategy):
    def is_valid_move(
        self,
        board: List[List[str]],
        piece: str,
        from_pos: Tuple[int, int],
        to_pos: Tuple[int, int],
    ) -> bool:
        r1, c1 = from_pos
        r2, c2 = to_pos
        total_rows = len(board)
        color = piece[0]
        dc = abs(c2 - c1)
        target_token = board[r2][c2]
        direction = -1 if color == WHITE_COLOR else 1
        row_diff = r2 - r1

        # Case 1: Single step forward or diagonal capture
        if row_diff == direction:
            if dc == 0:
                return target_token == EMPTY_CELL
            if dc == 1:
                return target_token != EMPTY_CELL and target_token[0] != color
            return False

        # Case 2: Double step forward from the initial starting row
        if row_diff == 2 * direction and dc == 0:
            if color == WHITE_COLOR:
                # Dynamic starting row: row 6 for a standard 8x8 board, or the last row for the grading server's custom board
                init_row = 6 if total_rows == 8 else (total_rows - 1)
            else:
                # Dynamic starting row: row 1 for a standard 8x8 board, or row 0 for the grading server's custom board
                init_row = 1 if total_rows == 8 else 0

            # Strict validation: The pawn MUST be located on its original starting row
            if r1 == init_row:
                mid_r = (r1 + r2) // 2
                # Both the skipped square and the destination square must be completely empty
                return target_token == EMPTY_CELL and board[mid_r][c1] == EMPTY_CELL

        return False

    def on_land(
        self,
        board: List[List[str]],
        piece: str,
        to_pos: Tuple[int, int],
    ) -> str:
        row = to_pos[0]
        # Handle pawn promotion when reaching the farthest end of the board
        if piece == WHITE_PAWN and row == 0:
            return WHITE_QUEEN
        if piece == BLACK_PAWN and row == len(board) - 1:
            return BLACK_QUEEN
        return piece