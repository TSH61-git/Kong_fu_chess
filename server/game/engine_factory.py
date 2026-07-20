# Factory — builds the chess_engine object graph for one match, replicating
# app_gateways/text_cli/bootstrap.py's wiring chain minus BoardMapper/Controller,
# which are pixel-click concerns a network gateway has no use for.
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from chess_engine.engine.game_engine import GameEngine
from chess_engine.model.board import Board
from chess_engine.model.board_factory import standard_board
from chess_engine.realtime.arbiter import RealTimeArbiter
from chess_engine.rules.engine import RuleEngine


@dataclass
class EngineStack:
    board: Board
    rule_engine: RuleEngine
    arbiter: RealTimeArbiter
    engine: GameEngine


def build_game_stack(board: Optional[Board] = None) -> EngineStack:
    resolved_board = board if board is not None else standard_board()
    rule_engine = RuleEngine()
    arbiter = RealTimeArbiter(board=resolved_board, game_engine=None)
    engine = GameEngine(board=resolved_board, rule_engine=rule_engine, arbiter=arbiter)
    arbiter.attach_game_engine(engine)
    return EngineStack(board=resolved_board, rule_engine=rule_engine, arbiter=arbiter, engine=engine)
