"""
Piece promotion rules for the rules layer.

Public API
----------
get_promoted_token(piece_type, current_row, max_rows, color) -> str
    Evaluates whether a piece should be promoted after reaching the
    promotion row, and returns the promoted piece type or the original
    type if no promotion occurs.

Design notes
------------
- Completely stateless: no instance variables, no side effects.
- Dispatches to one private function per piece type via a plain dict registry.
- Pawn is the only piece that promotes: to 'Q' (Queen) when reaching the
  promotion row (row 0 for White, row max_rows-1 for Black).
- All other pieces return their original type (no transformation).
- Promotion is the sole responsibility of this module; it does not validate
  legality or interact with board state beyond the row number.
"""
from __future__ import annotations

from typing import Callable, Dict

# Type alias for a promotion-rule function.
_PromotionFn = Callable[[int, int, str], str]


# ------------------------------------------------------------------ #
# Per-piece promotion functions                                       #
# ------------------------------------------------------------------ #

def _promote_pawn(current_row: int, max_rows: int, color: str) -> str:
    """
    Promote a pawn to a Queen if it reaches the promotion row.

    Promotion occurs when:
      - White pawn ('w'): reaches row 0.
      - Black pawn ('b'): reaches row max_rows - 1.

    If the pawn reaches the promotion row, returns 'Q' (Queen).
    Otherwise, returns the original pawn character 'P'.

    Args:
        current_row: The row the pawn has reached.
        max_rows:    The total number of rows on the board.
        color:       The color prefix of the pawn ('w' or 'b').

    Returns:
        'Q' if promotion occurs, 'P' otherwise.
    """
    promotion_row = 0 if color == "w" else (max_rows - 1)
    return "Q" if current_row == promotion_row else "P"


def _promote_rook(current_row: int, max_rows: int, color: str) -> str:
    """
    Rook does not promote; return the original piece type.
    """
    return "R"


def _promote_bishop(current_row: int, max_rows: int, color: str) -> str:
    """
    Bishop does not promote; return the original piece type.
    """
    return "B"


def _promote_knight(current_row: int, max_rows: int, color: str) -> str:
    """
    Knight does not promote; return the original piece type.
    """
    return "N"


def _promote_queen(current_row: int, max_rows: int, color: str) -> str:
    """
    Queen does not promote; return the original piece type.
    """
    return "Q"


def _promote_king(current_row: int, max_rows: int, color: str) -> str:
    """
    King does not promote; return the original piece type.
    """
    return "K"


# ------------------------------------------------------------------ #
# Dispatch registry                                                   #
# ------------------------------------------------------------------ #

_PROMOTION_REGISTRY: Dict[str, _PromotionFn] = {
    "P": _promote_pawn,
    "R": _promote_rook,
    "B": _promote_bishop,
    "N": _promote_knight,
    "Q": _promote_queen,
    "K": _promote_king,
}


# ------------------------------------------------------------------ #
# Public API                                                          #
# ------------------------------------------------------------------ #

def get_promoted_token(piece_type: str, current_row: int,
                       max_rows: int, color: str) -> str:
    """
    Determine the promoted piece type for a given piece at a given row.

    This function is the single public entry point for the promotion layer.
    It is completely stateless and evaluates promotion based solely on
    piece type, row position, and board dimensions.

    Args:
        piece_type:  One-character token representing the piece ('P', 'R', etc.).
        current_row: The row the piece has moved to.
        max_rows:    The total number of rows on the board.
        color:       The color prefix of the piece ('w' or 'b').

    Returns:
        The promoted piece type (e.g. 'Q' for a pawn reaching row 0),
        or the original piece type if no promotion occurs.
        Returns the original type for unknown piece types.
    """
    promotion_fn = _PROMOTION_REGISTRY.get(piece_type)
    if promotion_fn is None:
        return piece_type
    return promotion_fn(current_row, max_rows, color)
