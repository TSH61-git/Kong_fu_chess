# Bootstrap factory — wires the typed chess_engine stack for the CLI gateway.
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional

from chess_engine.model.board import Board
from chess_engine.realtime.arbiter import RealTimeArbiter
from chess_engine.rules.engine import RuleEngine
from chess_engine.engine.game_engine import GameEngine
from chess_engine.input.board_mapper import BoardMapper
from chess_engine.input.controller import Controller


@dataclass
class GameRuntime:
    board: Board
    rule_engine: RuleEngine
    arbiter: RealTimeArbiter
    engine: GameEngine
    mapper: BoardMapper
    controller: Controller


def bootstrap_game_system(board: Optional[Board] = None):
    from app_gateways.text_cli.console_runner import ConsoleRunner

    resolved_board = board if board is not None else Board(rows=8, cols=8)
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
    return ConsoleRunner(runtime=runtime)
