"""Immutable data transfer objects for engine-level state snapshots."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from model.position import Position


@dataclass(frozen=True)
class MoveResult:
    """Immutable result of a single move request."""

    is_accepted: bool
    reason: str


@dataclass(frozen=True)
class GameSnapshot:
    """Read-only snapshot of the current game state for the presentation layer."""

    board_width: int
    board_height: int
    board_grid: List[List[str]]
    selected_cell: Optional[Position]
    game_over: bool
