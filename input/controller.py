"""Two-click selection state machine for the input layer."""
from __future__ import annotations

from typing import Optional, Protocol

from model.board import Board
from model.position import Position
from input.board_mapper import BoardMapper
from rules.rule_engine import MoveValidation

_EMPTY = "."


class IGameEngine(Protocol):
    """Minimal structural interface required by Controller."""

    def request_move(self, source: Position, destination: Position) -> None: ...
    def validate_move(self, board: Board, source: Position, destination: Position) -> MoveValidation: ...


class Controller:
    """Two-click selection state machine that forwards move intents to the engine."""

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
        cell = self._mapper.pixel_to_cell(x, y)

        if self._selected_cell is None:
            self._handle_first_click(cell)
        else:
            self._handle_second_click(cell)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _handle_first_click(self, cell: Optional[Position]) -> None:
        if cell is None:
            return
        if self._board.get(cell) == _EMPTY:
            return
        self._selected_cell = cell

    def _handle_second_click(self, cell: Optional[Position]) -> None:
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
