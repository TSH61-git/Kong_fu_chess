"""BoardPrinter — serialises a Board to canonical text lines."""
from typing import List
from model.board import Board
from model.position import Position


class BoardPrinter:
    """Converts a Board instance into human-readable text lines."""

    @staticmethod
    def to_lines(board: Board) -> List[str]:
        return [
            " ".join(board.get(Position(r, c)) for c in range(board.cols))
            for r in range(board.rows)
        ]
