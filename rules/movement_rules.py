"""Stateless piece movement geometry for the rules layer."""
from __future__ import annotations

from typing import Callable, Dict, Set

from model.board import Board
from model.position import Position

_EMPTY = "."

# Type alias for a piece-rule function.
_RuleFn = Callable[[Board, Position, str], Set[Position]]


# ------------------------------------------------------------------ #
# Shared sliding helper                                               #
# ------------------------------------------------------------------ #

def _slide(board: Board, from_pos: Position, color: str,
           directions: list[tuple[int, int]]) -> Set[Position]:
    result: Set[Position] = set()
    for dr, dc in directions:
        r, c = from_pos.row + dr, from_pos.col + dc
        while True:
            pos = Position(r, c)
            if not board.is_inside(pos):
                break
            token = board.get(pos)
            if token == _EMPTY:
                result.add(pos)
            elif token[0] == color:
                break                  # friendly — stop, exclude
            else:
                result.add(pos)        # enemy — include, then stop
                break
            r += dr
            c += dc
    return result


# ------------------------------------------------------------------ #
# Per-piece rule functions                                            #
# ------------------------------------------------------------------ #

def _rook(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    return _slide(board, from_pos, piece_token[0],
                  [(-1, 0), (1, 0), (0, -1), (0, 1)])


def _bishop(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    return _slide(board, from_pos, piece_token[0],
                  [(-1, -1), (-1, 1), (1, -1), (1, 1)])


def _queen(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    return _slide(board, from_pos, piece_token[0],
                  [(-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (-1, 1), (1, -1), (1, 1)])


def _knight(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    color = piece_token[0]
    offsets = [(-2, -1), (-2, 1), (-1, -2), (-1, 2),
               (1, -2),  (1, 2),  (2, -1),  (2, 1)]
    result: Set[Position] = set()
    for dr, dc in offsets:
        pos = Position(from_pos.row + dr, from_pos.col + dc)
        if not board.is_inside(pos):
            continue
        token = board.get(pos)
        if token != _EMPTY and token[0] == color:
            continue                   # friendly landing — excluded
        result.add(pos)
    return result


def _king(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    color = piece_token[0]
    result: Set[Position] = set()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            pos = Position(from_pos.row + dr, from_pos.col + dc)
            if not board.is_inside(pos):
                continue
            token = board.get(pos)
            if token != _EMPTY and token[0] == color:
                continue               # friendly — excluded
            result.add(pos)
    return result


def _pawn(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    color = piece_token[0]
    dr = -1 if color == "w" else 1
    result: Set[Position] = set()

    # Forward step — only to an empty cell
    fwd = Position(from_pos.row + dr, from_pos.col)
    if board.is_inside(fwd) and board.get(fwd) == _EMPTY:
        result.add(fwd)

        start_row = board.rows - 2 if color == "w" else 1
        if from_pos.row == start_row:
            double_step = Position(from_pos.row + (2 * dr), from_pos.col)
            if (
                board.is_inside(double_step)
                and board.get(double_step) == _EMPTY
                and board.get(Position(from_pos.row + dr, from_pos.col)) == _EMPTY
            ):
                result.add(double_step)

    # Diagonal captures — only onto an enemy piece
    for dc in (-1, 1):
        diag = Position(from_pos.row + dr, from_pos.col + dc)
        if not board.is_inside(diag):
            continue
        token = board.get(diag)
        if token != _EMPTY and token[0] != color:
            result.add(diag)

    return result


# ------------------------------------------------------------------ #
# Dispatch registry                                                   #
# ------------------------------------------------------------------ #

_REGISTRY: Dict[str, _RuleFn] = {
    "R": _rook,
    "B": _bishop,
    "Q": _queen,
    "N": _knight,
    "K": _king,
    "P": _pawn,
}


# ------------------------------------------------------------------ #
# Public API                                                          #
# ------------------------------------------------------------------ #

def legal_destinations(board: Board, from_pos: Position,
                       piece_token: str) -> Set[Position]:
    piece_type = piece_token[1] if len(piece_token) == 2 else ""
    rule_fn = _REGISTRY.get(piece_type)
    if rule_fn is None:
        return set()
    return rule_fn(board, from_pos, piece_token)
