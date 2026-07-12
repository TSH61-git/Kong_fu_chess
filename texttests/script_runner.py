"""Execution harness for the text integration DSL."""
from __future__ import annotations

from pathlib import Path
from typing import List

from app_factory import bootstrap_game_system
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
        runner = bootstrap_game_system(board=board)

        output_lines: List[str] = []
        for command, args in parsed.commands:
            if command == "click":
                x = int(args[0])
                y = int(args[1])
                runner.controller.click(x, y)
            elif command == "wait":
                runner.engine.wait(int(args[0]))
            elif command == "print board":
                output_lines.extend(BoardPrinter.to_lines(board))

        return "\n".join(output_lines)
