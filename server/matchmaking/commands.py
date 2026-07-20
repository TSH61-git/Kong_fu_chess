# Wire handlers for queue_join/queue_cancel. Mirrors auth/commands.py's
# shape (session, envelope, context) -> str.
from __future__ import annotations

from server.core.protocol import Envelope, ErrorCode, encode_ack, encode_error
from server.network.context import ServerContext
from server.network.session import ClientSession


async def handle_queue_join(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    if session.user_id is None:
        return encode_error(envelope.id, ErrorCode.NOT_AUTHENTICATED, "login or register before queuing")
    if session.current_match is not None:
        return encode_error(envelope.id, ErrorCode.ALREADY_IN_MATCH, "already in a match")
    if context.queue.contains(session):
        return encode_error(envelope.id, ErrorCode.ALREADY_QUEUED, "already queued")

    user = await context.auth_service.users_repo.get_by_id(session.user_id)
    context.queue.enqueue(session, user.elo, context.clock.now())
    return encode_ack(envelope.id, {"elo": user.elo})


async def handle_queue_cancel(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    if session.user_id is None:
        return encode_error(envelope.id, ErrorCode.NOT_AUTHENTICATED, "login or register before queuing")
    if not context.queue.cancel(session):
        return encode_error(envelope.id, ErrorCode.NOT_QUEUED, "not currently queued")
    return encode_ack(envelope.id)
