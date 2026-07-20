# Base shape every Bus-carried event extends. Later sub-packages append
# their own event types on top of this — this shape itself is never redefined.
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ServerEvent:
    ts: float
