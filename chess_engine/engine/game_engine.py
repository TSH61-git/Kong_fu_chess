# Application service layer — GameEngine orchestrator.
from __future__ import annotations

from typing import Optional, Protocol

from chess_engine.engine.helpers.snapshot_helpers import build_snapshot
from chess_engine.engine.helpers.snapshot_models import GameSnapshot, MoveResult
from chess_engine.model.board import Board
from chess_engine.model.position import Position
from chess_engine.rules.engine import RuleEngine

_OK = "ok"
_GAME_OVER = "game_over"
_COOLDOWN_ACTIVE = "cooldown_active"
_MOTION_IN_PROGRESS = "motion_in_progress"


def _is_piece_in_flight(arbiter, source: Position) -> bool:
    motions = arbiter.get_active_motions()
    if not motions:
        return False
    return any(getattr(m, "source", None) == source for m in motions)


class IRealTimeArbiter(Protocol):
    def has_active_motion(self) -> bool: ...
    def get_active_motions(self): ...
    def start_motion(self, piece: str, source: Position, destination: Position) -> None: ...
    def advance_time(self, ms: int) -> None: ...
    def is_in_cooldown(self, pos: Position) -> bool: ...


class GameEngine:
    def __init__(self, board: Board, rule_engine: RuleEngine, arbiter: IRealTimeArbiter) -> None:
        self._board = board
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self._game_over: bool = False

    def request_move(self, source: Position, destination: Position) -> MoveResult:
        if self._game_over:
            return MoveResult(is_accepted=False, reason=_GAME_OVER)
        if self._arbiter.is_in_cooldown(source):
            return MoveResult(is_accepted=False, reason=_COOLDOWN_ACTIVE)
        if _is_piece_in_flight(self._arbiter, source):
            return MoveResult(is_accepted=False, reason=_MOTION_IN_PROGRESS)
        validation = self._rule_engine.validate_move(self._board, source, destination)
        if not validation.is_valid:
            return MoveResult(is_accepted=False, reason=validation.reason)
        self._arbiter.start_motion(
            piece=self._board.get(source), source=source, destination=destination,
        )
        return MoveResult(is_accepted=True, reason=_OK)

    def validate_move(self, board: Board, source: Position, destination: Position):
        return self._rule_engine.validate_move(board, source, destination)

    def request_jump(self, position: Position) -> MoveResult:
        if self._game_over:
            return MoveResult(is_accepted=False, reason=_GAME_OVER)
        if self._arbiter.is_in_cooldown(position):
            return MoveResult(is_accepted=False, reason=_COOLDOWN_ACTIVE)
        if _is_piece_in_flight(self._arbiter, position):
            return MoveResult(is_accepted=False, reason=_MOTION_IN_PROGRESS)
        if self._board.get(position) is None:
            return MoveResult(is_accepted=False, reason="empty_source")
        self._arbiter.start_motion(
            piece=self._board.get(position), source=position, destination=position, duration_ms=1000,
        )
        return MoveResult(is_accepted=True, reason=_OK)

    def advance_time(self, ms: int) -> None:
        self._arbiter.advance_time(ms)

    def wait(self, ms: int) -> None:
        self.advance_time(ms)

    def get_snapshot(self, selected_cell: Optional[Position] = None) -> GameSnapshot:
        return build_snapshot(self._board, selected_cell, self._game_over)

    def snapshot(self, selected_cell: Optional[Position] = None) -> GameSnapshot:
        return self.get_snapshot(selected_cell)

    def notify_king_captured(self) -> None:
        self._game_over = True
