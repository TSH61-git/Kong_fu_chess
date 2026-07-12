"""
User interaction controller for the input layer.

Responsibility
--------------
Manage the two-click selection state machine that translates physical
user interactions into move intents forwarded to the game engine.

The Controller is the ONLY component that tracks which cell the user
has currently selected.  It enforces the following policy:

  First click (no selection):
    - Outside board  → ignore entirely.
    - Empty cell     → ignore entirely.
    - Piece cell     → record as selected_cell.

  Second click (selection active):
    - Outside board  → clear selection; do NOT call request_move.
    - Inside board   → call engine.request_move(source, destination)
                       with the recorded and new positions, then
                       clear selection unconditionally.

The Controller never evaluates chess rules, never reads piece colors,
and never calls Board.set.  All legality decisions belong to the engine.

IGameEngine protocol
--------------------
Controller depends on a structural Protocol rather than a concrete class
to avoid a circular import when GameEngine is introduced in Step 4.
Any object that exposes request_move(source, destination) satisfies it.
"""
from __future__ import annotations

from typing import Optional, Protocol

from model.board import Board
from model.position import Position
from input.board_mapper import BoardMapper
from rules.rule_engine import MoveValidation

_EMPTY = "."


class IGameEngine(Protocol):
    """
    Minimal structural interface required by Controller.

    Any object implementing request_move satisfies this protocol.
    The concrete GameEngine introduced in Step 4 will conform to it
    without explicit inheritance.
    """

    def request_move(self, source: Position, destination: Position) -> None:
        """Submit a move intent from source to destination."""
        ...

    def validate_move(self, board: Board, source: Position, destination: Position) -> MoveValidation:
        """Validate a proposed move without mutating the board."""
        ...


class Controller:
    """
    Two-click selection state machine.

    Translates pixel click events into move intents and forwards them
    to the game engine.  Holds no chess knowledge whatsoever.

    Args:
        engine: Any object satisfying IGameEngine (has request_move).
        mapper: BoardMapper used to convert pixel coords to Positions.
        board:  Read-only Board reference used to inspect cell contents
                for the first-click empty-cell guard.
    """

    def __init__(
        self,
        engine: IGameEngine,
        mapper: BoardMapper,
        board: Board,
    ) -> None:
        self._engine = engine
        self._mapper = mapper
        self._board = board
        self._selected_cell: Optional[Position] = None

    @property
    def selected_cell(self) -> Optional[Position]:
        """The currently selected grid position, or None if nothing is selected."""
        return self._selected_cell

    def click(self, x: int, y: int) -> None:
        """
        Process a single pixel click event.

        Applies the two-click policy described in the module docstring.
        Selection state is always consistent after this call returns.

        Args:
            x: Horizontal pixel coordinate of the click.
            y: Vertical pixel coordinate of the click.
        """
        cell = self._mapper.pixel_to_cell(x, y)

        if self._selected_cell is None:
            self._handle_first_click(cell)
        else:
            self._handle_second_click(cell)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _handle_first_click(self, cell: Optional[Position]) -> None:
        """
        Process a click when no piece is currently selected.

        Selects the cell only if it is inside the board and contains
        a piece token (i.e. is not the empty sentinel '.').
        """
        if cell is None:
            return
        if self._board.get(cell) == _EMPTY:
            return
        self._selected_cell = cell

    def _handle_second_click(self, cell: Optional[Position]) -> None:
        """
        Process a click when a piece is already selected.

        If the click is outside the board, the selection is cancelled
        silently.  If it is inside the board, the controller asks the
        engine to validate the intended move. A friendly-destination result
        is treated as a selection swap rather than a move request.
        """
        source = self._selected_cell
        if source is None or cell is None:
            self._selected_cell = None
            return

        validation = self._engine.validate_move(self._board, source, cell)
        if validation.reason == "friendly_destination":
            self._selected_cell = cell
            return

        self._selected_cell = None
        self._engine.request_move(source=source, destination=cell)
