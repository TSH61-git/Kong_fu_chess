class MovementValidator:
    @classmethod
    def is_valid_move(cls, piece_type: str, from_pos: tuple, to_pos: tuple) -> bool:
        """
        בודק האם מהלך מחוקק לצורת הכלי.
        piece_type: סוג הכלי בלבד (K, R, B, Q, N) ללא הצבע.
        from_pos: (row, col) של נקודת המוצא
        to_pos: (row, col) של נקודת היעד
        """
        r1, c1 = from_pos
        r2, c2 = to_pos
        
        # אם השחקן לחץ על אותה משבצת, זה לא מהלך תנועה
        if r1 == r2 and c1 == c2:
            return True
            
        dr = abs(r2 - r1)
        dc = abs(c2 - c1)

        if piece_type == 'K':    # מלך: משבצת אחת לכל כיוון
            return max(dr, dc) == 1
            
        elif piece_type == 'R':  # צריח: רק בשורה או רק בעמודה
            return dr == 0 or dc == 0
            
        elif piece_type == 'B':  # רץ: באלכסון בלבד
            return dr == dc
            
        elif piece_type == 'Q':  # מלכה: שילוב של צריח ורץ
            return dr == 0 or dc == 0 or dr == dc
            
        elif piece_type == 'N':  # פרש: תנועת L (1 ו-2 או 2 ו-1)
            return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)
            
        return False