# Pure WebSocket I/O boundary — accept loop, per-connection read loop, and
# session seating/release. Owns zero game rules; every inbound message is
# handed to network/dispatch.py the moment it's decoded.
from __future__ import annotations

import asyncio
import logging
import uuid

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from server.core.protocol import ErrorCode, MalformedEnvelopeError, decode_envelope, encode_error
from server.game.match import MatchSession
from server.network.dispatch import dispatch
from server.network.session import ClientSession

_logger = logging.getLogger("kfchess.network")


async def _handle_message(session, raw_message: str, match: MatchSession) -> None:
    try:
        envelope = decode_envelope(raw_message)
    except MalformedEnvelopeError as exc:
        await session.send(encode_error(None, ErrorCode.MALFORMED_COMMAND, str(exc)))
        return
    await session.send(await dispatch(session, envelope, match))


async def handle_connection(websocket: ServerConnection, match: MatchSession) -> None:
    # A connection starts unseated and unauthenticated. It only ever gets a
    # seat via server/auth/commands.py, which calls match.try_seat after a
    # successful register/login — never here.
    session_id = str(uuid.uuid4())
    session = ClientSession(session_id, websocket)
    _logger.info("Session %s connected", session_id)
    try:
        async for raw_message in websocket:
            await _handle_message(session, raw_message, match)
    except ConnectionClosed:
        pass
    finally:
        match.release(session)
        _logger.info("Session %s disconnected", session_id)


async def serve_forever(host: str, port: int, match: MatchSession) -> None:
    async def handler(websocket: ServerConnection) -> None:
        await handle_connection(websocket, match)

    async with serve(handler, host, port):
        _logger.info("Listening on ws://%s:%s", host, port)
        await asyncio.Future()
