"""
Unit tests for rules/promotion_rules.py — Pawn promotion evaluation layer.

This test module validates the stateless promotion logic that determines
whether a piece should transform upon reaching a promotion row.

Test organization:
  - White pawn promotion scenarios (all rows)
  - Black pawn promotion scenarios (all rows)
  - Non-promoting pieces across all rows and colors
  - Edge cases (unknown pieces, boundary conditions)

All tests verify that the promotion registry correctly dispatches piece types
to their corresponding promotion functions and returns the expected transformed
or unchanged piece types.
"""
import pytest
from rules.promotion_rules import get_promoted_token


# ================================================================== #
# White Pawn Promotion Tests                                          #
# ================================================================== #

class TestWhitePawnPromotion:
    """Test suite for white pawn promotion behavior."""

    def test_white_pawn_promotion_at_rank_zero(self):
        """
        Verify that a white pawn reaching row 0 (promotion rank) transforms to Queen.
        
        White pawns move toward row 0 and promote upon arrival.
        This test confirms the transformation from 'P' to 'Q' at the
        promotion threshold.
        """
        result = get_promoted_token(
            piece_type="P",
            current_row=0,
            max_rows=8,
            color="w"
        )
        assert result == "Q"

    def test_white_pawn_no_promotion_one_rank_from_end(self):
        """
        Verify that a white pawn on row 1 (one rank before promotion) does not promote.
        
        Pawn promotion occurs only at the exact promotion row (row 0 for white).
        This test ensures premature promotion does not occur.
        """
        result = get_promoted_token(
            piece_type="P",
            current_row=1,
            max_rows=8,
            color="w"
        )
        assert result == "P"

    def test_white_pawn_no_promotion_in_middle_ranks(self):
        """
        Verify that a white pawn on intermediate rows (3, 4) remains unchanged.
        
        Promotion is exclusively triggered at the rank-zero threshold.
        This test confirms no unexpected transformations occur during travel.
        """
        for middle_row in [2, 3, 4, 5, 6]:
            result = get_promoted_token(
                piece_type="P",
                current_row=middle_row,
                max_rows=8,
                color="w"
            )
            assert result == "P", f"Pawn at row {middle_row} should not promote"

    def test_white_pawn_no_promotion_at_start_row(self):
        """
        Verify that a white pawn at its starting row (row 6 on an 8×8 board) does not promote.
        
        White pawns begin at row 6 on a standard board and require full traverse
        to row 0 for promotion.
        """
        result = get_promoted_token(
            piece_type="P",
            current_row=6,
            max_rows=8,
            color="w"
        )
        assert result == "P"


# ================================================================== #
# Black Pawn Promotion Tests                                          #
# ================================================================== #

class TestBlackPawnPromotion:
    """Test suite for black pawn promotion behavior."""

    def test_black_pawn_promotion_at_back_rank(self):
        """
        Verify that a black pawn reaching row 7 (the back rank on an 8×8 board) transforms to Queen.
        
        Black pawns move toward the final row (max_rows - 1) and promote upon arrival.
        This test confirms the transformation from 'P' to 'Q' at the black promotion threshold.
        """
        result = get_promoted_token(
            piece_type="P",
            current_row=7,
            max_rows=8,
            color="b"
        )
        assert result == "Q"

    def test_black_pawn_no_promotion_one_rank_from_end(self):
        """
        Verify that a black pawn on row 6 (one rank before promotion) does not promote.
        
        Pawn promotion occurs only at the exact promotion row (row max_rows-1 for black).
        This test ensures premature promotion does not occur.
        """
        result = get_promoted_token(
            piece_type="P",
            current_row=6,
            max_rows=8,
            color="b"
        )
        assert result == "P"

    def test_black_pawn_no_promotion_in_middle_ranks(self):
        """
        Verify that a black pawn on intermediate rows (2, 3, 4) remains unchanged.
        
        Promotion is exclusively triggered at the back-rank threshold.
        This test confirms no unexpected transformations occur during travel.
        """
        for middle_row in [1, 2, 3, 4, 5]:
            result = get_promoted_token(
                piece_type="P",
                current_row=middle_row,
                max_rows=8,
                color="b"
            )
            assert result == "P", f"Black pawn at row {middle_row} should not promote"

    def test_black_pawn_no_promotion_at_start_row(self):
        """
        Verify that a black pawn at its starting row (row 1 on an 8×8 board) does not promote.
        
        Black pawns begin at row 1 on a standard board and require full traverse
        to row 7 for promotion.
        """
        result = get_promoted_token(
            piece_type="P",
            current_row=1,
            max_rows=8,
            color="b"
        )
        assert result == "P"


# ================================================================== #
# Non-Promoting Pieces Tests                                          #
# ================================================================== #

class TestNonPromotingPieces:
    """Test suite for pieces that never transform regardless of position."""

    def test_rook_never_promotes(self):
        """
        Verify that Rooks return 'R' across all promotion rows and colors.
        
        Rooks are powerful pieces that do not participate in the promotion
        mechanic and remain unchanged regardless of their position.
        """
        for row in [0, 3, 7]:
            for color in ["w", "b"]:
                result = get_promoted_token(
                    piece_type="R",
                    current_row=row,
                    max_rows=8,
                    color=color
                )
                assert result == "R", \
                    f"Rook at row {row} (color {color}) should not promote"

    def test_bishop_never_promotes(self):
        """
        Verify that Bishops return 'B' across all promotion rows and colors.
        
        Bishops are powerful pieces that do not participate in the promotion
        mechanic and remain unchanged regardless of their position.
        """
        for row in [0, 3, 7]:
            for color in ["w", "b"]:
                result = get_promoted_token(
                    piece_type="B",
                    current_row=row,
                    max_rows=8,
                    color=color
                )
                assert result == "B", \
                    f"Bishop at row {row} (color {color}) should not promote"

    def test_knight_never_promotes(self):
        """
        Verify that Knights return 'N' across all promotion rows and colors.
        
        Knights are powerful pieces that do not participate in the promotion
        mechanic and remain unchanged regardless of their position.
        """
        for row in [0, 3, 7]:
            for color in ["w", "b"]:
                result = get_promoted_token(
                    piece_type="N",
                    current_row=row,
                    max_rows=8,
                    color=color
                )
                assert result == "N", \
                    f"Knight at row {row} (color {color}) should not promote"

    def test_queen_never_promotes(self):
        """
        Verify that Queens return 'Q' across all promotion rows and colors.
        
        Queens are the most powerful piece and do not participate in promotion;
        they remain unchanged regardless of position.
        """
        for row in [0, 3, 7]:
            for color in ["w", "b"]:
                result = get_promoted_token(
                    piece_type="Q",
                    current_row=row,
                    max_rows=8,
                    color=color
                )
                assert result == "Q", \
                    f"Queen at row {row} (color {color}) should not promote"

    def test_king_never_promotes(self):
        """
        Verify that Kings return 'K' across all promotion rows and colors.
        
        Kings are the most precious piece and do not participate in promotion;
        they remain unchanged regardless of position.
        """
        for row in [0, 3, 7]:
            for color in ["w", "b"]:
                result = get_promoted_token(
                    piece_type="K",
                    current_row=row,
                    max_rows=8,
                    color=color
                )
                assert result == "K", \
                    f"King at row {row} (color {color}) should not promote"

    def test_all_pieces_promotion_matrix(self):
        """
        Comprehensive matrix test: verify all piece types across all rows return correctly.
        
        This parameterized test exercises the complete promotion registry by testing
        each piece type ('P', 'R', 'B', 'N', 'Q', 'K') at critical rows (promotion rows
        and intermediate rows) for both colors.
        """
        pieces_and_expected = {
            "P": "P",  # Pawns are tested separately; here we verify non-promotion rows
            "R": "R",
            "B": "B",
            "N": "N",
            "Q": "Q",
            "K": "K",
        }
        critical_rows = [0, 1, 3, 6, 7]

        for piece_type, expected in pieces_and_expected.items():
            for row in critical_rows:
                for color in ["w", "b"]:
                    # Skip pawn promotion rows (they have special logic)
                    if piece_type == "P":
                        white_promo_row = 0
                        black_promo_row = 7
                        if (color == "w" and row == white_promo_row) or \
                           (color == "b" and row == black_promo_row):
                            continue  # Skip; tested in dedicated pawn tests

                    result = get_promoted_token(
                        piece_type=piece_type,
                        current_row=row,
                        max_rows=8,
                        color=color
                    )
                    assert result == expected, \
                        f"{piece_type} at row {row} (color {color}) returned {result}, expected {expected}"


# ================================================================== #
# Edge Cases and Boundary Conditions                                  #
# ================================================================== #

class TestEdgeCases:
    """Test suite for edge cases and boundary conditions."""

    def test_pawn_promotion_on_different_board_sizes(self):
        """
        Verify that pawn promotion thresholds adjust correctly for non-standard board sizes.
        
        This test confirms that the promotion module correctly calculates the
        promotion row as max_rows - 1 for black pawns on boards of varying sizes.
        """
        # 10×10 board
        result_white = get_promoted_token("P", current_row=0, max_rows=10, color="w")
        result_black = get_promoted_token("P", current_row=9, max_rows=10, color="b")
        assert result_white == "Q"
        assert result_black == "Q"

        # 6×6 board
        result_white = get_promoted_token("P", current_row=0, max_rows=6, color="w")
        result_black = get_promoted_token("P", current_row=5, max_rows=6, color="b")
        assert result_white == "Q"
        assert result_black == "Q"

    def test_pawn_no_promotion_adjacent_to_threshold(self):
        """
        Verify strict boundary checking: pawns one row away from promotion do not promote.
        
        This test confirms that promotion is exclusive to the exact threshold row
        and does not occur at adjacent rows, preventing off-by-one errors.
        """
        # White pawn at row 1 (one away from promotion at row 0)
        result = get_promoted_token("P", current_row=1, max_rows=8, color="w")
        assert result == "P"

        # Black pawn at row 6 (one away from promotion at row 7)
        result = get_promoted_token("P", current_row=6, max_rows=8, color="b")
        assert result == "P"

    def test_unknown_piece_type_returns_original(self):
        """
        Verify that unknown piece types return their original character unchanged.
        
        This defensive behavior ensures that the promotion module gracefully
        handles unexpected input without raising exceptions or returning null.
        """
        result = get_promoted_token(
            piece_type="X",
            current_row=0,
            max_rows=8,
            color="w"
        )
        assert result == "X"

    def test_promotion_is_stateless(self):
        """
        Verify that multiple consecutive calls return consistent results.
        
        The promotion module is stateless; repeated calls with identical
        arguments must produce identical results (idempotency).
        """
        args = {"piece_type": "P", "current_row": 0, "max_rows": 8, "color": "w"}
        result1 = get_promoted_token(**args)
        result2 = get_promoted_token(**args)
        result3 = get_promoted_token(**args)
        assert result1 == result2 == result3 == "Q"
