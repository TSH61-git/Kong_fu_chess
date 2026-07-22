# Command Pattern dispatcher — envelope "type" -> handler. Adding a wire
# command means registering one function here, never editing a branch chain.
from __future__ import annotations

from typing import Awaitable, Callable

import logging

from server.auth import commands as auth_commands
from server.core.protocol import Envelope, ErrorCode, encode_error
from server.game import commands
from server.matchmaking import commands as matchmaking_commands
from server.network.context import ServerContext
from server.network.session import ClientSession
from server.rooms import commands as rooms_commands

_logger = logging.getLogger("kfchess.dispatch")

CommandHandler = Callable[[ClientSession, Envelope, ServerContext], Awaitable[str]]

_HANDLERS: dict[str, CommandHandler] = {
    "move": commands.handle_move,
    "jump": commands.handle_jump,
    "ping": commands.handle_ping,
    "register": auth_commands.handle_register,
    "login": auth_commands.handle_login,
    "queue_join": matchmaking_commands.handle_queue_join,
    "queue_cancel": matchmaking_commands.handle_queue_cancel,
    "room_create": rooms_commands.handle_room_create,
    "room_join": rooms_commands.handle_room_join,
}


async def dispatch(session: ClientSession, envelope: Envelope, context: ServerContext) -> str:
    handler = _HANDLERS.get(envelope.type)
    if handler is None:
        return encode_error(
            envelope.id, ErrorCode.UNKNOWN_COMMAND_TYPE, f"unknown command type: {envelope.type!r}",
        )
    _logger.info("session=%s type=%s id=%s", session.session_id, envelope.type, envelope.id)
    return await handler(session, envelope, context)
