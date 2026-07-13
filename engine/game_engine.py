"""Application service layer — GameEngine orchestrator."""
from __future__ import annotations

from typing import Optional, Protocol

from engine.helpers.snapshot_helpers import build_snapshot
from engine.helpers.snapshot_models import GameSnapshot, MoveResult
from model.board import Board
from model.position import Position
from rules.rule_engine import RuleEngine

_OK = "ok"
_GAME_OVER = "game_over"
_COOLDOWN_ACTIVE = "cooldown_active"


class IRealTimeArbiter(Protocol):
    """Structural interface for the real-time coordination layer."""

    def has_active_motion(self) -> bool: ...
    def get_active_motions(self): ...
    def start_motion(self, piece: str, source: Position, destination: Position) -> None: ...
    def advance_time(self, ms: int) -> None: ...
    def is_in_cooldown(self, pos: Position) -> bool: ...


class GameEngine:
    """High-level application service orchestrating rules, motion, and state progression."""

    def __init__(
        self,
        board: Board,
        rule_engine: RuleEngine,
        arbiter: IRealTimeArbiter,
    ) -> None:
        self._board = board
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self._game_over: bool = False

    def request_move(
        self,
        source: Position,
        destination: Position,
    ) -> MoveResult:
        if self._game_over:
            return MoveResult(is_accepted=False, reason=_GAME_OVER)

        if self._arbiter.is_in_cooldown(source):
            return MoveResult(is_accepted=False, reason=_COOLDOWN_ACTIVE)

        validation = self._rule_engine.validate_move(self._board, source, destination)
        if not validation.is_valid:
            return MoveResult(is_accepted=False, reason=validation.reason)

        self._arbiter.start_motion(
            piece=self._board.get(source),
            source=source,
            destination=destination,
        )
        return MoveResult(is_accepted=True, reason=_OK)

    def validate_move(self, board: Board, source: Position, destination: Position):
        return self._rule_engine.validate_move(board, source, destination)

    def request_jump(self, position: Position) -> MoveResult:
        if self._game_over:
            return MoveResult(is_accepted=False, reason=_GAME_OVER)

        if self._arbiter.is_in_cooldown(position):
            return MoveResult(is_accepted=False, reason=_COOLDOWN_ACTIVE)

        if self._board.get(position) == ".":
            return MoveResult(is_accepted=False, reason="empty_source")

        self._arbiter.start_motion(
            piece=self._board.get(position),
            source=position,
            destination=position,
            duration_ms=1000,
        )
        return MoveResult(is_accepted=True, reason=_OK)

    def advance_time(self, ms: int) -> None:
        self._arbiter.advance_time(ms)

    def wait(self, ms: int) -> None:
        self.advance_time(ms)

    def get_snapshot(
        self,
        selected_cell: Optional[Position] = None,
    ) -> GameSnapshot:
        return build_snapshot(self._board, selected_cell, self._game_over)

    def snapshot(
        self,
        selected_cell: Optional[Position] = None,
    ) -> GameSnapshot:
        return self.get_snapshot(selected_cell)

    def notify_king_captured(self) -> None:
        self._game_over = True
