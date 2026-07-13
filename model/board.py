"""
Board — logical grid storing token strings indexed by Position.
"""
from typing import List
from model.position import Position

_EMPTY = "."


class Board:
    """Logical chess board of fixed dimensions; cells store token strings."""

    def __init__(self, rows: int, cols: int) -> None:
        self._rows = rows
        self._cols = cols
        self._grid: List[List[str]] = [[_EMPTY] * cols for _ in range(rows)]

    @property
    def rows(self) -> int:
        return self._rows

    @property
    def cols(self) -> int:
        return self._cols

    def is_inside(self, pos: Position) -> bool:
        """Return True if pos falls within the board boundaries."""
        return 0 <= pos.row < self._rows and 0 <= pos.col < self._cols

    def get(self, pos: Position) -> str:
        """Return the token at pos. Raises ValueError if out of bounds."""
        self._require_inside(pos)
        return self._grid[pos.row][pos.col]

    def set(self, pos: Position, token: str) -> None:
        """Place token at pos. Raises ValueError if out of bounds."""
        self._require_inside(pos)
        self._grid[pos.row][pos.col] = token

    def _require_inside(self, pos: Position) -> None:
        if not self.is_inside(pos):
            raise ValueError(
                f"Position {pos} is outside the board ({self._rows}×{self._cols})."
            )
