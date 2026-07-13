# Console runner for the text CLI gateway — uses the command registry.
from __future__ import annotations
import sys
from typing import List, Optional, Sequence, Tuple

from app_gateways.text_cli.translator import board_from_token_lines
from app_gateways.text_cli.command_registry import build_registry


class ConsoleRunner:

    def __init__(self, runtime=None) -> None:
        self._runtime = runtime

    @property
    def runtime(self):
        return self._runtime

    @property
    def board(self):
        return None if self._runtime is None else self._runtime.board

    @property
    def engine(self):
        return None if self._runtime is None else self._runtime.engine

    @property
    def arbiter(self):
        return None if self._runtime is None else self._runtime.arbiter

    @property
    def controller(self):
        return None if self._runtime is None else self._runtime.controller

    @property
    def mapper(self):
        return None if self._runtime is None else self._runtime.mapper

    def run(self, raw_text: Optional[str] = None) -> None:
        text = raw_text if raw_text is not None else sys.stdin.read()
        board_lines, command_lines = self._split_sections(text)
        board = self._parse_board(board_lines)
        if board is None:
            return

        from app_gateways.text_cli.bootstrap import bootstrap_game_system
        self._runtime = bootstrap_game_system(board=board).runtime
        self._run_commands(command_lines)

    def _split_sections(self, raw_text: str) -> Tuple[List[str], List[str]]:
        board_lines: List[str] = []
        command_lines: List[str] = []
        section: Optional[str] = None
        for raw_line in raw_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            low = line.lower()
            if low == "board:":
                section = "board"
            elif low == "commands:":
                section = "commands"
            elif section == "board":
                board_lines.append(line)
            elif section == "commands":
                command_lines.append(line)
        return board_lines, command_lines

    def _parse_board(self, board_lines: Sequence[str]):
        try:
            return board_from_token_lines(list(board_lines))
        except ValueError as exc:
            msg = str(exc)
            print("ERROR ROW_WIDTH_MISMATCH" if "mismatch" in msg else "ERROR UNKNOWN_TOKEN")
            return None

    def _run_commands(self, command_lines: Sequence[str]) -> None:
        if self._runtime is None:
            return
        registry = build_registry(
            self.controller, self.engine, self.mapper, self.board
        )
        for raw in command_lines:
            parts = raw.split()
            if not parts:
                continue
            cmd = parts[0].lower()
            fn = registry.get(cmd)
            if fn is not None:
                fn(parts[1:])
