"""
BoardPrinter — serialises a Board back to the canonical text format.

Output is a list of strings, one per row, with tokens separated by
single spaces. This is the exact format consumed by the 'print board'
DSL command in the integration test harness.
"""
from typing import List
from model.board import Board
from model.position import Position


class BoardPrinter:
    """Converts a Board instance into human-readable text lines."""

    @staticmethod
    def to_lines(board: Board) -> List[str]:
        """
        Serialise every row of board to a space-separated token string.

        Args:
            board: The Board to serialise.

        Returns:
            A list of strings, one per row, in row-major order.
        """
        return [
            " ".join(board.get(Position(r, c)) for c in range(board.cols))
            for r in range(board.rows)
        ]
