"""Parser for the text integration DSL used by .kfc scripts."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple


@dataclass
class ParsedScript:
    """Structured representation of a parsed .kfc script."""

    board_lines: List[str]
    commands: List[Tuple[str, List[str]]]
    expected_text: str


class ScriptParser:
    """Parse a .kfc script into board setup, commands, and expected output."""

    @staticmethod
    def parse(path: Path) -> ParsedScript:
        """Parse a script file into a structured representation."""
        lines = [line.rstrip("\n") for line in path.read_text(encoding="utf-8").splitlines()]
        board_lines: List[str] = []
        commands: List[Tuple[str, List[str]]] = []
        expected_lines: List[str] = []
        in_board = False
        expect_output = False

        for raw_line in lines:
            line = raw_line.strip()
            if not line:
                continue
            if line == "Board":
                in_board = True
                continue
            if line.startswith(">"):
                expected_lines.append(line[1:].strip())
                expect_output = True
                continue
            if line.startswith("click"):
                in_board = False
                expect_output = False
                parts = line.split()
                commands.append((parts[0], parts[1:]))
                continue
            if line.startswith("wait"):
                in_board = False
                expect_output = False
                parts = line.split()
                commands.append((parts[0], parts[1:]))
                continue
            if line == "print board":
                in_board = False
                expect_output = True
                commands.append(("print board", []))
                continue
            if in_board:
                board_lines.append(line)
                continue
            if expect_output:
                expected_lines.append(line)

        return ParsedScript(
            board_lines=board_lines,
            commands=commands,
            expected_text="\n".join(expected_lines),
        )
