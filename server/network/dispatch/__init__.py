# Command Pattern dispatcher — envelope "type" -> handler. Adding a wire
# command means registering one function here, never editing a branch chain.
from __future__ import annotations

from typing import Awaitable, Callable

import logging

from server.auth import commands as auth_commands
from server.network.protocol import Envelope, ErrorCode, encode_error
from server.game import commands
from server.matchmaking import commands as matchmaking_commands
from server.network.server_context import ServerContext
from server.network.transport.session import ClientSession
from server.rooms import commands as rooms_commands
from server.core.wire_events import CommandType

_logger = logging.getLogger("kfchess.dispatch")

CommandHandler = Callable[[ClientSession, Envelope, ServerContext], Awaitable[str]]

_HANDLERS: dict[str, CommandHandler] = {
    CommandType.MOVE: commands.handle_move,
    CommandType.JUMP: commands.handle_jump,
    CommandType.PING: commands.handle_ping,
    CommandType.REGISTER: auth_commands.handle_register,
    CommandType.LOGIN: auth_commands.handle_login,
    CommandType.QUEUE_JOIN: matchmaking_commands.handle_queue_join,
    CommandType.QUEUE_CANCEL: matchmaking_commands.handle_queue_cancel,
    CommandType.ROOM_CREATE: rooms_commands.handle_room_create,
    CommandType.ROOM_JOIN: rooms_commands.handle_room_join,
}


async def dispatch(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    handler = _HANDLERS.get(envelope.type)
    if handler is None:
        return encode_error(
            envelope.id, ErrorCode.UNKNOWN_COMMAND_TYPE, f"unknown command type: {envelope.type!r}",
        )
    _logger.info("session=%s type=%s id=%s", session.session_id, envelope.type, envelope.id)
    return await handler(session, envelope, context)
