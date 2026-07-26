# GUI-local mirror of the wire-level game-over reason vocabulary the server
# sends in a "game_over" event's `reason` field. Deliberately not imported
# from server/ — the GUI must stay a plain client of the wire protocol, not
# a dependency of the server package (see CLAUDE.md's layer-boundary rules).
from __future__ import annotations

from enum import Enum


class GameOverReason(str, Enum):
    KING_CAPTURED = "king_captured"
    DISCONNECT_TIMEOUT = "disconnect_timeout"
    BOTH_DISCONNECTED = "both_disconnected"
