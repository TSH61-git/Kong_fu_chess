from app_gateways.gui.animation.anim_state import AnimState
from app_gateways.gui.bootstrap import bootstrap_gui
from chess_engine.model.board import Board
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.model.position import Position
from config import CELL_SIZE


def _cell_to_px(row: int, col: int) -> tuple[int, int]:
    return col * CELL_SIZE + CELL_SIZE // 2, row * CELL_SIZE + CELL_SIZE // 2


def _make_runner_with_move(source: Position, destination: Position):
    board = Board(rows=8, cols=8)
    board.set(source, Piece(PieceType.ROOK, Color.WHITE))

    runner = bootstrap_gui(board=board)
    rt = runner._runtime
    for row in range(board.rows):
        for col in range(board.cols):
            piece = board.get(Position(row, col))
            if piece is not None:
                runner._animators[(row, col)] = runner._make_animator(piece)

    x1, y1 = _cell_to_px(source.row, source.col)
    x2, y2 = _cell_to_px(destination.row, destination.col)
    rt.controller.click(x1, y1)
    rt.controller.click(x2, y2)
    return runner, rt


class TestAnimatorRelocationOnMotionCompletion:
    def test_arriving_piece_enters_long_rest_not_a_fresh_idle(self):
        source, destination = Position(4, 4), Position(4, 6)
        runner, rt = _make_runner_with_move(source, destination)

        # drive the sim until the motion (2000ms) fully completes
        for _ in range(45):
            rt.engine.advance_time(50)
            motions = rt.arbiter.get_active_motions()
            runner._sync_animators(motions)
            runner._update_animators(50)

        dest_key = (destination.row, destination.col)
        source_key = (source.row, source.col)
        assert dest_key in runner._animators
        assert runner._animators[dest_key].current_state == AnimState.LONG_REST
        assert source_key not in runner._animators

    def test_rest_animation_eventually_returns_to_idle(self):
        source, destination = Position(4, 4), Position(4, 6)
        runner, rt = _make_runner_with_move(source, destination)

        for _ in range(120):  # well past motion (2000ms) + long_rest (~2000ms)
            rt.engine.advance_time(50)
            motions = rt.arbiter.get_active_motions()
            runner._sync_animators(motions)
            runner._update_animators(50)

        dest_key = (destination.row, destination.col)
        assert runner._animators[dest_key].current_state == AnimState.IDLE
