# Application service layer — GameEngine orchestrator.
from __future__ import annotations

from typing import Optional, Protocol

from chess_engine.engine.helpers.move_history import MoveHistory, MoveRecord
from chess_engine.engine.helpers.score_manager import CapturedEntry, ScoreManager
from chess_engine.engine.helpers.snapshot_helpers import build_snapshot
from chess_engine.engine.helpers.snapshot_models import GameSnapshot, MoveResult
from chess_engine.model.board import Board
from chess_engine.model.piece import Color
from chess_engine.model.position import Position
from chess_engine.rules.engine import RuleEngine

_OK = "ok"
_GAME_OVER = "game_over"
_COOLDOWN_ACTIVE = "cooldown_active"
_MOTION_IN_PROGRESS = "motion_in_progress"
_DESTINATION_CLAIMED = "destination_claimed"


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
    def is_destination_claimed(self, destination: Position, color) -> bool: ...
    def take_captures(self) -> list: ...


class GameEngine:
    def __init__(self, board: Board, rule_engine: RuleEngine, arbiter: IRealTimeArbiter) -> None:
        self._board = board
        self._rule_engine = rule_engine
        self._arbiter = arbiter
        self._game_over: bool = False
        self._history = MoveHistory()
        self._score = ScoreManager()

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
        moving_piece = self._board.get(source)
        if moving_piece is not None and self._arbiter.is_destination_claimed(
            destination, moving_piece.color
        ):
            return MoveResult(is_accepted=False, reason=_DESTINATION_CLAIMED)
        self._arbiter.start_motion(
            piece=self._board.get(source), source=source, destination=destination,
        )
        if moving_piece is not None:
            target = self._board.get(destination)
            is_capture = target is not None and target.color != moving_piece.color
            self._history.record(moving_piece, source, destination, is_capture=is_capture)
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
        jumping_piece = self._board.get(position)
        if jumping_piece is None:
            return MoveResult(is_accepted=False, reason="empty_source")
        self._arbiter.start_motion(
            piece=jumping_piece, source=position, destination=position, duration_ms=1000,
        )
        self._history.record(jumping_piece, position, position, is_capture=False)
        return MoveResult(is_accepted=True, reason=_OK)

    def advance_time(self, ms: int) -> None:
        self._arbiter.advance_time(ms)
        for piece, captured_by in self._arbiter.take_captures():
            self._score.record_capture(piece, captured_by)

    def wait(self, ms: int) -> None:
        self.advance_time(ms)

    def get_snapshot(self, selected_cell: Optional[Position] = None) -> GameSnapshot:
        return build_snapshot(self._board, selected_cell, self._game_over)

    def snapshot(self, selected_cell: Optional[Position] = None) -> GameSnapshot:
        return self.get_snapshot(selected_cell)

    def notify_king_captured(self) -> None:
        self._game_over = True

    def history_entries(self) -> list[MoveRecord]:
        return self._history.entries()

    def get_scores(self) -> dict[Color, int]:
        return self._score.get_scores()

    def get_captured(self, color: Color) -> list[CapturedEntry]:
        return self._score.get_captured(color)
