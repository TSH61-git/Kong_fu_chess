# Integration tests for the text-script DSL — typed stack, self-contained.
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

from app_gateways.text_cli.bootstrap import bootstrap_game_system
from app_gateways.text_cli.translator import board_from_token_lines, board_to_token_lines


@dataclass
class _ParsedScript:
    board_lines: List[str]
    commands: List[Tuple[str, List[str]]]
    expected_text: str


def _parse(path: Path) -> _ParsedScript:
    lines = path.read_text(encoding="utf-8").splitlines()
    board_lines, commands, expected, in_board = [], [], [], False
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line == "Board":
            in_board = True
        elif line.startswith(">"):
            expected.append(line[1:].strip())
        elif line in ("print board",) or line.startswith(("click", "wait", "jump")):
            in_board = False
            parts = line.split()
            commands.append(("print board" if line == "print board" else parts[0], parts[1:]))
        elif in_board:
            board_lines.append(line)
    return _ParsedScript(board_lines, commands, "\n".join(expected))


def _run(script_path: Path) -> str:
    parsed = _parse(script_path)
    board = board_from_token_lines(parsed.board_lines)
    runner = bootstrap_game_system(board=board)
    output: List[str] = []
    for command, args in parsed.commands:
        if command == "click":
            runner.controller.click(int(args[0]), int(args[1]))
        elif command == "wait":
            runner.engine.wait(int(args[0]))
        elif command == "print board":
            output.extend(board_to_token_lines(board))
    return "\n".join(output)


def test_all_kfc_scripts_match_expected_output():
    script_dir = Path(__file__).parent / "scripts"
    scripts = sorted(script_dir.glob("*.kfc"))
    assert scripts, "Expected at least one .kfc script"
    for script_path in scripts:
        assert _run(script_path) == _parse(script_path).expected_text
