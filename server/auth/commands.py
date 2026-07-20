# Wire handlers for register/login. Mirrors game/commands.py's shape
# (session, envelope, match) -> str, so network/dispatch.py can register
# these next to move/jump/ping without any special-casing.
#
# This is the ONLY place match.try_seat is ever called, and only once the
# database has confirmed the credentials — a session never occupies a seat
# without first being a real, authenticated account.
from __future__ import annotations

from server.auth.service import InvalidCredentialsError, UsernameTakenError
from server.core.protocol import Envelope, ErrorCode, encode_ack, encode_error, encode_notice
from server.game.match import MatchSession
from server.network.session import ClientSession


async def handle_register(session: ClientSession, envelope: Envelope, match: MatchSession) -> str:
    username = envelope.data.get("username", "")
    password = envelope.data.get("password", "")
    if not username or not password:
        return encode_error(envelope.id, ErrorCode.MALFORMED_COMMAND, "username and password are required")

    try:
        user = await match.auth_service.register(username, password)
    except UsernameTakenError:
        return encode_error(envelope.id, ErrorCode.USERNAME_TAKEN, "username is already taken")

    return await _finish_login(session, envelope, match, user.id, user.username, user.elo)


async def handle_login(session: ClientSession, envelope: Envelope, match: MatchSession) -> str:
    username = envelope.data.get("username", "")
    password = envelope.data.get("password", "")
    if not username or not password:
        return encode_error(envelope.id, ErrorCode.MALFORMED_COMMAND, "username and password are required")

    try:
        user = await match.auth_service.login(username, password)
    except InvalidCredentialsError:
        return encode_error(envelope.id, ErrorCode.INVALID_CREDENTIALS, "invalid username or password")

    return await _finish_login(session, envelope, match, user.id, user.username, user.elo)


async def _finish_login(
    session: ClientSession, envelope: Envelope, match: MatchSession, user_id: int, username: str, elo: int,
) -> str:
    session.user_id = user_id
    session.username = username

    if not match.try_seat(session):
        session.user_id = None
        session.username = None
        return encode_error(envelope.id, ErrorCode.MATCH_FULL, "match is full")

    await session.send(encode_notice("seated", {"role": session.role.name.lower()}))
    return encode_ack(envelope.id, {"user_id": user_id, "username": username, "elo": elo})
