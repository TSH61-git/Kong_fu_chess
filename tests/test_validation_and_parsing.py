import pytest
from core.board_parser import BoardParser
from core.movement_validator import MovementValidator
from core.exceptions import UnknownTokenError, RowWidthMismatchError
from core.strategies.rook_strategy import RookStrategy
from core.strategies.bishop_strategy import BishopStrategy
from core.strategies.knight_strategy import KnightStrategy
from core.strategies.king_strategy import KingStrategy
from core.strategies.queen_strategy import QueenStrategy
from core.strategies.pawn_strategy import PawnStrategy


# ------------------------------------------------------------------ #
# Fixtures                                                            #
# ------------------------------------------------------------------ #

@pytest.fixture
def registry():
    return {
        'R': RookStrategy(),
        'B': BishopStrategy(),
        'N': KnightStrategy(),
        'K': KingStrategy(),
        'Q': QueenStrategy(),
        'P': PawnStrategy(),
    }


@pytest.fixture
def validator(registry):
    return MovementValidator(registry)


@pytest.fixture
def simple_board():
    # 4x4 board: wR at (0,0), bR at (0,3), empty elsewhere
    return [
        ['wR', '.', '.', 'bR'],
        ['.', '.', '.', '.'],
        ['.', '.', '.', '.'],
        ['.', '.', '.', '.'],
    ]


# ------------------------------------------------------------------ #
# BoardParser.validate_and_parse                                      #
# ------------------------------------------------------------------ #

class TestBoardParserValidateAndParse:
    def test_valid_board_returns_matrix(self):
        lines = ['wR . . bR', '. . . .', '. . . .', '. . . .']
        board = BoardParser.validate_and_parse(lines)
        assert board[0][0] == 'wR'
        assert board[0][3] == 'bR'
        assert len(board) == 4
        assert all(len(row) == 4 for row in board)

    def test_empty_lines_are_skipped(self):
        lines = ['', 'wK .', '', '. bK', '']
        board = BoardParser.validate_and_parse(lines)
        assert len(board) == 2

    def test_all_valid_tokens_accepted(self):
        tokens = 'wK bK wR bR wB bB wQ bQ wN bN wP bP .'
        board = BoardParser.validate_and_parse([tokens])
        assert len(board[0]) == 13

    def test_unknown_token_raises(self):
        with pytest.raises(UnknownTokenError):
            BoardParser.validate_and_parse(['wR XX .'])

    def test_row_width_mismatch_raises(self):
        with pytest.raises(RowWidthMismatchError):
            BoardParser.validate_and_parse(['wR . .', 'wR .'])

    def test_fully_empty_input_returns_empty_list(self):
        assert BoardParser.validate_and_parse([]) == []

    def test_all_empty_lines_returns_empty_list(self):
        assert BoardParser.validate_and_parse(['', '  ', '']) == []

    def test_single_dot_row(self):
        board = BoardParser.validate_and_parse(['.'])
        assert board == [['.']]


    def test_first_non_empty_row_sets_width(self):
        lines = ['', 'wR bR', '. .']
        board = BoardParser.validate_and_parse(lines)
        assert len(board) == 2
        assert len(board[0]) == 2


# ------------------------------------------------------------------ #
# BoardParser.to_string                                               #
# ------------------------------------------------------------------ #

class TestBoardParserToString:
    def test_to_string_roundtrip(self):
        lines = ['wR . . bR', '. . . .']
        board = BoardParser.validate_and_parse(lines)
        result = BoardParser.to_string(board)
        assert result == 'wR . . bR\n. . . .'

    def test_to_string_single_row(self):
        board = [['wK', 'bK']]
        assert BoardParser.to_string(board) == 'wK bK'


# ------------------------------------------------------------------ #
# MovementValidator — same-square (no-op)                            #
# ------------------------------------------------------------------ #

class TestMovementValidatorNoOp:
    def test_same_square_is_valid(self, validator, simple_board):
        assert validator.is_valid_move(simple_board, 'wR', (0, 0), (0, 0)) is True


# ------------------------------------------------------------------ #
# MovementValidator — friendly fire                                   #
# ------------------------------------------------------------------ #

class TestMovementValidatorFriendlyFire:
    def test_cannot_capture_own_piece(self, validator):
        board = [['wR', 'wB'], ['.', '.']]
        assert validator.is_valid_move(board, 'wR', (0, 0), (0, 1)) is False


# ------------------------------------------------------------------ #
# MovementValidator — unknown piece type                              #
# ------------------------------------------------------------------ #

class TestMovementValidatorUnknownPiece:
    def test_unknown_piece_type_returns_false(self, validator, simple_board):
        assert validator.is_valid_move(simple_board, 'wX', (0, 0), (1, 0)) is False


# ------------------------------------------------------------------ #
# MovementValidator — Rook (sliding, path check)                     #
# ------------------------------------------------------------------ #

class TestMovementValidatorRook:
    def test_rook_valid_horizontal(self, validator, simple_board):
        assert validator.is_valid_move(simple_board, 'wR', (0, 0), (0, 2)) is True

    def test_rook_valid_vertical(self, validator, simple_board):
        assert validator.is_valid_move(simple_board, 'wR', (0, 0), (3, 0)) is True

    def test_rook_capture_enemy(self, validator, simple_board):
        assert validator.is_valid_move(simple_board, 'wR', (0, 0), (0, 3)) is True

    def test_rook_blocked_by_piece(self, validator):
        board = [['wR', 'wB', '.', 'bR'], ['.', '.', '.', '.'],
                 ['.', '.', '.', '.'], ['.', '.', '.', '.']]
        assert validator.is_valid_move(board, 'wR', (0, 0), (0, 3)) is False

    def test_rook_invalid_diagonal(self, validator, simple_board):
        assert validator.is_valid_move(simple_board, 'wR', (0, 0), (1, 1)) is False


# ------------------------------------------------------------------ #
# MovementValidator — Bishop (sliding, path check)                   #
# ------------------------------------------------------------------ #

class TestMovementValidatorBishop:
    def test_bishop_valid_diagonal(self, validator):
        board = [['.', '.', '.', '.'],
                 ['.', 'wB', '.', '.'],
                 ['.', '.', '.', '.'],
                 ['.', '.', '.', '.']]
        assert validator.is_valid_move(board, 'wB', (1, 1), (3, 3)) is True

    def test_bishop_blocked(self, validator):
        board = [['.', '.', '.', '.'],
                 ['.', 'wB', '.', '.'],
                 ['.', '.', 'wP', '.'],
                 ['.', '.', '.', '.']]
        assert validator.is_valid_move(board, 'wB', (1, 1), (3, 3)) is False

    def test_bishop_invalid_straight(self, validator):
        board = [['.', '.'], ['.', 'wB'], ['.', '.'], ['.', '.']]
        assert validator.is_valid_move(board, 'wB', (1, 1), (3, 1)) is False


# ------------------------------------------------------------------ #
# MovementValidator — Queen (sliding)                                 #
# ------------------------------------------------------------------ #

class TestMovementValidatorQueen:
    def test_queen_straight(self, validator, simple_board):
        simple_board[0][0] = 'wQ'
        assert validator.is_valid_move(simple_board, 'wQ', (0, 0), (3, 0)) is True

    def test_queen_diagonal(self, validator, simple_board):
        simple_board[0][0] = 'wQ'
        assert validator.is_valid_move(simple_board, 'wQ', (0, 0), (3, 3)) is True

    def test_queen_invalid_shape(self, validator, simple_board):
        simple_board[0][0] = 'wQ'
        assert validator.is_valid_move(simple_board, 'wQ', (0, 0), (1, 2)) is False


# ------------------------------------------------------------------ #
# MovementValidator — Knight (no path check)                         #
# ------------------------------------------------------------------ #

class TestMovementValidatorKnight:
    def test_knight_valid_l_shape(self, validator, simple_board):
        simple_board[0][0] = 'wN'
        assert validator.is_valid_move(simple_board, 'wN', (0, 0), (2, 1)) is True

    def test_knight_jumps_over_pieces(self, validator):
        board = [['wN', 'wP', 'wP', '.'],
                 ['wP', '.', '.', '.'],
                 ['.', '.', '.', '.'],
                 ['.', '.', '.', '.']]
        assert validator.is_valid_move(board, 'wN', (0, 0), (2, 1)) is True

    def test_knight_invalid_shape(self, validator, simple_board):
        simple_board[0][0] = 'wN'
        assert validator.is_valid_move(simple_board, 'wN', (0, 0), (2, 2)) is False


# ------------------------------------------------------------------ #
# MovementValidator — King                                            #
# ------------------------------------------------------------------ #

class TestMovementValidatorKing:
    def test_king_one_step(self, validator, simple_board):
        simple_board[0][0] = 'wK'
        assert validator.is_valid_move(simple_board, 'wK', (0, 0), (1, 1)) is True

    def test_king_two_steps_invalid(self, validator, simple_board):
        simple_board[0][0] = 'wK'
        assert validator.is_valid_move(simple_board, 'wK', (0, 0), (2, 0)) is False


# ------------------------------------------------------------------ #
# MovementValidator — Pawn                                            #
# ------------------------------------------------------------------ #

class TestMovementValidatorPawn:
    def test_white_pawn_forward(self, validator):
        board = [['.', '.'], ['.', '.'], ['.', '.'],
                 ['.', '.'], ['.', '.'], ['.', '.'],
                 ['wP', '.'], ['.', '.']]
        assert validator.is_valid_move(board, 'wP', (6, 0), (5, 0)) is True

    def test_white_pawn_backward_invalid(self, validator):
        board = [['.', '.'], ['.', '.'], ['.', '.'],
                 ['.', '.'], ['.', '.'], ['.', '.'],
                 ['wP', '.'], ['.', '.']]
        assert validator.is_valid_move(board, 'wP', (6, 0), (7, 0)) is False

    def test_white_pawn_diagonal_capture(self, validator):
        board = [['.', '.'], ['.', '.'], ['.', '.'],
                 ['.', '.'], ['.', '.'], ['.', 'bP'],
                 ['wP', '.'], ['.', '.']]
        assert validator.is_valid_move(board, 'wP', (6, 0), (5, 1)) is True
