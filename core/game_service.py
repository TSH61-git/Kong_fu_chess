from typing import List, Tuple, Optional
from core.movement_validator import MovementValidator

class GameService:
    def __init__(self, board: List[List[str]]):
        self.board = board
        self.rows = len(board)
        self.cols = len(board[0]) if self.rows > 0 else 0
        self.selected_pos: Optional[Tuple[int, int]] = None

    def handle_click(self, x: int, y: int):
        """ממיר קואורדינטות פיקסל למשבצת ומנהל את לוגיקת הבחירה/תנועה"""
        col = x // 100
        row = y // 100

        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return

        token = self.board[row][col]

        if self.selected_pos is None:
            if token != '.': 
                self.selected_pos = (row, col)
            return

        curr_row, curr_col = self.selected_pos
        selected_token = self.board[curr_row][curr_col]

        if token != '.' and token[0] == selected_token[0]:
            self.selected_pos = (row, col)
        else:
            if MovementValidator.is_valid_move(self.board, selected_token, (curr_row, curr_col), (row, col)):
                self.board[row][col] = selected_token
                self.board[curr_row][curr_col] = '.'
            
            self.selected_pos = None

    def handle_wait(self, ms: int):
        """מקדמת את שעון המשחק (בשלב זה אין לוגיקת זמן מורכבת, הפקודה פשוט מבוצעת)"""
        pass

    def get_board_lines(self) -> List[str]:
        """מחזירה את שורות הלוח הנוכחיות כרשימת מחרוזות"""
        return [" ".join(row) for row in self.board]