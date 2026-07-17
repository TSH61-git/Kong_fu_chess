from chess_engine.engine.event_manager import EventManager
from chess_engine.engine.events import MoveAccepted
from chess_engine.engine.helpers.move_history import MoveHistory
from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position

_WP = Piece(PieceType.PAWN, Color.WHITE)


class TestMoveHistoryDirectRecord:
    def test_record_appends_with_incrementing_index(self):
        history = MoveHistory(EventManager())
        history.record(_WP, Position(6, 4), Position(4, 4))
        history.record(_WP, Position(4, 4), Position(3, 4))

        entries = history.entries()
        assert [e.index for e in entries] == [1, 2]

    def test_display_text_includes_letter_and_algebraic_destination(self):
        history = MoveHistory(EventManager())
        history.record(_WP, Position(6, 4), Position(4, 4))

        assert history.entries()[0].display_text() == "Pe4"


class TestMoveHistorySubscribesToEvents:
    def test_publishing_move_accepted_appends_an_entry(self):
        events = EventManager()
        history = MoveHistory(events)

        events.publish(MoveAccepted(
            color=Color.WHITE,
            piece_type=PieceType.PAWN,
            source=Position(6, 4),
            destination=Position(4, 4),
            is_capture=False,
        ))

        entries = history.entries()
        assert len(entries) == 1
        assert entries[0].color == Color.WHITE
        assert entries[0].piece_type == PieceType.PAWN
