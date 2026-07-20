from chess_engine.model.piece import Color, Piece, PieceType
from chess_engine.model.position import Position
from chess_engine.realtime.motion import Motion
from chess_engine.wire.state import (
    deserialize_cooldowns,
    deserialize_motions,
    serialize_cooldowns,
    serialize_motions,
)


class TestSerializeMotions:
    def test_serializes_every_field(self):
        motion = Motion(
            piece=Piece(PieceType.QUEEN, Color.WHITE),
            source=Position(6, 4), destination=Position(3, 4),
            elapsed_ms=320, duration_ms=700,
        )
        [entry] = serialize_motions([motion])
        assert entry == {
            "piece": "wQ", "source": "e2", "destination": "e5",
            "elapsed_ms": 320, "duration_ms": 700,
        }

    def test_empty_list_round_trips(self):
        assert serialize_motions([]) == []


class TestDeserializeMotions:
    def test_round_trips_with_serialize_motions(self):
        motion = Motion(
            piece=Piece(PieceType.KNIGHT, Color.BLACK),
            source=Position(0, 1), destination=Position(2, 2),
            elapsed_ms=100, duration_ms=200,
        )
        [restored] = deserialize_motions(serialize_motions([motion]))
        assert restored.piece == motion.piece
        assert restored.source == motion.source
        assert restored.destination == motion.destination
        assert restored.elapsed_ms == motion.elapsed_ms
        assert restored.duration_ms == motion.duration_ms


class TestCooldowns:
    def test_serialize_cooldowns(self):
        cooldowns = {Position(3, 4): 640}
        assert serialize_cooldowns(cooldowns) == [{"square": "e5", "remaining_ms": 640}]

    def test_deserialize_round_trips_with_serialize(self):
        cooldowns = {Position(3, 4): 640, Position(6, 0): 1000}
        assert deserialize_cooldowns(serialize_cooldowns(cooldowns)) == cooldowns

    def test_empty_dict_round_trips(self):
        assert deserialize_cooldowns(serialize_cooldowns({})) == {}
