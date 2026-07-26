# Shared vocabulary for move validation / rejection outcomes.
from __future__ import annotations

from enum import Enum


class MoveRejectReason(str, Enum):
    OK = "ok"
    GAME_OVER = "game_over"
    COOLDOWN_ACTIVE = "cooldown_active"
    MOTION_IN_PROGRESS = "motion_in_progress"
    DESTINATION_CLAIMED = "destination_claimed"
    ILLEGAL_PIECE_MOVE = "illegal_piece_move"
    FRIENDLY_DESTINATION = "friendly_destination"
    EMPTY_SOURCE = "empty_source"
    OUTSIDE_BOARD = "outside_board"
