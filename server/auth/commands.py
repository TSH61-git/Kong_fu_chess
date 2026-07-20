# Wire handlers for register/login. Mirrors game/commands.py's shape
# (session, envelope, context) -> str, so network/dispatch.py can register
# these next to move/jump/ping/queue_join without any special-casing.
#
# These handlers only ever authenticate — they never seat. Seating happens
# later, once the session queue_joins and the matchmaker pairs it (see
# server/matchmaking/matchmaker.py).
from __future__ import annotations

from server.auth.service import InvalidCredentialsError, UsernameTakenError
from server.core.protocol import Envelope, ErrorCode, encode_ack, encode_error
from server.network.context import ServerContext
from server.network.session import ClientSession


async def handle_register(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    username = envelope.data.get("username", "")
    password = envelope.data.get("password", "")
    if not username or not password:
        return encode_error(envelope.id, ErrorCode.MALFORMED_COMMAND, "username and password are required")

    try:
        user = await context.auth_service.register(username, password)
    except UsernameTakenError:
        return encode_error(envelope.id, ErrorCode.USERNAME_TAKEN, "username is already taken")

    return _finish_login(session, envelope, user.id, user.username, user.elo)


async def handle_login(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    username = envelope.data.get("username", "")
    password = envelope.data.get("password", "")
    if not username or not password:
        return encode_error(envelope.id, ErrorCode.MALFORMED_COMMAND, "username and password are required")

    try:
        user = await context.auth_service.login(username, password)
    except InvalidCredentialsError:
        return encode_error(envelope.id, ErrorCode.INVALID_CREDENTIALS, "invalid username or password")

    return _finish_login(session, envelope, user.id, user.username, user.elo)


def _finish_login(session: ClientSession, envelope: Envelope, user_id: int, username: str, elo: int) -> str:
    session.user_id = user_id
    session.username = username
    return encode_ack(envelope.id, {"user_id": user_id, "username": username, "elo": elo})
