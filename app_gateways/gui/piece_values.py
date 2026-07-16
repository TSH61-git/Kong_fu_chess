# Point values awarded for capturing each piece type — tune freely, used by the
# side panel's "captured" score. Standard chess values aren't wired in yet, so
# everything defaults to _DEFAULT except the queen; adjust per-type as needed.
from __future__ import annotations

from chess_engine.model.piece import PieceType

_DEFAULT = 5

PIECE_VALUES: dict[PieceType, int] = {
    PieceType.QUEEN:  9,
    PieceType.ROOK:   5,
    PieceType.BISHOP: 3,
    PieceType.KNIGHT: 3,
    PieceType.PAWN:   1,
    PieceType.KING:   10,
}
