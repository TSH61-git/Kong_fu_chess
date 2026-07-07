from typing import List
from core.exceptions import UnknownTokenError, RowWidthMismatchError

class BoardParser:
    VALID_TOKENS = {'wK', 'bK', 'wR', 'bR', 'wQ', 'bQ', 'wN', 'bN', 'wP', 'bP', '.'}

    @classmethod
    def validate_and_parse(cls, board_lines: List[str]) -> List[List[str]]:
        """
        מקבל רשימת שורות טקסט, מוודא תקינות ומחזיר מטריצה של הלוח.
        """
        parsed_board = []
        expected_width = None
        
        for line in board_lines:
            tokens = line.split()
            if not tokens: 
                continue
            
            # טסט 5: בדיקת אחידות אורך השורות
            if expected_width is None: 
                expected_width = len(tokens)
            elif len(tokens) != expected_width: 
                raise RowWidthMismatchError()
            
            # טסט 4: בדיקת טוקנים חוקיים
            if any(t not in cls.VALID_TOKENS for t in tokens): 
                raise UnknownTokenError()
            
            parsed_board.append(tokens)
            
        return parsed_board

    @classmethod
    def to_string(cls, board: List[List[str]]) -> str:
        """הופך את המטריצה חזרה לטקסט לצורך הדפסה"""
        return "\n".join(" ".join(row) for row in board)