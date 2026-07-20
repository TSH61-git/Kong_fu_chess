from server.rating.elo import expected_score, update_ratings


class TestExpectedScore:
    def test_equal_ratings_expect_an_even_split(self):
        assert expected_score(1200, 1200) == 0.5

    def test_higher_rating_is_favored(self):
        assert expected_score(1400, 1200) > 0.5
        assert expected_score(1200, 1400) < 0.5


class TestUpdateRatings:
    def test_equal_ratings_white_wins(self):
        new_white, new_black = update_ratings(1200, 1200, white_won=True)
        assert new_white == 1216  # 1200 + 32 * (1 - 0.5)
        assert new_black == 1184

    def test_equal_ratings_black_wins(self):
        new_white, new_black = update_ratings(1200, 1200, white_won=False)
        assert new_white == 1184
        assert new_black == 1216

    def test_equal_ratings_draw_is_a_no_op(self):
        new_white, new_black = update_ratings(1200, 1200, white_won=None)
        assert new_white == 1200
        assert new_black == 1200

    def test_favorite_gains_less_for_an_expected_win(self):
        # White (1400) beating black (1200) should gain less than the
        # equal-ratings case above, since the win was already expected.
        new_white, _ = update_ratings(1400, 1200, white_won=True)
        assert 0 < new_white - 1400 < 16

    def test_underdog_gains_more_for_an_upset_win(self):
        new_white, _ = update_ratings(1200, 1400, white_won=True)
        assert new_white - 1200 > 16

    def test_custom_k_factor_scales_the_change(self):
        new_white, _ = update_ratings(1200, 1200, white_won=True, k=16)
        assert new_white == 1208
