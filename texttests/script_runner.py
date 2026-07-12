"""Execution harness for the text integration DSL."""
from __future__ import annotations

from pathlib import Path
from typing import List

from engine.game_engine import GameEngine
from input.board_mapper import BoardMapper
from input.controller import Controller
from model.board import Board
from model.position import Position
from rules.rule_engine import RuleEngine
from realtime.real_time_arbiter import RealTimeArbiter
from text_io.board_parser import BoardParser
from text_io.board_printer import BoardPrinter
from texttests.script_parser import ScriptParser


class ScriptRunner:
    """Instantiate a fresh engine graph for each script and execute its commands."""

    def run_script(self, path: Path | str) -> str:
        """Execute the script and return the full expected textual output."""
        script_path = Path(path)
        parsed = ScriptParser.parse(script_path)
        board = BoardParser.parse(parsed.board_lines)
        arbiter = RealTimeArbiter(board=board, game_engine=None)
        engine = GameEngine(board=board, rule_engine=RuleEngine(), arbiter=arbiter)
        arbiter.attach_game_engine(engine)
        mapper = BoardMapper(board)
        controller = Controller(engine=engine, mapper=mapper, board=board)

        output_lines: List[str] = []
        for command, args in parsed.commands:
            if command == "click":
                x = int(args[0])
                y = int(args[1])
                controller.click(x, y)
            elif command == "wait":
                engine.wait(int(args[0]))
            elif command == "print board":
                output_lines.extend(BoardPrinter.to_lines(board))

        return "\n".join(output_lines)
