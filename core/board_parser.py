from typing import List, Optional, Set
from core.exceptions import UnknownTokenError, RowWidthMismatchError
from core.constants import EMPTY_CELL

# Default allowed tokens — kept here so callers that don't pass a registry
# still get sensible validation. Extend by passing allowed_tokens explicitly.
_DEFAULT_TOKENS: Set[str] = {
    'wK', 'bK', 'wR', 'bR', 'wB', 'bB', 'wQ', 'bQ', 'wN', 'bN', 'wP', 'bP', EMPTY_CELL
}


class BoardParser:
    @classmethod
    def validate_and_parse(
        cls,
        board_lines: List[str],
        allowed_tokens: Optional[Set[str]] = None,
    ) -> List[List[str]]:
        valid = _DEFAULT_TOKENS if allowed_tokens is None else allowed_tokens
        parsed_board = []
        expected_width = None

        for line in board_lines:
            tokens = line.split()
            if not tokens:
                continue

            if expected_width is None:
                expected_width = len(tokens)
            elif len(tokens) != expected_width:
                raise RowWidthMismatchError()

            if any(t not in valid for t in tokens):
                raise UnknownTokenError()

            parsed_board.append(tokens)

        return parsed_board

    @classmethod
    def to_string(cls, board: List[List[str]]) -> str:
        return "\n".join(" ".join(row) for row in board)