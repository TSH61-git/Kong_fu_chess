# Short, human-typable room codes for custom rooms — distinct from the UUID
# room_id matchmaking-created matches use, which is never shown to a player.
from __future__ import annotations

import secrets
from typing import Callable

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O/1/I — unambiguous when read aloud
_CODE_LENGTH = 6


def generate_room_code(exists: Callable[[str], bool]) -> str:
    while True:
        code = "".join(secrets.choice(_ALPHABET) for _ in range(_CODE_LENGTH))
        if not exists(code):
            return code
