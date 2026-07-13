# Immutable grid coordinate — standalone, no external dependencies.
from dataclasses import dataclass


@dataclass(frozen=True)
class Position:
    # A grid coordinate (row, col). Immutable and hashable.
    row: int
    col: int
