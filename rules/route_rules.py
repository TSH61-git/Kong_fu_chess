"""Pure trajectory geometry helpers for route-conflict detection."""
from __future__ import annotations

from model.position import Position


def _is_linear_move(source: Position, destination: Position) -> bool:
    """Return True for standard row/column/diagonal moves."""
    if source == destination:
        return False
    return (
        source.row == destination.row
        or source.col == destination.col
        or abs(source.row - destination.row) == abs(source.col - destination.col)
    )


def _linear_path(source: Position, destination: Position) -> list[Position]:
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


def _segments_overlap(
    source_a: Position,
    destination_a: Position,
    source_b: Position,
    destination_b: Position,
) -> bool:
    """Return True when two linear segments share at least one grid cell."""
    path_a = _linear_path(source_a, destination_a)
    path_b = _linear_path(source_b, destination_b)
    return any(position in path_b for position in path_a)


def has_route_conflict(
    source_a: Position,
    destination_a: Position,
    source_b: Position,
    destination_b: Position,
) -> bool:
    """Return True when two linear routes occupy at least one common grid cell."""
    if not _is_linear_move(source_a, destination_a):
        return False
    if not _is_linear_move(source_b, destination_b):
        return False
    return _segments_overlap(source_a, destination_a, source_b, destination_b)
