"""Stateless piece promotion rules for the rules layer."""
from __future__ import annotations

from typing import Callable, Dict

# Type alias for a promotion-rule function.
_PromotionFn = Callable[[int, int, str], str]


# ------------------------------------------------------------------ #
# Per-piece promotion functions                                       #
# ------------------------------------------------------------------ #

def _promote_pawn(current_row: int, max_rows: int, color: str) -> str:
    promotion_row = 0 if color == "w" else (max_rows - 1)
    return "Q" if current_row == promotion_row else "P"


def _promote_rook(current_row: int, max_rows: int, color: str) -> str:
    return "R"


def _promote_bishop(current_row: int, max_rows: int, color: str) -> str:
    return "B"


def _promote_knight(current_row: int, max_rows: int, color: str) -> str:
    return "N"


def _promote_queen(current_row: int, max_rows: int, color: str) -> str:
    return "Q"


def _promote_king(current_row: int, max_rows: int, color: str) -> str:
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
    promotion_fn = _PROMOTION_REGISTRY.get(piece_type)
    if promotion_fn is None:
        return piece_type
    return promotion_fn(current_row, max_rows, color)
