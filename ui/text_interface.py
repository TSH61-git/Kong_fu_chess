import sys
from core.board_parser import BoardParser
from core.exceptions import BoardValidationError

class TextInterface:
    @classmethod
    def run(cls):
        input_text = sys.stdin.read().strip()
        if not input_text: 
            return

        board_lines = []
        in_board = False
        print_board_command = False

        for line in [l.strip() for l in input_text.splitlines()]:
            if line.startswith("Board:"):
                in_board = True
                continue
            elif line.startswith("Commands:"):
                in_board = False
            
            if in_board and line:
                board_lines.append(line)
            elif not in_board and "print board" in line:
                print_board_command = True

        try:
            parsed_board = BoardParser.validate_and_parse(board_lines)
            if print_board_command:
                print(BoardParser.to_string(parsed_board))
        except BoardValidationError as e:
            print(e)