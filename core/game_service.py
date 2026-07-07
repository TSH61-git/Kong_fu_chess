from typing import List, Tuple, Optional
from core.interfaces.i_movement_validator import IMovementValidator


class GameService:
    def __init__(self, board: List[List[str]], validator: IMovementValidator) -> None:
        self._board = board
        self._rows = len(board)
        self._cols = len(board[0]) if self._rows > 0 else 0
        self._validator = validator
        self._selected_pos: Optional[Tuple[int, int]] = None

    def handle_click(self, x: int, y: int) -> None:
        col = x // 100
        row = y // 100

        if not (0 <= row < self._rows and 0 <= col < self._cols):
            return

        token = self._board[row][col]

        if self._selected_pos is None:
            if token != '.':
                self._selected_pos = (row, col)
            return

        curr_row, curr_col = self._selected_pos
        selected_token = self._board[curr_row][curr_col]

        if token != '.' and token[0] == selected_token[0]:
            self._selected_pos = (row, col)
        else:
            if self._validator.is_valid_move(
                self._board, selected_token, (curr_row, curr_col), (row, col)
            ):
                self._board[row][col] = selected_token
                self._board[curr_row][curr_col] = '.'
            self._selected_pos = None

    def handle_wait(self, ms: int) -> None:
        pass

    def get_board_lines(self) -> List[str]:
        return [' '.join(row) for row in self._board]
