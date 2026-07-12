"""
Move validation service for the rules layer.

Public API
----------
RuleEngine.validate_move(board, source, destination) -> MoveValidation
    Evaluates a proposed move and returns a MoveValidation describing
    whether the move is legal and, if not, the precise machine-readable
    reason it was rejected.

MoveValidation
--------------
A frozen (read-only) dataclass with two fields:
  is_valid : bool  — True only when reason is "ok".
  reason   : str   — Always populated.  One of:
               "ok"                  — move is fully legal.
               "outside_board"       — source or destination is off the grid.
               "empty_source"        — source cell contains no piece.
               "friendly_destination"— destination holds a same-color piece.
               "illegal_piece_move"  — destination not in legal_destinations.

Evaluation order (strict)
-------------------------
1. outside_board   — checked before any board access.
2. empty_source    — checked before color comparison.
3. friendly_destination — checked before piece-rule query.
4. illegal_piece_move   — queried last via legal_destinations.

Design notes
------------
- Completely read-only relative to Board: no set() calls are made.
- Stateless: RuleEngine holds no mutable state between calls.
- Depends only on model/ and rules/piece_rules; no game or timing logic.
"""
from __future__ import annotations

from dataclasses import dataclass

from model.board import Board
from model.position import Position
from rules.piece_rules import legal_destinations

_EMPTY = "."

# Stable machine-readable reason constants.
_OK                   = "ok"
_OUTSIDE_BOARD        = "outside_board"
_EMPTY_SOURCE         = "empty_source"
_FRIENDLY_DESTINATION = "friendly_destination"
_ILLEGAL_PIECE_MOVE   = "illegal_piece_move"


@dataclass(frozen=True)
class MoveValidation:
    """
    Immutable result of a single move-validation check.

    Attributes:
        is_valid: True if and only if reason is "ok".
        reason:   Machine-readable outcome string.  Always populated.
    """
    is_valid: bool
    reason: str


class RuleEngine:
    """
    Stateless move-validation service.

    Evaluates proposed moves against board state and piece geometry.
    Never modifies the board or any piece state.
    """

    def validate_move(
        self,
        board: Board,
        source: Position,
        destination: Position,
    ) -> MoveValidation:
        """
        Validate a proposed move from source to destination.

        Evaluation proceeds through four ordered guards; the first
        failing guard determines the returned reason.

        Args:
            board:       Current board state.  Read-only.
            source:      Position of the piece to move.
            destination: Intended target position.

        Returns:
            MoveValidation with is_valid=True and reason="ok" when the
            move is legal, or is_valid=False with the appropriate reason
            string otherwise.
        """
        # Guard 1 — boundary check (before any board.get call)
        if not board.is_inside(source) or not board.is_inside(destination):
            return MoveValidation(is_valid=False, reason=_OUTSIDE_BOARD)

        source_token = board.get(source)

        # Guard 2 — source must not be empty
        if source_token == _EMPTY:
            return MoveValidation(is_valid=False, reason=_EMPTY_SOURCE)

        destination_token = board.get(destination)

        # Guard 3 — destination must not hold a friendly piece
        if destination_token != _EMPTY and destination_token[0] == source_token[0]:
            return MoveValidation(is_valid=False, reason=_FRIENDLY_DESTINATION)

        # Guard 4 — destination must be in the piece's legal destinations
        if destination not in legal_destinations(board, source, source_token):
            return MoveValidation(is_valid=False, reason=_ILLEGAL_PIECE_MOVE)

        return MoveValidation(is_valid=True, reason=_OK)
