# Wire handlers for room_create/room_join. Mirrors matchmaking/commands.py's
# shape (session, envelope, context) -> str.
from __future__ import annotations

import logging
import re

from chess_engine.model.piece import Color

from server.core.protocol import Envelope, ErrorCode, encode_ack, encode_error
from server.game.match import MatchSession, create_match_session
from server.network.context import ServerContext
from server.network.session import ClientSession
from server.rooms.codes import generate_room_code

_logger = logging.getLogger("kfchess.rooms")

_ALIAS_MIN_LEN, _ALIAS_MAX_LEN = 3, 12
_ALIAS_PATTERN = re.compile(r"[A-Z0-9]+")


def _match_state_payload(match: MatchSession) -> dict:
    # Included in every room_create/room_join ack (not just the viewer path)
    # so any joiner — including a viewer arriving mid-game, who misses the
    # original match_ready broadcast entirely — gets the current player
    # names and score in the same response that seats/spectates them,
    # instead of relying on a broadcast they may never see.
    scores = match.stack.engine.get_scores()
    return {
        "white_username": match.white.username if match.white is not None else None,
        "black_username": match.black.username if match.black is not None else None,
        "white_score": scores[Color.WHITE],
        "black_score": scores[Color.BLACK],
    }


async def handle_room_create(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    if session.user_id is None:
        return encode_error(envelope.id, ErrorCode.NOT_AUTHENTICATED, "login or register before creating a room")
    if session.current_match is not None:
        return encode_error(envelope.id, ErrorCode.ALREADY_IN_MATCH, "already in a match")

    requested = (envelope.data.get("room_id") or "").strip().upper()
    if requested:
        if not (_ALIAS_MIN_LEN <= len(requested) <= _ALIAS_MAX_LEN) or not _ALIAS_PATTERN.fullmatch(requested):
            return encode_error(
                envelope.id, ErrorCode.MALFORMED_COMMAND,
                "room name must be 3-12 alphanumeric characters",
            )
        if context.registry.get(requested) is not None:
            return encode_error(envelope.id, ErrorCode.ROOM_ALREADY_EXISTS, f"room {requested!r} already exists")
        code = requested
    else:
        code = generate_room_code(lambda c: context.registry.get(c) is not None)

    match = create_match_session(
        bus=context.bus, clock=context.clock, auth_service=context.auth_service,
        matches_repo=context.matches_repo, registry=context.registry, room_id=code,
    )
    match.try_seat(session)
    match.pause_for_opponent()
    _logger.info("Room %s created by user_id=%s", code, session.user_id)
    return encode_ack(envelope.id, {"room_id": code, "role": "white", **_match_state_payload(match)})


async def handle_room_join(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    if session.user_id is None:
        return encode_error(envelope.id, ErrorCode.NOT_AUTHENTICATED, "login or register before joining a room")
    if session.current_match is not None:
        return encode_error(envelope.id, ErrorCode.ALREADY_IN_MATCH, "already in a match")

    code = (envelope.data.get("room_id") or "").strip().upper()
    match = context.registry.get(code)
    if match is None:
        _logger.info("Room join failed: no room %r (user_id=%s)", code, session.user_id)
        return encode_error(envelope.id, ErrorCode.ROOM_NOT_FOUND, f"no room with code {code!r}")

    if match.try_seat(session):
        role = session.role.name.lower()
    else:
        match.add_viewer(session)
        role = "viewer"
    _logger.info("Room %s joined by user_id=%s as %s", code, session.user_id, role)
    return encode_ack(envelope.id, {"room_id": code, "role": role, **_match_state_payload(match)})
