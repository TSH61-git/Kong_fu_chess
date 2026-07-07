from typing import List, Tuple, Optional

class GameService:
    def __init__(self, board: List[List[str]]):
        self.board = board
        self.rows = len(board)
        self.cols = len(board[0]) if self.rows > 0 else 0
        self.selected_pos: Optional[Tuple[int, int]] = None  # שומר את (row, col) של הכלי הנבחר

    def handle_click(self, x: int, y: int):
        """ממיר קואורדינטות פיקסל למשבצת ומנהל את לוגיקת הבחירה/תנועה"""
        # המרה מפיקסלים לאינדקסים (כל משבצת היא 100x100)
        col = x // 100
        row = y // 100

        # טסט 3: לחיצה מחוץ לגבולות הלוח מנוטרלת לחלוטין
        if not (0 <= row < self.rows and 0 <= col < self.cols):
            return

        token = self.board[row][col]

        # אם אין כלי נבחר כרגע
        if self.selected_pos is None:
            if token != '.':  # לחצו על כלי כלשהו -> בוחרים אותו (טסט 1)
                self.selected_pos = (row, col)
            # אם לחצו על משבצת ריקה ואין בחירה -> מתעלמים (טסט 2)
            return

        # אם כבר יש כלי נבחר
        curr_row, curr_col = self.selected_pos
        selected_token = self.board[curr_row][curr_col]

        # בדיקה האם הכלי שנלחץ כעת שייך לאותו שחקן (friendly piece) לפי האות הראשונה (w/b)
        if token != '.' and token[0] == selected_token[0]:
            # טסט 4: החלפת הבחירה לכלי הידידותי החדש
            self.selected_pos = (row, col)
        else:
            # ביצוע התנועה/אכילה למשבצת החדשה
            self.board[row][col] = selected_token
            self.board[curr_row][curr_col] = '.'
            self.selected_pos = None  # איפוס הבחירה לאחר המהלך

    def handle_wait(self, ms: int):
        """מקדמת את שעון המשחק (בשלב זה אין לוגיקת זמן מורכבת, הפקודה פשוט מבוצעת)"""
        pass

    def get_board_lines(self) -> List[str]:
        """מחזירה את שורות הלוח הנוכחיות כרשימת מחרוזות"""
        return [" ".join(row) for row in self.board]