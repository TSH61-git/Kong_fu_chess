from __future__ import annotations
from enum import Enum


class AnimState(Enum):
    IDLE       = "idle"
    MOVE       = "move"
    JUMP       = "jump"
    LONG_REST  = "long_rest"
    SHORT_REST = "short_rest"
