from typing import List, Tuple

class MovementValidator:
    @classmethod
    def is_valid_move(cls, board: List[List[str]], piece: str, from_pos: Tuple[int, int], to_pos: Tuple[int, int]) -> bool:
        """
        מבצע בדיקה מקיפה: צורת כלי, חוסמים במסלול, ואכילה חוקית ביעד.
        piece: הטוקן המלא של הכלי הזז (למשל 'wR', 'bB')
        """
        r1, c1 = from_pos
        r2, c2 = to_pos
        
        if r1 == r2 and c1 == c2:
            return True
            
        target_token = board[r2][c2]
        
        # 1. בדיקת תא היעד : מניעת אכילת כלי מאותו צבע
        if target_token != '.' and target_token[0] == piece[0]:
            return False
            
        # חילוץ סוג הכלי בלבד
        piece_type = piece[1]
        dr = abs(r2 - r1)
        dc = abs(c2 - c1)

        if piece_type == 'P':
            # קביעת כיוון הצעד המותר בשורות: לבן זז למעלה (-1), שחור זז למטה (1)
            allowed_row_diff = -1 if piece[0] == 'w' else 1
            
            # בדיקה שהרגלי זז בדיוק שורה אחת ובכיוון הנכון
            if (r2 - r1) != allowed_row_diff:
                return False
                
            # מקרה א': תנועה ישר קדימה (עמודה לא משתנה) -> חייב משבצת ריקה
            if dc == 0:
                return target_token == '.'
                
            # מקרה ב': תנועה באלכסון (עמודה משתנה ב-1) -> חייב להיות שם כלי אויב
            elif dc == 1:
                return target_token != '.'
                
            # כל תנועה אחרת הצידה אסורה לרגלי
            return False

        # 2. בדיקת צורת הכלי הבסיסית (Shape)
        shape_valid = False
        if piece_type == 'K':    shape_valid = (max(dr, dc) == 1)
        elif piece_type == 'R':  shape_valid = (dr == 0 or dc == 0)
        elif piece_type == 'B':  shape_valid = (dr == dc)
        elif piece_type == 'Q':  shape_valid = (dr == 0 or dc == 0 or dr == dc)
        elif piece_type == 'N':  shape_valid = ((dr == 1 and dc == 2) or (dr == 2 and dc == 1))
        
        if not shape_valid:
            return False

        # 3. בדיקת מסלול וחוסמים : רלוונטי רק לצריח, רץ ומלכה
        if piece_type in ('R', 'B', 'Q'):
            # חישוב כיוון הצעד (-1, 0, או 1)
            step_r = 1 if r2 > r1 else (-1 if r2 < r1 else 0)
            step_c = 1 if c2 > c1 else (-1 if c2 < c1 else 0)
            
            curr_r = r1 + step_r
            curr_c = c1 + step_c
            
            # לולאה שצועדת בתוך המסלול עד שהיא מגיעה אל משבצת היעד
            while (curr_r, curr_c) != (r2, c2):
                if board[curr_r][curr_c] != '.':
                    return False  # נמצא חוסם בדרך!
                curr_r += step_r
                curr_c += step_c

        return True