from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
from core.interfaces.i_movement_validator import IMovementValidator
from core.game_clock import GameClock


@dataclass
class _PendingMove:
    piece:        str
    from_pos:     Tuple[int, int]
    to_pos:       Tuple[int, int]
    arrival_time: int


class GameService:
    def __init__(
        self,
        board: List[List[str]],
        validator: IMovementValidator,
        clock: GameClock,
    ) -> None:
        self._board = board
        self._rows = len(board)
        self._cols = len(board[0]) if self._rows > 0 else 0
        self._validator = validator
        self._clock = clock
        self._selected_pos: Optional[Tuple[int, int]] = None
        self._pending_moves: List[_PendingMove] = []

    # ------------------------------------------------------------------ #
    # Public interface                                                     #
    # ------------------------------------------------------------------ #

    def handle_click(self, x: int, y: int) -> None:
        col = x // 100
        row = y // 100

        if not (0 <= row < self._rows and 0 <= col < self._cols):
            return

        # Settle any arrivals before evaluating the click
        self._flush_pending()

        token = self._board[row][col]

        if self._selected_pos is None:
            # Only select a piece that exists on the matrix and is not in-flight
            if token != '.' and not self._is_in_flight(row, col):
                self._selected_pos = (row, col)
            return

        curr_row, curr_col = self._selected_pos
        selected_token = self._board[curr_row][curr_col]

        # Re-select a friendly piece that is not in-flight
        if token != '.' and token[0] == selected_token[0]:
            if not self._is_in_flight(row, col):
                self._selected_pos = (row, col)
            return

        # Attempt move — board matrix is NOT mutated here
        if self._validator.is_valid_move(
            self._board, selected_token, (curr_row, curr_col), (row, col)
        ):
            dr = abs(row - curr_row)
            dc = abs(col - curr_col)
            arrival = self._clock.now() + max(dr, dc) * 1000
            self._pending_moves.append(
                _PendingMove(selected_token, (curr_row, curr_col), (row, col), arrival)
            )
            # Piece remains visible at source on the matrix until arrival_time

        self._selected_pos = None

    def handle_wait(self, ms: int) -> None:
        self._clock.advance(ms)
        self._flush_pending()

    def get_board_lines(self) -> List[str]:
        self._flush_pending()
        return [' '.join(row) for row in self._board]

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _flush_pending(self) -> None:
        """Atomically settle every move whose arrival_time <= clock.now()."""
        arrived = [m for m in self._pending_moves if self._clock.now() >= m.arrival_time]
        for move in arrived:
            r1, c1 = move.from_pos
            r2, c2 = move.to_pos
            self._board[r2][c2] = move.piece  # land at destination
            self._board[r1][c1] = '.'          # clear source
            self._pending_moves.remove(move)

    def _is_in_flight(self, row: int, col: int) -> bool:
        """True if a piece at (row, col) has been dispatched but not yet arrived."""
        return any(m.from_pos == (row, col) for m in self._pending_moves)
