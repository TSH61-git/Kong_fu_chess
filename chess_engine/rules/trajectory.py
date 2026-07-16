# Trajectory math — linear path generation and route overlap detection.
from __future__ import annotations
from chess_engine.model.position import Position


def linear_path(source: Position, destination: Position) -> list[Position]:
    if source == destination:
        return [source]
    if not _is_linear_move(source, destination):
        return [source, destination]
    dr = 0 if source.row == destination.row else (1 if destination.row > source.row else -1)
    dc = 0 if source.col == destination.col else (1 if destination.col > source.col else -1)
    path: list[Position] = []
    cur = source
    while cur != destination:
        path.append(cur)
        cur = Position(cur.row + dr, cur.col + dc)
    path.append(destination)
    return path


def _is_linear_move(source: Position, destination: Position) -> bool:
    if source == destination:
        return False
    return (source.row == destination.row
            or source.col == destination.col
            or abs(source.row - destination.row) == abs(source.col - destination.col))


def has_route_conflict(
    source_a: Position, destination_a: Position,
    source_b: Position, destination_b: Position,
) -> bool:
    if not _is_linear_move(source_a, destination_a):
        return False
    if not _is_linear_move(source_b, destination_b):
        return False
    path_b = set(linear_path(source_b, destination_b))
    return any(p in path_b for p in linear_path(source_a, destination_a))
