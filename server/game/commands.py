# Authorization gate + engine invocation for move/jump commands. This is the
# ONLY place server code decides "is this call allowed" — chess_engine itself
# performs no color-ownership check by design (RuleEngine only guards
# boundary/empty-source/friendly-fire/legal-move), so every one of the checks
# below exists specifically because the engine will not perform it.
from __future__ import annotations

from chess_engine.model.piece import Color
from chess_engine.wire.notation import MalformedMoveCommandError, parse_move_command

from server.core.protocol import (
    Envelope,
    ErrorCode,
    encode_ack,
    encode_error,
    error_code_for_engine_reason,
)
from server.game.match import MatchSession
from server.network.session import ClientSession, Role

_ROLE_TO_COLOR: dict[Role, Color] = {Role.WHITE: Color.WHITE, Role.BLACK: Color.BLACK}


def handle_move(session: ClientSession, envelope: Envelope, match: MatchSession) -> str:
    return _handle_move_or_jump(session, envelope, match, is_jump=False)


def handle_jump(session: ClientSession, envelope: Envelope, match: MatchSession) -> str:
    return _handle_move_or_jump(session, envelope, match, is_jump=True)


def handle_ping(session: ClientSession, envelope: Envelope, match: MatchSession) -> str:
    return encode_ack(envelope.id)


def _handle_move_or_jump(
    session: ClientSession, envelope: Envelope, match: MatchSession, is_jump: bool,
) -> str:
    raw_command = envelope.data.get("cmd", "")
    try:
        parsed = parse_move_command(raw_command)
    except MalformedMoveCommandError as exc:
        return encode_error(envelope.id, ErrorCode.MALFORMED_COMMAND, str(exc))

    authorized_color = _ROLE_TO_COLOR[session.role]

    # The client-supplied color is never trusted as authority — it must agree
    # with the seat this session was assigned at join time.
    if parsed.color is not authorized_color:
        return encode_error(envelope.id, ErrorCode.NOT_YOUR_COLOR, "command color does not match your seat")

    # Cross-check against the live board, independent of the client's claim —
    # catches stale client state a moment after the piece moved or was
    # captured, which the check above alone would miss.
    piece = match.stack.board.get(parsed.source)
    if piece is None or piece.color is not authorized_color:
        return encode_error(envelope.id, ErrorCode.EMPTY_SOURCE, "no piece of your color on that square")
    if piece.piece_type is not parsed.piece_type:
        return encode_error(envelope.id, ErrorCode.PIECE_MISMATCH, "piece letter does not match the board")

    engine = match.stack.engine
    result = engine.request_jump(parsed.source) if is_jump else engine.request_move(
        parsed.source, parsed.destination,
    )
    if not result.is_accepted:
        return encode_error(envelope.id, error_code_for_engine_reason(result.reason))
    return encode_ack(envelope.id)
