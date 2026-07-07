import sys
from typing import Tuple, List
from core.game_service import GameService


class TextInterface:
    def __init__(self, game_service: GameService, command_lines: List[str]) -> None:
        self._game = game_service
        self._commands = command_lines

    def run(self) -> None:
        for cmd in self._commands:
            self._dispatch(cmd)

    # ------------------------------------------------------------------
    # Static factory helper — called by the Composition Root BEFORE the
    # object graph is assembled, so board lines can be parsed first.
    # ------------------------------------------------------------------

    @staticmethod
    def read_sections() -> Tuple[List[str], List[str]]:
        """
        Reads stdin once and splits it into (board_lines, command_lines).
        Returns two empty lists if stdin is empty.
        """
        raw = sys.stdin.read().strip()
        if not raw:
            return [], []

        board_lines: List[str] = []
        command_lines: List[str] = []
        in_board = False

        for line in (l.strip() for l in raw.splitlines()):
            if line.startswith('Board:'):
                in_board = True
            elif line.startswith('Commands:'):
                in_board = False
            elif in_board and line:
                board_lines.append(line)
            elif not in_board and line:
                command_lines.append(line)

        return board_lines, command_lines

    # ------------------------------------------------------------------

    def _dispatch(self, cmd: str) -> None:
        parts = cmd.split()
        if not parts:
            return

        cmd_type = parts[0]

        if cmd_type == 'click':
            self._game.handle_click(int(parts[1]), int(parts[2]))
        elif cmd_type == 'wait':
            self._game.handle_wait(int(parts[1]))
        elif cmd == 'print board':
            print('\n'.join(self._game.get_board_lines()))
