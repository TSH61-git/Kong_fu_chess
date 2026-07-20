# Command Pattern dispatcher — envelope "type" -> handler. Adding a wire
# command means registering one function here, never editing a branch chain.
from __future__ import annotations

from typing import Callable

from server.core.protocol import Envelope, ErrorCode, encode_error
from server.game import commands
from server.game.match import MatchSession
from server.network.session import ClientSession

CommandHandler = Callable[[ClientSession, Envelope, MatchSession], str]

_HANDLERS: dict[str, CommandHandler] = {
    "move": commands.handle_move,
    "jump": commands.handle_jump,
    "ping": commands.handle_ping,
}


def dispatch(session: ClientSession, envelope: Envelope, match: MatchSession) -> str:
    handler = _HANDLERS.get(envelope.type)
    if handler is None:
        return encode_error(
            envelope.id, ErrorCode.UNKNOWN_COMMAND_TYPE, f"unknown command type: {envelope.type!r}",
        )
    return handler(session, envelope, match)
