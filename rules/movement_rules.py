"""
Piece movement geometry for the rules layer.

Public API
----------
legal_destinations(board, from_pos, piece_token) -> set[Position]
    Returns the set of all positions a piece may legally move to from
    from_pos, given the current board state.  The result never contains
    the source position itself.

Design notes
------------
- Completely stateless: no instance variables, no side effects.
- Read-only relative to Board: only Board.get and Board.is_inside are called.
- Dispatches to one private function per piece type via a plain dict registry.
- The shared _slide helper encodes the path-obstruction rule used by Rook,
  Bishop, and Queen: walk one direction, stop at a friendly (exclude) or
  stop at an enemy (include, then stop).
- Pawn is simplified: single forward step + diagonal capture only.
  No double-step opening, no en-passant, no promotion.
- Travel duration note: grid-step distance (Manhattan/Chebyshev steps along
  the piece's actual path) maps directly to timing in the real-time layer.
  A Bishop moving 3 diagonal squares takes 3 steps, not Euclidean distance.
"""
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
    """
    Walk each direction until the board edge or a blocking piece.

    For each direction (dr, dc):
      - Empty cells are added and the walk continues.
      - A friendly piece stops the walk; that cell is excluded.
      - An enemy piece stops the walk; that cell is included (capture).

    Args:
        board:      The current board state (read-only).
        from_pos:   Starting position of the sliding piece.
        color:      Color prefix of the moving piece ('w' or 'b').
        directions: List of (dr, dc) unit-step tuples to walk.

    Returns:
        Set of reachable positions across all given directions.
    """
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
    """
    Rook: slides horizontally and vertically any number of squares.
    Blocked by the first piece encountered in each direction.
    """
    return _slide(board, from_pos, piece_token[0],
                  [(-1, 0), (1, 0), (0, -1), (0, 1)])


def _bishop(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    """
    Bishop: slides diagonally any number of squares.
    Blocked by the first piece encountered in each diagonal direction.
    """
    return _slide(board, from_pos, piece_token[0],
                  [(-1, -1), (-1, 1), (1, -1), (1, 1)])


def _queen(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    """
    Queen: combines Rook and Bishop movement (all 8 directions, sliding).
    """
    return _slide(board, from_pos, piece_token[0],
                  [(-1, 0), (1, 0), (0, -1), (0, 1),
                   (-1, -1), (-1, 1), (1, -1), (1, 1)])


def _knight(board: Board, from_pos: Position, piece_token: str) -> Set[Position]:
    """
    Knight: L-shaped jumps (±1, ±2) or (±2, ±1).
    Ignores all intermediate pieces; only the landing square matters.
    Friendly landing squares are excluded.
    """
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
    """
    King: exactly one step in any of the 8 directions.
    Friendly adjacent squares are excluded.
    """
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
    """
    Pawn (simplified): single forward step, diagonal capture, and opening double-step.

    Direction:
      - White ('w'): moves toward row 0 (dr = -1).
      - Black ('b'): moves toward last row (dr = +1).

    Rules:
      - Forward step: one cell directly ahead, only if that cell is empty.
      - Double-step opening: allowed only when the pawn is on its official
        starting row and both the intermediate and destination cells are empty.
      - Diagonal capture: one cell diagonally ahead (dc = ±1), only if
        that cell contains an enemy piece.

    Excluded: en-passant, promotion.
    """
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
    """
    Return all positions the piece at from_pos may legally move to.

    This function is the single public entry point for the rules layer.
    It is completely stateless and read-only relative to the board.

    Args:
        board:        Current board state.  Never mutated.
        from_pos:     Grid position of the piece to move.
        piece_token:  Two-character token string, e.g. 'wR', 'bK'.
                      The second character identifies the piece type.

    Returns:
        A set of Position objects the piece can legally reach.
        Returns an empty set for unknown piece types.
    """
    piece_type = piece_token[1] if len(piece_token) == 2 else ""
    rule_fn = _REGISTRY.get(piece_type)
    if rule_fn is None:
        return set()
    return rule_fn(board, from_pos, piece_token)
