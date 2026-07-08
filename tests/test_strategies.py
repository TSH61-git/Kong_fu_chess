import pytest
from core.strategies.rook_strategy import RookStrategy
from core.strategies.bishop_strategy import BishopStrategy
from core.strategies.knight_strategy import KnightStrategy
from core.strategies.king_strategy import KingStrategy
from core.strategies.queen_strategy import QueenStrategy
from core.strategies.pawn_strategy import PawnStrategy


# Minimal helper: build an 8x8 empty board and place a single piece
def _board(piece: str, r: int, c: int, target: str = '.', tr: int = None, tc: int = None):
    b = [['.' for _ in range(8)] for _ in range(8)]
    b[r][c] = piece
    if tr is not None and tc is not None:
        b[tr][tc] = target
    return b


# ------------------------------------------------------------------ #
# Rook Strategy                                                       #
# ------------------------------------------------------------------ #

class TestRookStrategy:
    def setup_method(self):
        self.s = RookStrategy()

    def test_valid_horizontal(self):
        b = _board('wR', 0, 0)
        assert self.s.is_valid_move(b, 'wR', (0, 0), (0, 5)) is True

    def test_valid_vertical(self):
        b = _board('wR', 0, 0)
        assert self.s.is_valid_move(b, 'wR', (0, 0), (3, 0)) is True

    def test_invalid_diagonal(self):
        b = _board('wR', 0, 0)
        assert self.s.is_valid_move(b, 'wR', (0, 0), (2, 2)) is False

    def test_blocked_by_piece(self):
        b = _board('wR', 0, 0)
        b[0][2] = 'bP'
        assert self.s.is_valid_move(b, 'wR', (0, 0), (0, 5)) is False


# ------------------------------------------------------------------ #
# Bishop Strategy                                                     #
# ------------------------------------------------------------------ #

class TestBishopStrategy:
    def setup_method(self):
        self.s = BishopStrategy()

    def test_valid_diagonal(self):
        b = _board('wB', 1, 1)
        assert self.s.is_valid_move(b, 'wB', (1, 1), (4, 4)) is True

    def test_invalid_straight(self):
        b = _board('wB', 1, 1)
        assert self.s.is_valid_move(b, 'wB', (1, 1), (4, 1)) is False

    def test_invalid_asymmetric(self):
        b = _board('wB', 1, 1)
        assert self.s.is_valid_move(b, 'wB', (1, 1), (3, 4)) is False

    def test_blocked_by_piece(self):
        b = _board('wB', 1, 1)
        b[2][2] = 'bP'
        assert self.s.is_valid_move(b, 'wB', (1, 1), (4, 4)) is False


# ------------------------------------------------------------------ #
# Knight Strategy                                                     #
# ------------------------------------------------------------------ #

class TestKnightStrategy:
    def setup_method(self):
        self.s = KnightStrategy()

    def test_valid_l_shape_1_2(self):
        b = _board('wN', 0, 0)
        assert self.s.is_valid_move(b, 'wN', (0, 0), (1, 2)) is True

    def test_valid_l_shape_2_1(self):
        b = _board('wN', 0, 0)
        assert self.s.is_valid_move(b, 'wN', (0, 0), (2, 1)) is True

    def test_invalid_shape(self):
        b = _board('wN', 0, 0)
        assert self.s.is_valid_move(b, 'wN', (0, 0), (2, 2)) is False

    def test_jumps_over_pieces(self):
        b = _board('wN', 0, 0)
        b[0][1] = 'wP'
        b[1][0] = 'wP'
        assert self.s.is_valid_move(b, 'wN', (0, 0), (2, 1)) is True


# ------------------------------------------------------------------ #
# King Strategy                                                       #
# ------------------------------------------------------------------ #

class TestKingStrategy:
    def setup_method(self):
        self.s = KingStrategy()

    def test_valid_one_step_diagonal(self):
        b = _board('wK', 3, 3)
        assert self.s.is_valid_move(b, 'wK', (3, 3), (4, 4)) is True

    def test_valid_one_step_straight(self):
        b = _board('wK', 3, 3)
        assert self.s.is_valid_move(b, 'wK', (3, 3), (3, 4)) is True

    def test_invalid_two_steps(self):
        b = _board('wK', 3, 3)
        assert self.s.is_valid_move(b, 'wK', (3, 3), (5, 3)) is False

    def test_invalid_two_step_diagonal(self):
        b = _board('wK', 3, 3)
        assert self.s.is_valid_move(b, 'wK', (3, 3), (5, 5)) is False


# ------------------------------------------------------------------ #
# Queen Strategy                                                      #
# ------------------------------------------------------------------ #

class TestQueenStrategy:
    def setup_method(self):
        self.s = QueenStrategy()

    def test_valid_straight(self):
        b = _board('wQ', 0, 0)
        assert self.s.is_valid_move(b, 'wQ', (0, 0), (0, 4)) is True

    def test_valid_diagonal(self):
        b = _board('wQ', 0, 0)
        assert self.s.is_valid_move(b, 'wQ', (0, 0), (4, 4)) is True

    def test_invalid_shape(self):
        b = _board('wQ', 0, 0)
        assert self.s.is_valid_move(b, 'wQ', (0, 0), (1, 2)) is False

    def test_blocked_by_piece(self):
        b = _board('wQ', 0, 0)
        b[0][2] = 'bP'
        assert self.s.is_valid_move(b, 'wQ', (0, 0), (0, 4)) is False


# ------------------------------------------------------------------ #
# Pawn Strategy                                                       #
# ------------------------------------------------------------------ #

class TestPawnStrategy:
    def setup_method(self):
        self.s = PawnStrategy()

    def test_white_forward_single_step(self):
        b = _board('wP', 6, 0)
        assert self.s.is_valid_move(b, 'wP', (6, 0), (5, 0)) is True

    def test_white_backward_invalid(self):
        b = _board('wP', 6, 0)
        assert self.s.is_valid_move(b, 'wP', (6, 0), (7, 0)) is False

    def test_white_diagonal_capture(self):
        b = _board('wP', 6, 0, target='bR', tr=5, tc=1)
        assert self.s.is_valid_move(b, 'wP', (6, 0), (5, 1)) is True

    def test_white_diagonal_no_capture_on_empty(self):
        b = _board('wP', 6, 0)
        assert self.s.is_valid_move(b, 'wP', (6, 0), (5, 1)) is False

    def test_white_double_step_from_init_row(self):
        b = _board('wP', 6, 0)  # init row for white on 8-row board
        assert self.s.is_valid_move(b, 'wP', (6, 0), (4, 0)) is True

    def test_white_double_step_blocked_intermediate(self):
        b = _board('wP', 6, 0)
        b[5][0] = 'bP'  # block the intermediate cell
        assert self.s.is_valid_move(b, 'wP', (6, 0), (4, 0)) is False

    def test_white_double_step_not_from_init_row(self):
        b = _board('wP', 5, 0)  # not the init row
        assert self.s.is_valid_move(b, 'wP', (5, 0), (3, 0)) is False

    def test_black_forward_single_step(self):
        b = _board('bP', 1, 0)
        assert self.s.is_valid_move(b, 'bP', (1, 0), (2, 0)) is True

    def test_black_double_step_from_init_row(self):
        b = _board('bP', 1, 0)  # init row for black
        assert self.s.is_valid_move(b, 'bP', (1, 0), (3, 0)) is True

    def test_black_double_step_blocked_intermediate(self):
        b = _board('bP', 1, 0)
        b[2][0] = 'wP'
        assert self.s.is_valid_move(b, 'bP', (1, 0), (3, 0)) is False


# ------------------------------------------------------------------ #
# PawnStrategy.on_land — promotion hook                              #
# ------------------------------------------------------------------ #

class TestPawnOnLand:
    def setup_method(self):
        self.s = PawnStrategy()

    def test_white_promotes_on_row_0(self):
        b = _board('wP', 0, 3)
        assert self.s.on_land(b, 'wP', (0, 3)) == 'wQ'

    def test_black_promotes_on_last_row(self):
        b = _board('bP', 7, 3)
        assert self.s.on_land(b, 'bP', (7, 3)) == 'bQ'

    def test_no_promotion_mid_board(self):
        b = _board('wP', 4, 3)
        assert self.s.on_land(b, 'wP', (4, 3)) == 'wP'
