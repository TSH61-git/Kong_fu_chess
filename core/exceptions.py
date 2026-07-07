class BoardValidationError(Exception):
    """שגיאת בסיס לכל שגיאות הולידציה של הלוח"""
    pass

class UnknownTokenError(BoardValidationError):
    def __str__(self):
        return "ERROR UNKNOWN_TOKEN"

class RowWidthMismatchError(BoardValidationError):
    def __str__(self):
        return "ERROR ROW_WIDTH_MISMATCH"