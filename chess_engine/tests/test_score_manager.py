from chess_engine.engine.event_manager import EventManager
from chess_engine.engine.events import PieceCaptured
from chess_engine.engine.helpers.piece_info import PieceInfo
from chess_engine.engine.helpers.score_manager import PIECE_VALUES, ScoreManager
from chess_engine.model.piece import Color, Piece, PieceType

_WR = Piece(PieceType.ROOK, Color.WHITE)
_BP = Piece(PieceType.PAWN, Color.BLACK)
_BQ = Piece(PieceType.QUEEN, Color.BLACK)


class TestScoreManagerCaptureAttribution:
    def test_capture_attributed_to_the_capturing_color(self):
        mgr = ScoreManager(EventManager())
        mgr.record_capture(_BP, captured_by=Color.WHITE)

        assert len(mgr.get_captured(Color.WHITE)) == 1
        assert mgr.get_captured(Color.WHITE)[0].piece == PieceInfo(PieceType.PAWN, Color.BLACK)
        assert mgr.get_captured(Color.BLACK) == []

    def test_multiple_captures_accumulate_per_color(self):
        mgr = ScoreManager(EventManager())
        mgr.record_capture(_BP, captured_by=Color.WHITE)
        mgr.record_capture(_WR, captured_by=Color.BLACK)

        assert len(mgr.get_captured(Color.WHITE)) == 1
        assert len(mgr.get_captured(Color.BLACK)) == 1


class TestScoreManagerScores:
    def test_score_sums_piece_values_by_capturing_color(self):
        mgr = ScoreManager(EventManager())
        mgr.record_capture(_BP, captured_by=Color.WHITE)
        mgr.record_capture(_BQ, captured_by=Color.WHITE)

        scores = mgr.get_scores()
        assert scores[Color.WHITE] == PIECE_VALUES[PieceType.PAWN] + PIECE_VALUES[PieceType.QUEEN]
        assert scores[Color.BLACK] == 0

    def test_no_captures_yields_zero_scores(self):
        mgr = ScoreManager(EventManager())
        scores = mgr.get_scores()
        assert scores[Color.WHITE] == 0
        assert scores[Color.BLACK] == 0


class TestScoreManagerSubscribesToEvents:
    def test_publishing_piece_captured_updates_the_score(self):
        events = EventManager()
        mgr = ScoreManager(events)

        events.publish(PieceCaptured(piece=_BP, captured_by=Color.WHITE))

        assert len(mgr.get_captured(Color.WHITE)) == 1
        assert mgr.get_scores()[Color.WHITE] == PIECE_VALUES[PieceType.PAWN]


class TestCapturedEntryIsADto:
    def test_piece_info_from_piece_extracts_type_and_color(self):
        info = PieceInfo.from_piece(_BQ)
        assert info == PieceInfo(PieceType.QUEEN, Color.BLACK)

    def test_captured_entry_holds_a_piece_info_not_the_original_piece(self):
        mgr = ScoreManager(EventManager())
        mgr.record_capture(_BP, captured_by=Color.WHITE)

        stored = mgr.get_captured(Color.WHITE)[0].piece
        assert isinstance(stored, PieceInfo)
        assert not isinstance(stored, Piece)
