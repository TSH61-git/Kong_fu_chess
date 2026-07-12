"""
Position — immutable value object representing a logical grid coordinate.

Row and col are zero-based integers. No pixel or UI knowledge lives here.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    """A grid coordinate (row, col). Immutable and hashable."""
    row: int
    col: int
