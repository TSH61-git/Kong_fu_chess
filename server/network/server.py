# Pure WebSocket I/O boundary — accept loop, per-connection read loop, and
# session release. Owns zero game rules and zero seating: a connection
# never seats itself, it only ever gets a match via the matchmaker (see
# server/matchmaking/matchmaker.py), which is why this file has no
# knowledge of MatchSession at all.
from __future__ import annotations

import asyncio
import logging
import uuid

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from server.core.protocol import ErrorCode, MalformedEnvelopeError, decode_envelope, encode_error
from server.network.context import ServerContext
from server.network.dispatch import dispatch
from server.network.session import ClientSession

_logger = logging.getLogger("kfchess.network")


async def _handle_message(session, raw_message: str, context: ServerContext) -> None:
    try:
        envelope = decode_envelope(raw_message)
    except MalformedEnvelopeError as exc:
        await session.send(encode_error(None, ErrorCode.MALFORMED_COMMAND, str(exc)))
        return
    await session.send(await dispatch(session, envelope, context))


async def handle_connection(websocket: ServerConnection, context: ServerContext) -> None:
    # A connection starts unseated and unauthenticated. It only ever gets a
    # seat via the matchmaker, once authenticated and paired — never here.
    session_id = str(uuid.uuid4())
    session = ClientSession(session_id, websocket)
    _logger.info("Session %s connected", session_id)
    try:
        async for raw_message in websocket:
            await _handle_message(session, raw_message, context)
    except ConnectionClosed:
        pass
    finally:
        if session.current_match is not None:
            session.current_match.release(session)
        context.queue.cancel(session)  # no-op if not queued; drops a still-queued dead session
        _logger.info("Session %s disconnected", session_id)


async def serve_forever(host: str, port: int, context: ServerContext) -> None:
    async def handler(websocket: ServerConnection) -> None:
        await handle_connection(websocket, context)

    async with serve(handler, host, port):
        _logger.info("Listening on ws://%s:%s", host, port)
        await asyncio.Future()
