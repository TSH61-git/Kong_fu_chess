import pytest

from chess_engine.model.board import Board
from chess_engine.model.board_factory import standard_board
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position
from chess_engine.wire.notation import (
    MalformedMoveCommandError,
    build_move_command,
    parse_move_command,
    piece_to_wire_token,
    position_to_square,
    refresh_board,
    serialize_board,
    square_to_position,
    wire_token_to_piece,
)


class TestSquareToPosition:
    def test_a1_is_bottom_left(self):
        assert square_to_position("a1") == Position(row=7, col=0)

    def test_h8_is_top_right(self):
        assert square_to_position("h8") == Position(row=0, col=7)

    def test_e2(self):
        assert square_to_position("e2") == Position(row=6, col=4)

    def test_invalid_file_raises(self):
        with pytest.raises(MalformedMoveCommandError):
            square_to_position("z1")

    def test_invalid_rank_raises(self):
        with pytest.raises(MalformedMoveCommandError):
            square_to_position("a9")

    def test_wrong_length_raises(self):
        with pytest.raises(MalformedMoveCommandError):
            square_to_position("a10")


class TestPositionToSquare:
    def test_round_trips_with_square_to_position(self):
        for square in ["a1", "h8", "e2", "e5", "d4"]:
            assert position_to_square(square_to_position(square)) == square


class TestParseMoveCommand:
    def test_parses_all_fields(self):
        parsed = parse_move_command("WQe2e5")
        assert parsed.color == Color.WHITE
        assert parsed.piece_type == PieceType.QUEEN
        assert parsed.source == Position(row=6, col=4)
        assert parsed.destination == Position(row=3, col=4)

    def test_black_pawn(self):
        parsed = parse_move_command("BPe7e5")
        assert parsed.color == Color.BLACK
        assert parsed.piece_type == PieceType.PAWN

    def test_wrong_length_raises(self):
        with pytest.raises(MalformedMoveCommandError):
            parse_move_command("WQe2e")

    def test_unknown_color_letter_raises(self):
        with pytest.raises(MalformedMoveCommandError):
            parse_move_command("XQe2e5")

    def test_unknown_piece_letter_raises(self):
        with pytest.raises(MalformedMoveCommandError):
            parse_move_command("WXe2e5")


class TestBuildMoveCommand:
    def test_round_trips_with_parse_move_command(self):
        source, destination = Position(6, 4), Position(3, 4)
        command = build_move_command(Color.WHITE, PieceType.QUEEN, source, destination)
        assert command == "WQe2e5"
        assert parse_move_command(command) == parse_move_command("WQe2e5")

    def test_black_knight(self):
        assert build_move_command(Color.BLACK, PieceType.KNIGHT, Position(0, 1), Position(2, 2)) == "BNb8c6"


class TestPieceToWireToken:
    def test_none_is_none(self):
        assert piece_to_wire_token(None) is None

    def test_white_queen(self):
        assert piece_to_wire_token(Piece(PieceType.QUEEN, Color.WHITE)) == "wQ"

    def test_black_knight(self):
        assert piece_to_wire_token(Piece(PieceType.KNIGHT, Color.BLACK)) == "bN"


class TestWireTokenToPiece:
    def test_none_is_none(self):
        assert wire_token_to_piece(None) is None

    def test_round_trips_with_piece_to_wire_token(self):
        piece = Piece(PieceType.BISHOP, Color.BLACK)
        assert wire_token_to_piece(piece_to_wire_token(piece)) == piece


class TestSerializeBoard:
    def test_standard_board_shape_and_corners(self):
        grid = serialize_board(standard_board())
        assert len(grid) == 8 and all(len(row) == 8 for row in grid)
        assert grid[0][0] == "bR"
        assert grid[7][0] == "wR"
        assert grid[4][4] is None


class TestRefreshBoard:
    def test_mutates_the_same_board_instance_in_place(self):
        board = Board(rows=8, cols=8)
        refresh_board(board, serialize_board(standard_board()))
        white_king = board.get(Position(7, 4))
        assert white_king.piece_type == PieceType.KING
        assert white_king.color == Color.WHITE

    def test_clears_cells_that_became_empty(self):
        board = Board(rows=8, cols=8)
        board.set(Position(3, 3), Piece(PieceType.QUEEN, Color.WHITE))
        refresh_board(board, [[None] * 8 for _ in range(8)])
        assert board.get(Position(3, 3)) is None
