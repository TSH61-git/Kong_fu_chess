# RuleEngine — slim orchestrator that iterates over SRP guard modules.
from __future__ import annotations

from dataclasses import dataclass

from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.rules.guards import (
    boundary_guard,
    empty_source_guard,
    friendly_fire_guard,
    legal_move_guard,
)

_GUARDS = [
    boundary_guard,
    empty_source_guard,
    friendly_fire_guard,
    legal_move_guard,
]


@dataclass(frozen=True)
class MoveValidation:
    # Immutable result of a single move-validation check.
    is_valid: bool
    reason: str


class RuleEngine:
    # Stateless move-validation service.

    def validate_move(
        self,
        board: Board,
        source: Position,
        destination: Position,
    ) -> MoveValidation:
        for guard in _GUARDS:
            reason = guard.check(board, source, destination)
            if reason is not None:
                return MoveValidation(is_valid=False, reason=reason)
        return MoveValidation(is_valid=True, reason="ok")
