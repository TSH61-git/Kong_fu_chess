"""
Coordinate adapter for the input layer.

Responsibility
--------------
Translate raw pixel coordinates (from mouse events or the text DSL) into
logical grid positions understood by the rest of the system.

This module is the ONLY place in the codebase that knows the physical
cell size in pixels.  No other layer may perform pixel arithmetic.

Constants
---------
CELL_SIZE : int
    Width and height of a single board cell in pixels (100 px).

Classes
-------
BoardMapper
    Stateless adapter constructed with a read-only Board reference.
    Uses Board.is_inside to validate the resulting Position without
    ever reading or writing cell contents.
"""
from __future__ import annotations

from typing import Optional

from model.board import Board
from model.position import Position

CELL_SIZE: int = 100


class BoardMapper:
    """
    Translates pixel coordinates into logical board positions.

    The mapper holds a reference to the Board solely to call
    Board.is_inside for boundary validation.  It never reads or
    modifies cell contents.

    Args:
        board: The current game board.  Used read-only for dimension
               queries via is_inside.
    """

    def __init__(self, board: Board) -> None:
        self._board = board

    def pixel_to_cell(self, x: int, y: int) -> Optional[Position]:
        """
        Convert pixel coordinates to a grid Position.

        Computes col = x // CELL_SIZE and row = y // CELL_SIZE, then
        validates the result against the board boundaries.

        Args:
            x: Horizontal pixel coordinate (left = 0).
            y: Vertical pixel coordinate (top = 0).

        Returns:
            A Position(row, col) if the pixel falls inside the board,
            or None if it falls outside (including negative values).
        """
        if x < 0 or y < 0:
            return None
        pos = Position(row=y // CELL_SIZE, col=x // CELL_SIZE)
        return pos if self._board.is_inside(pos) else None
