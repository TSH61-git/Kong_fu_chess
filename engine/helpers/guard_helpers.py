"""Small helper functions for engine-level guard evaluation."""
from __future__ import annotations

from typing import List

from model.position import Position
from rules.route_rules import has_route_conflict


def get_active_motions(arbiter) -> List[object]:
    motions = arbiter.get_active_motions()
    if motions is None:
        return []
    return list(motions)


def is_source_locked(arbiter, source: Position) -> bool:
    return any(getattr(motion, "source", None) == source for motion in get_active_motions(arbiter))


def has_route_conflict_with_active_motions(arbiter, source: Position, destination: Position) -> bool:
    for motion in get_active_motions(arbiter):
        other_source = getattr(motion, "source", None)
        other_destination = getattr(motion, "destination", None)
        if other_source is None or other_destination is None:
            continue
        if has_route_conflict(source, destination, other_source, other_destination):
            return True
    return False
