"""Application bootstrapper for the Kong Fu Chess runtime."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from engine.game_engine import GameEngine
from input.board_mapper import BoardMapper
from input.controller import Controller
from model.board import Board
from realtime.real_time_arbiter import RealTimeArbiter
from rules.rule_engine import RuleEngine

if TYPE_CHECKING:
    from engine.console_runner import ConsoleRunner


@dataclass
class GameRuntime:
    """Container for the core runtime object graph used by console and test flows."""

    board: Board
    rule_engine: RuleEngine
    arbiter: RealTimeArbiter
    engine: GameEngine
    mapper: BoardMapper
    controller: Controller


def bootstrap_game_system(board: Optional[Board] = None):
    """Construct and wire the standard game runtime for console and test usage."""
    from engine.console_runner import ConsoleRunner

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
