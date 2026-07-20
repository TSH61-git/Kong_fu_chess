from chess_engine.model.board_factory import standard_board
from chess_engine.model.piece import Color, PieceType
from chess_engine.model.position import Position


class TestStandardBoard:
    def test_dimensions(self):
        board = standard_board()
        assert board.rows == 8 and board.cols == 8

    def test_white_back_rank(self):
        board = standard_board()
        expected = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK,
        ]
        for col, piece_type in enumerate(expected):
            piece = board.get(Position(7, col))
            assert piece.piece_type == piece_type
            assert piece.color == Color.WHITE

    def test_black_back_rank(self):
        board = standard_board()
        expected = [
            PieceType.ROOK, PieceType.KNIGHT, PieceType.BISHOP, PieceType.QUEEN,
            PieceType.KING, PieceType.BISHOP, PieceType.KNIGHT, PieceType.ROOK,
        ]
        for col, piece_type in enumerate(expected):
            piece = board.get(Position(0, col))
            assert piece.piece_type == piece_type
            assert piece.color == Color.BLACK

    def test_pawn_rows(self):
        board = standard_board()
        for col in range(8):
            black_pawn = board.get(Position(1, col))
            white_pawn = board.get(Position(6, col))
            assert black_pawn.piece_type == PieceType.PAWN and black_pawn.color == Color.BLACK
            assert white_pawn.piece_type == PieceType.PAWN and white_pawn.color == Color.WHITE

    def test_middle_rows_empty(self):
        board = standard_board()
        for row in range(2, 6):
            for col in range(8):
                assert board.get(Position(row, col)) is None
