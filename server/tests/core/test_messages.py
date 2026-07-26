import json

from server.core.messages import (
    GameOverPayload,
    MatchReadyPayload,
    MatchStatePayload,
    MoveAcceptedPayload,
    OpponentDisconnectedPayload,
    OpponentReconnectedPayload,
    PieceCapturedPayload,
    StateTickPayload,
)


def _round_trip(payload):
    cls = type(payload)
    wire = json.loads(json.dumps(payload.to_dict()))
    return cls.from_dict(wire)


def test_move_accepted_payload_round_trips():
    payload = MoveAcceptedPayload(
        color="white", piece_type="pawn", source="e2", destination="e4", is_capture=False,
    )
    assert _round_trip(payload) == payload


def test_piece_captured_payload_round_trips():
    payload = PieceCapturedPayload(piece_type="pawn", piece_color="black", captured_by="white")
    assert _round_trip(payload) == payload


def test_game_over_payload_round_trips():
    payload = GameOverPayload(reason="king_captured", winner_username="alice")
    assert _round_trip(payload) == payload


def test_game_over_payload_round_trips_without_winner():
    payload = GameOverPayload(reason="both_disconnected")
    assert _round_trip(payload) == payload


def test_state_tick_payload_round_trips():
    payload = StateTickPayload(
        board_grid=[[None, "wP"], ["bK", None]],
        active_motions=[{"piece": "wQ"}],
        cooldowns=[{"square": "e5"}],
        game_over=False,
        frozen=True,
    )
    assert _round_trip(payload) == payload


def test_match_ready_payload_round_trips():
    payload = MatchReadyPayload(white_username="alice", black_username="bob")
    assert _round_trip(payload) == payload


def test_opponent_disconnected_payload_round_trips():
    payload = OpponentDisconnectedPayload(role="white", countdown_seconds=20.0)
    assert _round_trip(payload) == payload


def test_opponent_reconnected_payload_round_trips():
    payload = OpponentReconnectedPayload(role="black")
    assert _round_trip(payload) == payload


def test_match_state_payload_round_trips():
    payload = MatchStatePayload(
        white_username="alice", black_username=None, white_score=3, black_score=0,
    )
    assert _round_trip(payload) == payload
