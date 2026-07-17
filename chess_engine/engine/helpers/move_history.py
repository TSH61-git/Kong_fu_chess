# Chronological log of accepted moves, mirroring the MoveResult/GameSnapshot DTOs.
from __future__ import annotations

import time
from dataclasses import dataclass

from chess_engine.engine.event_manager import EventManager
from chess_engine.engine.events import MoveAccepted
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position

_PIECE_LETTERS: dict[PieceType, str] = {
    PieceType.KING:   "K",
    PieceType.QUEEN:  "Q",
    PieceType.ROOK:   "R",
    PieceType.BISHOP: "B",
    PieceType.KNIGHT: "N",
    PieceType.PAWN:   "P",
}

def _square(pos: Position) -> str:
    """Algebraic square name, e.g. Position(row=0, col=4) -> 'e8'."""
    file = chr(ord("a") + pos.col)
    rank = 8 - pos.row
    return f"{file}{rank}"


@dataclass(frozen=True)
class MoveRecord:
    index: int
    color: Color
    piece_type: PieceType
    source: Position
    destination: Position
    is_capture: bool
    timestamp: float

    def display_text(self) -> str:
        letter = _PIECE_LETTERS[self.piece_type]
        return f"{letter}{_square(self.destination)}"


class MoveHistory:
    """Records accepted moves in acceptance order.

    Kung-fu chess moves happen in real time rather than in alternating
    turns, so entries are a single chronological feed (not White/Black
    move pairs) ordered purely by when each request was accepted.
    """

    def __init__(self, events: EventManager) -> None:
        self._entries: list[MoveRecord] = []
        events.subscribe(MoveAccepted, self._on_move_accepted)

    def _on_move_accepted(self, event: MoveAccepted) -> None:
        self.record(
            Piece(event.piece_type, event.color),
            event.source,
            event.destination,
            is_capture=event.is_capture,
        )

    def record(
        self,
        piece: Piece,
        source: Position,
        destination: Position,
        is_capture: bool = False,
    ) -> None:
        self._entries.append(MoveRecord(
            index=len(self._entries) + 1,
            color=piece.color,
            piece_type=piece.piece_type,
            source=source,
            destination=destination,
            is_capture=is_capture,
            timestamp=time.time(),
        ))

    def entries(self) -> list[MoveRecord]:
        return self._entries
