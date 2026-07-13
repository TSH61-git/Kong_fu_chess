"""Mutable motion state for a single in-flight piece movement."""
from __future__ import annotations

from dataclasses import dataclass

from model.position import Position


@dataclass(eq=False)
class Motion:
    """Mutable state for a single in-flight piece movement."""

    piece: str
    source: Position
    destination: Position
    elapsed_ms: int = 0
    duration_ms: int = 0
