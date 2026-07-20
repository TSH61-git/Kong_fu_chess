# Bridges network-sourced game state into the exact object shapes GuiRunner
# and Controller already consume, so neither needs to change to work off a
# WebSocket connection instead of a local chess_engine.GameEngine.
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from chess_engine.engine.event_manager import EventManager
from chess_engine.engine.events import MoveAccepted, PieceCaptured
from chess_engine.engine.helpers.move_history import MoveHistory, MoveRecord
from chess_engine.engine.helpers.score_manager import CapturedEntry, ScoreManager
from chess_engine.engine.helpers.snapshot_helpers import build_snapshot
from chess_engine.engine.helpers.snapshot_models import GameSnapshot
from chess_engine.input.board_mapper import BoardMapper
from chess_engine.input.controller import Controller
from chess_engine.model.board import Board
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position
from chess_engine.realtime.motion import Motion
from chess_engine.rules.engine import MoveValidation, RuleEngine
from chess_engine.wire.notation import build_move_command, refresh_board
from chess_engine.wire.state import deserialize_cooldowns, deserialize_motions

SendEnvelope = Callable[[dict[str, Any]], Awaitable[None]]


class NetworkGameFacade:
    # Stands in for both `runtime.engine` and `runtime.arbiter` — GuiRunner
    # only ever calls methods on them, never checks their type — and is the
    # `engine=` a real, unmodified Controller is built against: Controller's
    # click handling reaches chess_engine's IGameEngine Protocol, which this
    # satisfies by sending network commands instead of mutating a local
    # GameEngine. MoveHistory/ScoreManager are the same chess_engine helpers
    # GameEngine itself uses internally, fed by translated network events
    # instead of a live EventManager.

    def __init__(self, board: Board, send_envelope: SendEnvelope) -> None:
        self._board = board
        self._send_envelope = send_envelope
        self._motions: list[Motion] = []
        self._cooldowns: dict[Position, int] = {}
        self._game_over = False
        self._events = EventManager()
        self._history = MoveHistory(self._events)
        self._score = ScoreManager(self._events)
        self._rule_engine = RuleEngine()

    # --------------------------------------------------- inbound: network -> facade

    def apply_state_tick(
        self,
        board_grid: list[list[Optional[str]]],
        active_motions: list[dict],
        cooldowns: list[dict],
        game_over: bool,
    ) -> None:
        refresh_board(self._board, board_grid)
        self._motions = deserialize_motions(active_motions)
        self._cooldowns = deserialize_cooldowns(cooldowns)
        self._game_over = game_over

    def apply_move_accepted(
        self,
        color: Color,
        piece_type: PieceType,
        source: Position,
        destination: Position,
        is_capture: bool,
    ) -> None:
        self._events.publish(MoveAccepted(
            color=color, piece_type=piece_type,
            source=source, destination=destination, is_capture=is_capture,
        ))

    def apply_piece_captured(self, piece_type: PieceType, piece_color: Color, captured_by: Color) -> None:
        self._events.publish(PieceCaptured(piece=Piece(piece_type, piece_color), captured_by=captured_by))

    def apply_game_over(self) -> None:
        self._game_over = True

    # --------------------------------------------------- outbound: GuiRunner -> facade

    def advance_time(self, _ms: int) -> None:
        pass  # the server is the sole clock; nothing to simulate locally

    def get_snapshot(self, selected_cell: Optional[Position] = None) -> GameSnapshot:
        return build_snapshot(self._board, selected_cell, self._game_over)

    def get_active_motions(self) -> list[Motion]:
        return self._motions

    def get_cooldowns(self) -> dict[Position, int]:
        return self._cooldowns

    def get_captured(self, color: Color) -> list[CapturedEntry]:
        return self._score.get_captured(color)

    def get_scores(self) -> dict[Color, int]:
        return self._score.get_scores()

    def history_entries(self) -> list[MoveRecord]:
        return self._history.entries()

    # --------------------------------------------------- IGameEngine Protocol: Controller -> facade

    def request_move(self, source: Position, destination: Position) -> None:
        self._send_command("move", source, destination)

    def request_jump(self, position: Position) -> None:
        self._send_command("jump", position, position)

    def validate_move(self, board: Board, source: Position, destination: Position) -> MoveValidation:
        return self._rule_engine.validate_move(board, source, destination)

    def _send_command(self, command_type: str, source: Position, destination: Position) -> None:
        piece = self._board.get(source)
        if piece is None:
            return
        cmd = build_move_command(piece.color, piece.piece_type, source, destination)
        envelope = {"type": command_type, "data": {"cmd": cmd}}
        asyncio.create_task(self._send_envelope(envelope))


@dataclass
class NetworkGameRuntime:
    # Duck-type compatible with app_gateways.text_cli.bootstrap.GameRuntime —
    # GuiRunner only ever reads .board/.engine/.arbiter/.controller off it.
    board: Board
    engine: NetworkGameFacade
    arbiter: NetworkGameFacade
    controller: Controller


def build_network_runtime(board: Board, send_envelope: SendEnvelope) -> NetworkGameRuntime:
    facade = NetworkGameFacade(board, send_envelope)
    controller = Controller(engine=facade, mapper=BoardMapper(board), board=board)
    return NetworkGameRuntime(board=board, engine=facade, arbiter=facade, controller=controller)
