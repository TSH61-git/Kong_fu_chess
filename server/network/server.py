# Pure WebSocket I/O boundary — accept loop, per-connection read loop, and
# session seating/release. Owns zero game rules; every inbound message is
# handed to network/dispatch.py the moment it's decoded.
from __future__ import annotations

import asyncio
import logging
import uuid

from websockets.asyncio.server import ServerConnection, serve
from websockets.exceptions import ConnectionClosed

from server.core.protocol import (
    ErrorCode,
    MalformedEnvelopeError,
    decode_envelope,
    encode_error,
    encode_notice,
)
from server.game.match import MatchSession
from server.network.dispatch import dispatch

_logger = logging.getLogger("kfchess.network")


async def _handle_message(session, raw_message: str, match: MatchSession) -> None:
    try:
        envelope = decode_envelope(raw_message)
    except MalformedEnvelopeError as exc:
        await session.send(encode_error(None, ErrorCode.MALFORMED_COMMAND, str(exc)))
        return
    await session.send(dispatch(session, envelope, match))


async def handle_connection(websocket: ServerConnection, match: MatchSession) -> None:
    session_id = str(uuid.uuid4())
    session = match.try_seat(session_id, websocket)
    if session is None:
        await websocket.close(code=1013, reason="match is full")
        return

    _logger.info("Session %s connected as %s", session_id, session.role.name)
    await session.send(encode_notice("seated", {"role": session.role.name.lower()}))
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
