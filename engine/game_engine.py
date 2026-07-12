"""
Application Service layer — GameEngine.

Responsibility
--------------
GameEngine is the central orchestrator of the game flow.  It sits between
the input layer (Controller) and the real-time coordination layer
(RealTimeArbiter), enforcing application-level guards before delegating
to either the RuleEngine or the arbiter.

Dependency direction (downward only):
  GameEngine → RuleEngine → PieceRules → Model
  GameEngine → IRealTimeArbiter  (Protocol; concrete impl in Step 5)
  GameEngine → Board (read for snapshot and token lookup)

Public types
------------
MoveResult
    Frozen dataclass returned by request_move.
    Fields: is_accepted (bool), reason (str).
    Reason values: "ok", "game_over", "motion_in_progress",
    or any reason string produced by RuleEngine.validate_move.

GameSnapshot
    Frozen DTO consumed by the Renderer and BoardPrinter.
    Contains a deep-copied board grid so the view layer cannot
    accidentally mutate live game state through the snapshot.
    Fields: board_width, board_height, board_grid, selected_cell,
            game_over.

IRealTimeArbiter
    Structural Protocol defining the subset of the arbiter's interface
    that GameEngine depends on.  The concrete RealTimeArbiter built in
    Step 5 will satisfy this protocol without explicit inheritance.

GameEngine
----------
Guards evaluated inside request_move (strict order):
  1. game_over          — rejects immediately; RuleEngine never consulted.
  2. motion_in_progress — rejects immediately; RuleEngine never consulted.
  3. RuleEngine.validate_move — rejects with the rule reason if invalid.
  4. arbiter.start_motion — called only when all guards pass.

wait(ms)
    Pure delegation to arbiter.advance_time(ms).
    GameEngine never mutates the Board inside this method.

snapshot(selected_cell)
    Builds a GameSnapshot from the current board state.
    selected_cell is an optional parameter supplied by the caller
    (typically the Controller) since GameEngine does not track UI
    selection state — that belongs to the Controller.

notify_king_captured()
    Hook called by RealTimeArbiter at the precise millisecond a King
    is captured.  Sets _game_over = True.  All subsequent request_move
    calls will be rejected with reason "game_over".
"""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import List, Optional, Protocol

from model.board import Board
from model.position import Position
from rules.rule_engine import RuleEngine

# ------------------------------------------------------------------ #
# Stable reason string constants                                      #
# ------------------------------------------------------------------ #

_OK                = "ok"
_GAME_OVER         = "game_over"
_MOTION_IN_PROGRESS = "motion_in_progress"


# ------------------------------------------------------------------ #
# Public DTOs                                                         #
# ------------------------------------------------------------------ #

@dataclass(frozen=True)
class MoveResult:
    """
    Immutable result of a single request_move call.

    Attributes:
        is_accepted: True only when the move was accepted and a motion
                     was started by the arbiter.
        reason:      Machine-readable outcome string.  Always populated.
                     One of: "ok", "game_over", "motion_in_progress",
                     or a reason string from RuleEngine.validate_move.
    """
    is_accepted: bool
    reason: str


@dataclass(frozen=True)
class GameSnapshot:
    """
    Read-only view of the current game state for the renderer.

    board_grid is a deep copy of the live board's token matrix.
    Mutating it has no effect on the running game.

    Attributes:
        board_width:  Number of columns on the board.
        board_height: Number of rows on the board.
        board_grid:   Deep-copied 2-D list of token strings.
        selected_cell: The currently highlighted cell, or None.
        game_over:    True once a King has been captured.
    """
    board_width: int
    board_height: int
    board_grid: List[List[str]]
    selected_cell: Optional[Position]
    game_over: bool


# ------------------------------------------------------------------ #
# IRealTimeArbiter Protocol                                           #
# ------------------------------------------------------------------ #

class IRealTimeArbiter(Protocol):
    """
    Structural interface for the real-time coordination layer.

    GameEngine depends on this Protocol rather than the concrete
    RealTimeArbiter to prevent a forward dependency.  Any object
    exposing the required methods satisfies the protocol.
    """

    def has_active_motion(self) -> bool:
        """Return True if any piece is currently in transit."""
        ...

    def get_active_motions(self):
        """Return a snapshot of the currently active motions."""
        ...

    def start_motion(
        self,
        piece: str,
        source: Position,
        destination: Position,
    ) -> None:
        """
        Register a new active motion for the given piece.

        Args:
            piece:       Token string of the moving piece (e.g. 'wR').
            source:      Grid position the piece departs from.
            destination: Grid position the piece is travelling to.
        """
        ...

    def advance_time(self, ms: int) -> None:
        """
        Advance the virtual timeline by ms milliseconds.

        Triggers any arrivals that fall within the elapsed window.
        """
        ...


# ------------------------------------------------------------------ #
# GameEngine                                                          #
# ------------------------------------------------------------------ #

class GameEngine:
    """
    Application Service orchestrator.

    Coordinates the Board, RuleEngine, and RealTimeArbiter.
    Enforces application-level guards before delegating to lower layers.
    Holds no piece-specific movement formulas and performs no rendering.

    Args:
        board:       The live game board.  Read for token lookup and
                     snapshot generation; written only by the arbiter.
        rule_engine: Stateless move-validation service.
        arbiter:     Any object satisfying IRealTimeArbiter.
    """

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

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def _get_active_motions(self):
        """Return active motions from the arbiter when it exposes them."""
        arbiter_type = getattr(type(self._arbiter), "get_active_motions", None)
        if callable(arbiter_type):
            motions = self._arbiter.get_active_motions()
            if motions is None:
                return []
            return list(motions)
        return []

    def _is_source_locked(self, source: Position) -> bool:
        """Return True when the requested source is already in flight."""
        return any(
            getattr(motion, "source", None) == source
            for motion in self._get_active_motions()
        )

    def _is_linear_move(self, source: Position, destination: Position) -> bool:
        """Return True for standard row/column/diagonal moves."""
        if source == destination:
            return False
        return (
            source.row == destination.row
            or source.col == destination.col
            or abs(source.row - destination.row) == abs(source.col - destination.col)
        )

    def _path_intersects(self, source: Position, destination: Position) -> bool:
        """Return True when the requested linear route overlaps an active linear route."""
        if not self._is_linear_move(source, destination):
            return False

        for motion in self._get_active_motions():
            other_source = getattr(motion, "source", None)
            other_destination = getattr(motion, "destination", None)
            if other_source is None or other_destination is None:
                continue
            if not self._is_linear_move(other_source, other_destination):
                continue

            if self._segments_overlap(source, destination, other_source, other_destination):
                return True
        return False

    def _segments_overlap(
        self,
        source_a: Position,
        destination_a: Position,
        source_b: Position,
        destination_b: Position,
    ) -> bool:
        """Return True when two linear segments share at least one grid cell."""
        path_a = self._linear_path(source_a, destination_a)
        path_b = self._linear_path(source_b, destination_b)
        return any(position in path_b for position in path_a)

    def _linear_path(self, source: Position, destination: Position) -> list[Position]:
        """Return all cells travelled by a linear move, including endpoints."""
        if source == destination:
            return [source]

        delta_row = 0 if source.row == destination.row else (1 if destination.row > source.row else -1)
        delta_col = 0 if source.col == destination.col else (1 if destination.col > source.col else -1)

        path: list[Position] = []
        current = source
        while current != destination:
            path.append(current)
            current = Position(current.row + delta_row, current.col + delta_col)
        path.append(destination)
        return path

    def request_move(
        self,
        source: Position,
        destination: Position,
    ) -> MoveResult:
        """
        Attempt to initiate a piece move from source to destination.

        Evaluates four ordered guards before accepting the move.
        Returns a MoveResult describing the outcome.

        Args:
            source:      Position of the piece to move.
            destination: Intended target position.

        Returns:
            MoveResult with is_accepted=True and reason="ok" when the
            move is accepted, or is_accepted=False with the blocking
            reason otherwise.
        """
        # Guard 1 — game already ended
        if self._game_over:
            return MoveResult(is_accepted=False, reason=_GAME_OVER)

        # Guard 2 — same piece already in motion
        if self._is_source_locked(source):
            return MoveResult(is_accepted=False, reason=_MOTION_IN_PROGRESS)

        # Guard 3 — shared linear route already in use
        if self._path_intersects(source, destination):
            return MoveResult(is_accepted=False, reason=_MOTION_IN_PROGRESS)

        # Guard 4 — chess rule validation
        validation = self._rule_engine.validate_move(
            self._board, source, destination
        )
        if not validation.is_valid:
            return MoveResult(is_accepted=False, reason=validation.reason)

        # Guard 5 — all clear: read piece token and start motion
        piece = self._board.get(source)
        self._arbiter.start_motion(
            piece=piece,
            source=source,
            destination=destination,
        )
        return MoveResult(is_accepted=True, reason=_OK)

    def validate_move(self, board: Board, source: Position, destination: Position):
        """Expose the underlying rules-layer validation result to the controller."""
        return self._rule_engine.validate_move(board, source, destination)

    def request_jump(self, position: Position) -> MoveResult:
        """Start an in-place jump motion for the piece at position.

        The jump is represented as a zero-distance motion with a fixed
        1000ms duration.  It is used for the console DSL flow and leaves
        promotion logic untouched.
        """
        if self._game_over:
            return MoveResult(is_accepted=False, reason=_GAME_OVER)

        if self._is_source_locked(position):
            return MoveResult(is_accepted=False, reason=_MOTION_IN_PROGRESS)

        if self._board.get(position) == ".":
            return MoveResult(is_accepted=False, reason="empty_source")

        self._arbiter.start_motion(
            piece=self._board.get(position),
            source=position,
            destination=position,
            duration_ms=1000,
        )
        return MoveResult(is_accepted=True, reason=_OK)

    def wait(self, ms: int) -> None:
        """
        Advance the virtual timeline by ms milliseconds.

        Delegates entirely to the arbiter.  GameEngine never mutates
        the Board inside this method.

        Args:
            ms: Milliseconds to advance.
        """
        self._arbiter.advance_time(ms)

    def snapshot(
        self,
        selected_cell: Optional[Position] = None,
    ) -> GameSnapshot:
        """
        Build a read-only snapshot of the current game state.

        The board grid is deep-copied so the caller cannot mutate live
        state through the returned DTO.

        Args:
            selected_cell: The currently highlighted cell from the
                           Controller, or None.  GameEngine does not
                           track UI selection state itself.

        Returns:
            A frozen GameSnapshot reflecting the current board and flags.
        """
        grid = [
            [self._board.get(Position(r, c)) for c in range(self._board.cols)]
            for r in range(self._board.rows)
        ]
        return GameSnapshot(
            board_width=self._board.cols,
            board_height=self._board.rows,
            board_grid=grid,
            selected_cell=selected_cell,
            game_over=self._game_over,
        )

    def notify_king_captured(self) -> None:
        """
        Signal that a King has been captured.

        Called by RealTimeArbiter at the precise millisecond of arrival.
        Sets the game_over flag; all subsequent request_move calls will
        be rejected immediately with reason "game_over".
        """
        self._game_over = True
