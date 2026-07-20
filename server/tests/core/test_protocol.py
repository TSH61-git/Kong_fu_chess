import json

import pytest

from server.core.protocol import (
    ErrorCode,
    MalformedEnvelopeError,
    decode_envelope,
    encode_ack,
    encode_broadcast,
    encode_error,
    error_code_for_engine_reason,
)


class TestDecodeEnvelope:
    def test_decodes_type_id_and_data(self):
        envelope = decode_envelope('{"type": "move", "id": "abc", "data": {"cmd": "WQe2e5"}}')
        assert envelope.type == "move"
        assert envelope.id == "abc"
        assert envelope.data == {"cmd": "WQe2e5"}

    def test_id_defaults_to_none(self):
        assert decode_envelope('{"type": "ping"}').id is None

    def test_data_defaults_to_empty_dict(self):
        assert decode_envelope('{"type": "ping"}').data == {}

    def test_invalid_json_raises(self):
        with pytest.raises(MalformedEnvelopeError):
            decode_envelope("not json")

    def test_missing_type_raises(self):
        with pytest.raises(MalformedEnvelopeError):
            decode_envelope('{"data": {}}')

    def test_non_object_raises(self):
        with pytest.raises(MalformedEnvelopeError):
            decode_envelope('"just a string"')


class TestEncoders:
    def test_encode_ack_shape(self):
        payload = json.loads(encode_ack("abc", {"foo": "bar"}))
        assert payload == {"type": "ack", "in_reply_to": "abc", "ok": True, "data": {"foo": "bar"}}

    def test_encode_ack_defaults_to_empty_data(self):
        payload = json.loads(encode_ack("abc"))
        assert payload["data"] == {}

    def test_encode_error_shape(self):
        payload = json.loads(encode_error("abc", ErrorCode.NOT_YOUR_COLOR, "nope"))
        assert payload == {
            "type": "error", "in_reply_to": "abc", "code": "NOT_YOUR_COLOR", "message": "nope",
        }

    def test_encode_broadcast_shape(self):
        payload = json.loads(encode_broadcast("default", "move_accepted", {"x": 1}))
        assert payload == {
            "type": "broadcast", "event": "move_accepted", "room_id": "default", "data": {"x": 1},
        }


class TestErrorCodeForEngineReason:
    def test_maps_ok(self):
        assert error_code_for_engine_reason("ok") is ErrorCode.OK

    def test_maps_every_known_chess_engine_reason(self):
        reasons = [
            "game_over", "cooldown_active", "motion_in_progress", "destination_claimed",
            "illegal_piece_move", "friendly_destination", "empty_source", "outside_board",
        ]
        for reason in reasons:
            assert isinstance(error_code_for_engine_reason(reason), ErrorCode)

    def test_unknown_reason_raises(self):
        with pytest.raises(KeyError):
            error_code_for_engine_reason("not_a_real_reason")
