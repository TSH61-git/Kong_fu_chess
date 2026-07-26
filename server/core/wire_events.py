# Shared wire-vocabulary enums: message envelope kind, broadcast/notice event
# names, and inbound command types. Single source of truth for every raw
# string that used to be duplicated across protocol.py, dispatch.py,
# engine_bridge.py, matchmaker.py, rooms/commands.py, and dev_client.py.
from __future__ import annotations

from enum import Enum


class MessageType(str, Enum):
    ACK = "ack"
    ERROR = "error"
    BROADCAST = "broadcast"
    NOTICE = "notice"


class WireEvent(str, Enum):
    MOVE_ACCEPTED = "move_accepted"
    PIECE_CAPTURED = "piece_captured"
    GAME_OVER = "game_over"
    STATE_TICK = "state_tick"
    MATCH_READY = "match_ready"
    OPPONENT_DISCONNECTED = "opponent_disconnected"
    OPPONENT_RECONNECTED = "opponent_reconnected"
    SEATED = "seated"
    QUEUE_TIMEOUT = "queue_timeout"


class CommandType(str, Enum):
    MOVE = "move"
    JUMP = "jump"
    PING = "ping"
    REGISTER = "register"
    LOGIN = "login"
    QUEUE_JOIN = "queue_join"
    QUEUE_CANCEL = "queue_cancel"
    ROOM_CREATE = "room_create"
    ROOM_JOIN = "room_join"


class GameOverReason(str, Enum):
    KING_CAPTURED = "king_captured"
    DISCONNECT_TIMEOUT = "disconnect_timeout"
    BOTH_DISCONNECTED = "both_disconnected"
