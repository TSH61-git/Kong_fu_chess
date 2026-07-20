from __future__ import annotations
from chess_engine.model.board import Board
from chess_engine.realtime.arbiter import RealTimeArbiter
from chess_engine.rules.engine import RuleEngine
from chess_engine.engine.game_engine import GameEngine
from chess_engine.input.board_mapper import BoardMapper
from chess_engine.input.controller import Controller
from app_gateways.text_cli.bootstrap import GameRuntime
from chess_engine.model.board_factory import standard_board


def bootstrap_gui(board: Board | None = None):
    from app_gateways.gui.gui_runner import GuiRunner

    resolved_board = board if board is not None else standard_board()
    rule_engine = RuleEngine()
    arbiter = RealTimeArbiter(board=resolved_board, game_engine=None)
    engine = GameEngine(board=resolved_board, rule_engine=rule_engine, arbiter=arbiter)
    arbiter.attach_game_engine(engine)
    mapper = BoardMapper(resolved_board)
    controller = Controller(engine=engine, mapper=mapper, board=resolved_board)
    runtime = GameRuntime(
        board=resolved_board,
        rule_engine=rule_engine,
        arbiter=arbiter,
        engine=engine,
        mapper=mapper,
        controller=controller,
    )
    return GuiRunner(runtime=runtime)
