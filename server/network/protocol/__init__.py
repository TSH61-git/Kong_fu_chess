# Wire protocol: envelope encode/decode and the ErrorCode vocabulary.
# Server-to-client messages are always one of ack / error / broadcast / notice.
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from chess_engine.rules.reasons import MoveRejectReason
from server.core.wire_events import MessageType


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
    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    USERNAME_TAKEN = "USERNAME_TAKEN"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    MATCH_FULL = "MATCH_FULL"
    ALREADY_IN_MATCH = "ALREADY_IN_MATCH"
    ALREADY_QUEUED = "ALREADY_QUEUED"
    NOT_QUEUED = "NOT_QUEUED"
    ROOM_NOT_FOUND = "ROOM_NOT_FOUND"
    ROOM_ALREADY_EXISTS = "ROOM_ALREADY_EXISTS"


# chess_engine's MoveResult.reason / MoveValidation.reason values (see
# chess_engine.rules.reasons.MoveRejectReason), mapped 1:1 onto the wire
# vocabulary.
_ENGINE_REASON_TO_ERROR_CODE: dict[MoveRejectReason, ErrorCode] = {
    MoveRejectReason.OK: ErrorCode.OK,
    MoveRejectReason.GAME_OVER: ErrorCode.GAME_OVER,
    MoveRejectReason.COOLDOWN_ACTIVE: ErrorCode.COOLDOWN_ACTIVE,
    MoveRejectReason.MOTION_IN_PROGRESS: ErrorCode.MOTION_IN_PROGRESS,
    MoveRejectReason.DESTINATION_CLAIMED: ErrorCode.DESTINATION_CLAIMED,
    MoveRejectReason.ILLEGAL_PIECE_MOVE: ErrorCode.ILLEGAL_PIECE_MOVE,
    MoveRejectReason.FRIENDLY_DESTINATION: ErrorCode.FRIENDLY_DESTINATION,
    MoveRejectReason.EMPTY_SOURCE: ErrorCode.EMPTY_SOURCE,
    MoveRejectReason.OUTSIDE_BOARD: ErrorCode.OUTSIDE_BOARD,
}


def error_code_for_engine_reason(reason: MoveRejectReason) -> ErrorCode:
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
    return json.dumps({"type": MessageType.ACK.value, "in_reply_to": in_reply_to, "ok": True, "data": data or {}})


def encode_error(in_reply_to: Optional[str], code: ErrorCode, message: str = "") -> str:
    return json.dumps({
        "type": MessageType.ERROR.value,
        "in_reply_to": in_reply_to,
        "code": code.value,
        "message": message,
    })


def encode_broadcast(room_id: str, event: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": MessageType.BROADCAST.value, "event": event, "room_id": room_id, "data": data})


def encode_notice(event: str, data: dict[str, Any]) -> str:
    return json.dumps({"type": MessageType.NOTICE.value, "event": event, "data": data})
