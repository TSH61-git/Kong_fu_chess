# Git Repository URL: https://github.com/TSH61-git/Kong_fu_chess
"""Console entry point for the refactored Kung Fu Chess application.

This module is the single orchestrator for the text-based execution flow.
It reads a board definition and a command stream from standard input,
constructs the production object graph, and emits board output to standard
output without invoking any graphical UI layer.
"""
from __future__ import annotations

import sys
from typing import List, Optional, Tuple

from engine.game_engine import GameEngine
from input.board_mapper import BoardMapper
from input.controller import Controller
from model.board import Board
from rules.rule_engine import RuleEngine
from realtime.real_time_arbiter import RealTimeArbiter
from text_io.board_parser import BoardParser
from text_io.board_printer import BoardPrinter


def _split_sections(raw_text: str) -> Tuple[List[str], List[str]]:
    """Split raw stdin text into board lines and command lines.

    The external input format is expected to contain a ``Board:`` section
    followed by a ``Commands:`` section. Blank lines are ignored.
    """
    board_lines: List[str] = []
    command_lines: List[str] = []
    current_section: Optional[str] = None

    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        lowered = line.lower()
        if lowered == "board:":
            current_section = "board"
            continue
        if lowered == "commands:":
            current_section = "commands"
            continue

        if current_section == "board":
            board_lines.append(line)
        elif current_section == "commands":
            command_lines.append(line)

    return board_lines, command_lines


def _parse_board(board_lines: List[str]) -> Optional[Board]:
    """Parse the board block and return a Board instance.

    Any parser failure is translated into the exact error token expected by
    the external integration tests, and None is returned for clean shutdown.
    """
    try:
        return BoardParser.parse(board_lines)
    except ValueError as exc:
        message = str(exc)
        if "Unknown token" in message:
            print("ERROR UNKNOWN_TOKEN")
        elif "Row width mismatch" in message:
            print("ERROR ROW_WIDTH_MISMATCH")
        else:
            print("ERROR UNKNOWN_TOKEN")
        return None


def _run_commands(
    board: Board,
    command_lines: List[str],
) -> None:
    """Execute the parsed command stream against the production object graph."""
    rule_engine = RuleEngine()
    arbiter = RealTimeArbiter(board=board, game_engine=None)
    game_engine = GameEngine(board=board, rule_engine=rule_engine, arbiter=arbiter)
    arbiter.attach_game_engine(game_engine)
    board_mapper = BoardMapper(board)
    controller = Controller(engine=game_engine, mapper=board_mapper, board=board)

    for raw_command in command_lines:
        parts = raw_command.split()
        if not parts:
            continue

        command = parts[0].lower()
        if command == "click" and len(parts) == 3:
            x = int(parts[1])
            y = int(parts[2])
            controller.click(x, y)
        elif command == "wait" and len(parts) == 2:
            game_engine.wait(int(parts[1]))
        elif command == "jump" and len(parts) == 3:
            x = int(parts[1])
            y = int(parts[2])
            pos = board_mapper.pixel_to_cell(x, y)
            if pos is not None:
                game_engine.request_jump(pos)
        elif command == "print" and len(parts) == 2 and parts[1].lower() == "board":
            for line in BoardPrinter.to_lines(board):
                print(line)


def main() -> None:
    """Serve as the console application's single entry point."""
    board_lines, command_lines = _split_sections(sys.stdin.read())
    board = _parse_board(board_lines)
    if board is None:
        return
    _run_commands(board, command_lines)


if __name__ == "__main__":
    main()
