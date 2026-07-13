import pytest
from chess_engine.model.piece import Piece, PieceType, Color
from chess_engine.realtime.arbiter import _promoted


class TestWhitePawnPromotion:
    def test_promotes_at_rank_zero(self):
        p = Piece(PieceType.PAWN, Color.WHITE)
        assert _promoted(p, 0, 8).piece_type == PieceType.QUEEN

    def test_no_promotion_one_rank_from_end(self):
        p = Piece(PieceType.PAWN, Color.WHITE)
        assert _promoted(p, 1, 8).piece_type == PieceType.PAWN

    def test_no_promotion_in_middle_ranks(self):
        p = Piece(PieceType.PAWN, Color.WHITE)
        for row in [2, 3, 4, 5, 6]:
            assert _promoted(p, row, 8).piece_type == PieceType.PAWN

    def test_no_promotion_at_start_row(self):
        p = Piece(PieceType.PAWN, Color.WHITE)
        assert _promoted(p, 6, 8).piece_type == PieceType.PAWN


class TestBlackPawnPromotion:
    def test_promotes_at_back_rank(self):
        p = Piece(PieceType.PAWN, Color.BLACK)
        assert _promoted(p, 7, 8).piece_type == PieceType.QUEEN

    def test_no_promotion_one_rank_from_end(self):
        p = Piece(PieceType.PAWN, Color.BLACK)
        assert _promoted(p, 6, 8).piece_type == PieceType.PAWN

    def test_no_promotion_in_middle_ranks(self):
        p = Piece(PieceType.PAWN, Color.BLACK)
        for row in [1, 2, 3, 4, 5]:
            assert _promoted(p, row, 8).piece_type == PieceType.PAWN

    def test_no_promotion_at_start_row(self):
        p = Piece(PieceType.PAWN, Color.BLACK)
        assert _promoted(p, 1, 8).piece_type == PieceType.PAWN


class TestNonPromotingPieces:
    @pytest.mark.parametrize("pt", [
        PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT,
        PieceType.QUEEN, PieceType.KING,
    ])
    def test_non_pawn_never_promotes(self, pt):
        for color in [Color.WHITE, Color.BLACK]:
            for row in [0, 3, 7]:
                p = Piece(pt, color)
                assert _promoted(p, row, 8).piece_type == pt


class TestEdgeCases:
    def test_promotion_on_different_board_sizes(self):
        assert _promoted(Piece(PieceType.PAWN, Color.WHITE), 0, 10).piece_type == PieceType.QUEEN
        assert _promoted(Piece(PieceType.PAWN, Color.BLACK), 9, 10).piece_type == PieceType.QUEEN
        assert _promoted(Piece(PieceType.PAWN, Color.WHITE), 0, 6).piece_type == PieceType.QUEEN
        assert _promoted(Piece(PieceType.PAWN, Color.BLACK), 5, 6).piece_type == PieceType.QUEEN

    def test_no_promotion_adjacent_to_threshold(self):
        assert _promoted(Piece(PieceType.PAWN, Color.WHITE), 1, 8).piece_type == PieceType.PAWN
        assert _promoted(Piece(PieceType.PAWN, Color.BLACK), 6, 8).piece_type == PieceType.PAWN

    def test_promotion_is_stateless(self):
        p = Piece(PieceType.PAWN, Color.WHITE)
        r1 = _promoted(p, 0, 8)
        r2 = _promoted(p, 0, 8)
        assert r1.piece_type == r2.piece_type == PieceType.QUEEN
