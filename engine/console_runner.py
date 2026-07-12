"""Console execution runner for the text-based application flow."""
from __future__ import annotations

import sys
from typing import List, Optional, Sequence, Tuple

from app_factory import GameRuntime
from model.board import Board
from text_io.board_parser import BoardParser
from text_io.board_printer import BoardPrinter


class ConsoleRunner:
    """Coordinate the console interaction loop for the game runtime."""

    def __init__(self, runtime: Optional[GameRuntime] = None) -> None:
        self._runtime = runtime

    @property
    def runtime(self) -> Optional[GameRuntime]:
        """Expose the underlying runtime container."""
        return self._runtime

    @property
    def board(self) -> Optional[Board]:
        """Expose the live board instance used by the runtime."""
        return None if self._runtime is None else self._runtime.board

    @property
    def engine(self):
        """Expose the application service instance."""
        return None if self._runtime is None else self._runtime.engine

    @property
    def arbiter(self):
        """Expose the real-time arbiter instance."""
        return None if self._runtime is None else self._runtime.arbiter

    @property
    def controller(self):
        """Expose the controller instance used for input dispatch."""
        return None if self._runtime is None else self._runtime.controller

    @property
    def mapper(self):
        """Expose the board coordinate mapper instance."""
        return None if self._runtime is None else self._runtime.mapper

    def run(self, raw_text: Optional[str] = None) -> None:
        """Parse and execute the command stream from the provided text."""
        text = raw_text if raw_text is not None else sys.stdin.read()
        board_lines, command_lines = self._split_sections(text)
        board = self._parse_board(board_lines)
        if board is None:
            return

        from app_factory import bootstrap_game_system

        self._runtime = bootstrap_game_system(board=board).runtime
        self._run_commands(command_lines)

    def _split_sections(self, raw_text: str) -> Tuple[List[str], List[str]]:
        """Split the textual input into board and command sections."""
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

    def _parse_board(self, board_lines: Sequence[str]) -> Optional[Board]:
        """Parse a board definition and return the resulting board object."""
        try:
            return BoardParser.parse(list(board_lines))
        except ValueError as exc:
            message = str(exc)
            if "Unknown token" in message:
                print("ERROR UNKNOWN_TOKEN")
            elif "Row width mismatch" in message:
                print("ERROR ROW_WIDTH_MISMATCH")
            else:
                print("ERROR UNKNOWN_TOKEN")
            return None

    def _run_commands(self, command_lines: Sequence[str]) -> None:
        """Execute the parsed command stream against the runtime."""
        if self._runtime is None:
            return

        for raw_command in command_lines:
            parts = raw_command.split()
            if not parts:
                continue

            command = parts[0].lower()
            if command == "click" and len(parts) == 3:
                x = int(parts[1])
                y = int(parts[2])
                self.controller.click(x, y)
            elif command == "wait" and len(parts) == 2:
                self.engine.wait(int(parts[1]))
            elif command == "jump" and len(parts) == 3:
                x = int(parts[1])
                y = int(parts[2])
                pos = self.mapper.pixel_to_cell(x, y)
                if pos is not None:
                    self.engine.request_jump(pos)
            elif command == "print" and len(parts) == 2 and parts[1].lower() == "board":
                for line in BoardPrinter.to_lines(self.board):
                    print(line)
