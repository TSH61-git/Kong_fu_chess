import pytest
from core.strategies.rook_strategy import RookStrategy
from core.strategies.bishop_strategy import BishopStrategy
from core.strategies.knight_strategy import KnightStrategy
from core.strategies.king_strategy import KingStrategy
from core.strategies.queen_strategy import QueenStrategy
from core.strategies.pawn_strategy import PawnStrategy

# ------------------------------------------------------------------ #
# Rook Strategy Tests                                                 #
# ------------------------------------------------------------------ #

def test_rook_shape_validation():
    strategy = RookStrategy()
    # Valid: straight moves (one delta is 0)
    assert strategy.is_shape_valid(0, 5) is True
    assert strategy.is_shape_valid(3, 0) is True
    # Invalid: diagonal or non-straight moves
    assert strategy.is_shape_valid(2, 2) is False


# ------------------------------------------------------------------ #
# Bishop Strategy Tests                                               #
# ------------------------------------------------------------------ #

def test_bishop_shape_validation():
    strategy = BishopStrategy()
    # Valid: diagonal moves (dr == dc)
    assert strategy.is_shape_valid(3, 3) is True
    assert strategy.is_shape_valid(1, 1) is True
    # Invalid: straight or asymmetric moves
    assert strategy.is_shape_valid(0, 3) is False
    assert strategy.is_shape_valid(2, 3) is False


# ------------------------------------------------------------------ #
# Knight Strategy Tests                                               #
# ------------------------------------------------------------------ #

def test_knight_shape_validation():
    strategy = KnightStrategy()
    # Valid: L-shapes (1 and 2, or 2 and 1)
    assert strategy.is_shape_valid(1, 2) is True
    assert strategy.is_shape_valid(2, 1) is True
    # Invalid: other movements
    assert strategy.is_shape_valid(2, 2) is False
    assert strategy.is_shape_valid(0, 3) is False


# ------------------------------------------------------------------ #
# King Strategy Tests                                                 #
# ------------------------------------------------------------------ #

def test_king_shape_validation():
    strategy = KingStrategy()
    # Valid: 1 square in any direction
    assert strategy.is_shape_valid(1, 0) is True
    assert strategy.is_shape_valid(0, 1) is True
    assert strategy.is_shape_valid(1, 1) is True
    # Invalid: more than 1 square
    assert strategy.is_shape_valid(2, 0) is False
    assert strategy.is_shape_valid(2, 2) is False


# ------------------------------------------------------------------ #
# Queen Strategy Tests                                                #
# ------------------------------------------------------------------ #

def test_queen_shape_validation():
    strategy = QueenStrategy()
    # Valid: straight or diagonal
    assert strategy.is_shape_valid(0, 4) is True
    assert strategy.is_shape_valid(4, 0) is True
    assert strategy.is_shape_valid(4, 4) is True
    # Invalid: non-linear moves
    assert strategy.is_shape_valid(1, 2) is False

# ------------------------------------------------------------------ #
# Pawn Strategy Tests                                                 #
# ------------------------------------------------------------------ #

def test_pawn_shape_validation():
    strategy = PawnStrategy()
    
    # 1. Test standard forward step for a White Pawn (r2 - r1 == -1, dc == 0) into empty cell
    # White moves from row 6 to row 5
    assert strategy.is_valid_pawn_move(color='w', r1=6, r2=5, dc=0, target_token='.') is True
    
    # 2. Test invalid backward step for a White Pawn
    # White tries to move from row 6 to row 7
    assert strategy.is_valid_pawn_move(color='w', r1=6, r2=7, dc=0, target_token='.') is False

    # 3. Test capturing diagonally if target is occupied
    assert strategy.is_valid_pawn_move(color='w', r1=6, r2=5, dc=1, target_token='bR') is True