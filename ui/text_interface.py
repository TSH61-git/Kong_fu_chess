import sys
from core.board_parser import BoardParser
from core.game_service import GameService
from core.exceptions import BoardValidationError

class TextInterface:
    @classmethod
    def run(cls):
        input_text = sys.stdin.read().strip()
        if not input_text: 
            return

        board_lines = []
        in_board = False
        commands_lines = [] 

        for line in [l.strip() for l in input_text.splitlines()]:
            if line.startswith("Board:"):
                in_board = True
                continue
            elif line.startswith("Commands:"):
                in_board = False
                continue 
            
            if in_board and line:
                board_lines.append(line)
            elif not in_board and line:
                commands_lines.append(line)

        try:
            parsed_matrix = BoardParser.validate_and_parse(board_lines)
            
            game = GameService(parsed_matrix)
            
            for cmd in commands_lines:
                parts = cmd.split()
                if not parts:
                    continue
                
                cmd_type = parts[0]
                
                if cmd_type == "click":
                    x, y = int(parts[1]), int(parts[2])
                    game.handle_click(x, y)
                    
                elif cmd_type == "wait":
                    ms = int(parts[1])
                    game.handle_wait(ms)
                    
                elif cmd == "print board":
                    print("\n".join(game.get_board_lines()))
                    
        except BoardValidationError as e:
            print(e)