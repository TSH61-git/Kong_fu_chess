"""Stateless cooldown duration registry."""
from __future__ import annotations

from typing import Dict

_COOLDOWN_MS: Dict[str, int] = {
    "P": 1000,
    "R": 1000,
    "B": 1000,
    "N": 1000,
    "Q": 1000,
    "K": 1000,
}

_DEFAULT_COOLDOWN_MS = 1000


def get_cooldown_duration(piece_token: str) -> int:
    piece_type = piece_token[1] if len(piece_token) == 2 else ""
    return _COOLDOWN_MS.get(piece_type, _DEFAULT_COOLDOWN_MS)
