"""
BoardParser — parses a list of text lines into a Board instance.

Accepted token set mirrors the existing project convention:
  color-prefix (w/b) + piece-type (K R B Q N P) or '.' for empty.

Raises ValueError for unknown tokens, inconsistent row widths, or empty input.
"""
from typing import List, Optional
from model.board import Board
from model.position import Position

_VALID_TOKENS = frozenset({
    "wK", "bK", "wR", "bR", "wB", "bB",
    "wQ", "bQ", "wN", "bN", "wP", "bP", ".",
})


class BoardParser:
    """Converts raw text lines into a Board value object."""

    @staticmethod
    def parse(lines: List[str]) -> Board:
        """
        Parse space-separated token lines into a Board.

        Args:
            lines: Each non-blank line is one board row; tokens are
                   separated by whitespace.

        Returns:
            A fully populated Board instance.

        Raises:
            ValueError: on empty input, unknown token, or row-width mismatch.
        """
        rows: List[List[str]] = []
        expected_width: Optional[int] = None

        for line in lines:
            tokens = line.split()
            if not tokens:
                continue

            if expected_width is None:
                expected_width = len(tokens)
            elif len(tokens) != expected_width:
                raise ValueError(
                    f"Row width mismatch: expected {expected_width}, got {len(tokens)}."
                )

            for token in tokens:
                if token not in _VALID_TOKENS:
                    raise ValueError(f"Unknown token: '{token}'.")

            rows.append(tokens)

        if not rows:
            raise ValueError("Board input is empty — no valid rows found.")

        board = Board(rows=len(rows), cols=len(rows[0]))
        for r, row in enumerate(rows):
            for c, token in enumerate(row):
                board.set(Position(r, c), token)

        return board
