from chess_engine.engine.game_engine import GameEngine
from chess_engine.model.board import Board
from chess_engine.model.piece import Color, PieceType
from chess_engine.model.position import Position
from chess_engine.realtime.arbiter import RealTimeArbiter
from chess_engine.rules.engine import RuleEngine

from server.game.engine_factory import build_game_stack


class TestBuildGameStack:
    def test_returns_a_fully_wired_stack(self):
        stack = build_game_stack()
        assert isinstance(stack.rule_engine, RuleEngine)
        assert isinstance(stack.arbiter, RealTimeArbiter)
        assert isinstance(stack.engine, GameEngine)

    def test_default_board_is_the_standard_starting_position(self):
        stack = build_game_stack()
        white_king = stack.board.get(Position(7, 4))
        assert white_king.piece_type == PieceType.KING
        assert white_king.color == Color.WHITE

    def test_arbiter_is_attached_to_the_engine(self):
        stack = build_game_stack()
        assert stack.arbiter.game_engine is stack.engine

    def test_accepts_a_custom_board(self):
        custom_board = Board(rows=8, cols=8)
        stack = build_game_stack(board=custom_board)
        assert stack.board is custom_board
