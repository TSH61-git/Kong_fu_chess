"""Move validation service for the rules layer."""
from __future__ import annotations

from dataclasses import dataclass

from model.board import Board
from model.position import Position
from rules.movement_rules import legal_destinations

_EMPTY = "."

# Stable machine-readable reason constants.
_OK                   = "ok"
_OUTSIDE_BOARD        = "outside_board"
_EMPTY_SOURCE         = "empty_source"
_FRIENDLY_DESTINATION = "friendly_destination"
_ILLEGAL_PIECE_MOVE   = "illegal_piece_move"


@dataclass(frozen=True)
class MoveValidation:
    """Immutable result of a single move-validation check."""
    is_valid: bool
    reason: str


class RuleEngine:
    """Stateless move-validation service."""

    def validate_move(
        self,
        board: Board,
        source: Position,
        destination: Position,
    ) -> MoveValidation:
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
