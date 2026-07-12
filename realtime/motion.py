"""Mutable motion state for a single in-flight piece movement."""
from __future__ import annotations

from dataclasses import dataclass

from model.position import Position


@dataclass
class Motion:
    """Represents one active movement in the real-time arbiter.

    This value object is intentionally mutable so the arbiter can update
    elapsed time while preserving the original source, destination, and
    duration information for the current tick window.
    """

    piece: str
    source: Position
    destination: Position
    elapsed_ms: int = 0
    duration_ms: int = 0
