# Wire protocol: envelope encode/decode and the ErrorCode vocabulary.
# Server-to-client messages are always one of ack / error / broadcast / notice.
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ErrorCode(Enum):
    OK = "OK"
    GAME_OVER = "GAME_OVER"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    MOTION_IN_PROGRESS = "MOTION_IN_PROGRESS"
    DESTINATION_CLAIMED = "DESTINATION_CLAIMED"
    ILLEGAL_PIECE_MOVE = "ILLEGAL_PIECE_MOVE"
    FRIENDLY_DESTINATION = "FRIENDLY_DESTINATION"
    EMPTY_SOURCE = "EMPTY_SOURCE"
    OUTSIDE_BOARD = "OUTSIDE_BOARD"
    MALFORMED_COMMAND = "MALFORMED_COMMAND"
    UNKNOWN_COMMAND_TYPE = "UNKNOWN_COMMAND_TYPE"
    PIECE_MISMATCH = "PIECE_MISMATCH"
    NOT_YOUR_COLOR = "NOT_YOUR_COLOR"
    VIEWER_READ_ONLY = "VIEWER_READ_ONLY"
    ROOM_NOT_READY = "ROOM_NOT_READY"


# chess_engine's MoveResult.reason / MoveValidation.reason strings, confirmed
# in game_engine.py and rules/guards/*.py, mapped 1:1 onto the wire vocabulary.
_ENGINE_REASON_TO_ERROR_CODE: dict[str, ErrorCode] = {
    "ok": ErrorCode.OK,
    "game_over": ErrorCode.GAME_OVER,
    "cooldown_active": ErrorCode.COOLDOWN_ACTIVE,
    "motion_in_progress": ErrorCode.MOTION_IN_PROGRESS,
    "destination_claimed": ErrorCode.DESTINATION_CLAIMED,
    "illegal_piece_move": ErrorCode.ILLEGAL_PIECE_MOVE,
    "friendly_destination": ErrorCode.FRIENDLY_DESTINATION,
    "empty_source": ErrorCode.EMPTY_SOURCE,
    "outside_board": ErrorCode.OUTSIDE_BOARD,
}


def error_code_for_engine_reason(reason: str) -> ErrorCode:
    return _ENGINE_REASON_TO_ERROR_CODE[reason]


class MalformedEnvelopeError(Exception):
    pass


@dataclass(frozen=True)
class Envelope:
    type: str
    id: Optional[str]
    data: dict[str, Any]


def decode_envelope(raw: str) -> Envelope:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MalformedEnvelopeError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict) or "type" not in payload:
        raise MalformedEnvelopeError("envelope must be a JSON object with a 'type' field")
    return Envelope(type=payload["type"], id=payload.get("id"), data=payload.get("data") or {})


def encode_ack(in_reply_to: Optional[str], data: Optional[dict[str, Any]] = None) -> str:
    return json.dumps({"type": "ack", "in_reply_to": in_reply_to, "ok": True, "data": data or {}})


def encode_error(in_reply_to: Optional[str], code: ErrorCode, message: str = "") -> str:
    return json.dumps({
        "type": "error",
        "in_reply_to": in_reply_to,
        "code": code.value,
        "message": message,
    })


def encode_broadcast(room_id: str, event: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": "broadcast", "event": event, "room_id": room_id, "data": data})


def encode_notice(event: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": "notice", "event": event, "data": data})
