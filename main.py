# Git Repository URL: https://github.com/TSH61-git/Kong_fu_chess

from ui.text_interface import TextInterface
from core.board_parser import BoardParser
from core.strategies import build_default_registry
from core.movement_validator import MovementValidator
from core.game_service import GameService
from core.game_clock import GameClock
from core.exceptions import BoardValidationError


def main() -> None:
    board_lines, command_lines = TextInterface.read_sections()

    registry  = build_default_registry()

    # Build allowed tokens dynamically from registry: both colors × each piece type + empty
    from core.constants import WHITE_COLOR, BLACK_COLOR, EMPTY_CELL
    allowed = {
        color + ptype
        for ptype in registry
        for color in (WHITE_COLOR, BLACK_COLOR)
    } | {EMPTY_CELL}

    try:
        board_matrix = BoardParser.validate_and_parse(board_lines, allowed)
    except BoardValidationError as e:
        print(e)
        return

    validator = MovementValidator(registry)
    clock     = GameClock()
    game      = GameService(board_matrix, validator, clock, registry)
    interface = TextInterface(game, command_lines)

    interface.run()


if __name__ == '__main__':
    main()
