# Piece movement rules — legal destination computation per piece type.
from __future__ import annotations
from typing import Callable, Dict, Optional, Set
from chess_engine.model.board import Board
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.model.position import Position

_RuleFn = Callable[[Board, Position, Color], Set[Position]]


def _is_enemy(cell: Optional[Piece], color: Color) -> bool:
    return cell is not None and cell.color != color


def _is_friendly(cell: Optional[Piece], color: Color) -> bool:
    return cell is not None and cell.color == color


def _slide(board: Board, from_pos: Position, color: Color,
           directions: list[tuple[int, int]]) -> Set[Position]:
    result: Set[Position] = set()
    for dr, dc in directions:
        r, c = from_pos.row + dr, from_pos.col + dc
        while True:
            pos = Position(r, c)
            if not board.is_inside(pos):
                break
            cell = board.get(pos)
            if cell is None:
                result.add(pos)
            elif cell.color == color:
                break
            else:
                result.add(pos)
                break
            r += dr
            c += dc
    return result


def _rook(board: Board, from_pos: Position, color: Color) -> Set[Position]:
    return _slide(board, from_pos, color, [(-1, 0), (1, 0), (0, -1), (0, 1)])


def _bishop(board: Board, from_pos: Position, color: Color) -> Set[Position]:
    return _slide(board, from_pos, color, [(-1, -1), (-1, 1), (1, -1), (1, 1)])


def _queen(board: Board, from_pos: Position, color: Color) -> Set[Position]:
    return _slide(board, from_pos, color,
                  [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)])


def _knight(board: Board, from_pos: Position, color: Color) -> Set[Position]:
    result: Set[Position] = set()
    for dr, dc in [(-2, -1), (-2, 1), (-1, -2), (-1, 2), (1, -2), (1, 2), (2, -1), (2, 1)]:
        pos = Position(from_pos.row + dr, from_pos.col + dc)
        if board.is_inside(pos) and not _is_friendly(board.get(pos), color):
            result.add(pos)
    return result


def _king(board: Board, from_pos: Position, color: Color) -> Set[Position]:
    result: Set[Position] = set()
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            pos = Position(from_pos.row + dr, from_pos.col + dc)
            if board.is_inside(pos) and not _is_friendly(board.get(pos), color):
                result.add(pos)
    return result


def _pawn(board: Board, from_pos: Position, color: Color) -> Set[Position]:
    dr = -1 if color == Color.WHITE else 1
    result: Set[Position] = set()
    fwd = Position(from_pos.row + dr, from_pos.col)
    if board.is_inside(fwd) and board.get(fwd) is None:
        result.add(fwd)
        start_row = board.rows - 2 if color == Color.WHITE else 1
        if from_pos.row == start_row:
            double = Position(from_pos.row + 2 * dr, from_pos.col)
            if board.is_inside(double) and board.get(double) is None:
                result.add(double)
    for dc in (-1, 1):
        diag = Position(from_pos.row + dr, from_pos.col + dc)
        if board.is_inside(diag) and _is_enemy(board.get(diag), color):
            result.add(diag)
    return result


_REGISTRY: Dict[PieceType, _RuleFn] = {
    PieceType.ROOK:   _rook,
    PieceType.BISHOP: _bishop,
    PieceType.QUEEN:  _queen,
    PieceType.KNIGHT: _knight,
    PieceType.KING:   _king,
    PieceType.PAWN:   _pawn,
}


def legal_destinations(board: Board, from_pos: Position, piece: Piece) -> Set[Position]:
    rule_fn = _REGISTRY.get(piece.piece_type)
    return rule_fn(board, from_pos, piece.color) if rule_fn else set()
