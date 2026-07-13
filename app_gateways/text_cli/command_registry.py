# O(1) command dispatch registry for the text CLI layer.
from __future__ import annotations
from typing import Callable, Dict, List


CommandFn = Callable[[List[str]], None]


def build_registry(controller, engine, mapper, board) -> Dict[str, CommandFn]:
    from app_gateways.text_cli.translator import board_to_token_lines

    def _click(args: List[str]) -> None:
        controller.click(int(args[0]), int(args[1]))

    def _wait(args: List[str]) -> None:
        engine.wait(int(args[0]))

    def _jump(args: List[str]) -> None:
        pos = mapper.pixel_to_cell(int(args[0]), int(args[1]))
        if pos is not None:
            engine.request_jump(pos)

    def _print(args: List[str]) -> None:
        if args and args[0].lower() == "board":
            for line in board_to_token_lines(board):
                print(line)

    return {"click": _click, "wait": _wait, "jump": _jump, "print": _print}
