import asyncio
import json

from chess_engine.model.piece import Color, PieceType
from chess_engine.model.position import Position

from server.core.bus import Bus
from server.game.engine_bridge import EngineEventRelay, RoomBroadcaster, _encode_room_event
from server.game.engine_factory import build_game_stack
from server.game.events import RoomGameOver, RoomMatchReady, RoomMoveAccepted, RoomStateTick


class _RecordingSession:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, message: str) -> None:
        self.sent.append(message)


def test_engine_event_relay_republishes_move_accepted_onto_the_bus():
    async def body():
        bus = Bus()
        stack = build_game_stack()
        EngineEventRelay(stack.engine, bus, "test-room")
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("room:test-room", handler)

        result = stack.engine.request_move(Position(6, 4), Position(5, 4))
        assert result.is_accepted
        await asyncio.sleep(0.01)

        assert len(received) == 1
        event = received[0]
        assert isinstance(event, RoomMoveAccepted)
        assert event.room_id == "test-room"
        assert event.color == Color.WHITE
        assert event.piece_type == PieceType.PAWN

    asyncio.run(body())


def test_engine_event_relay_republishes_game_over():
    async def body():
        bus = Bus()
        stack = build_game_stack()
        EngineEventRelay(stack.engine, bus, "test-room")
        received = []

        async def handler(event):
            received.append(event)

        bus.subscribe("room:test-room", handler)
        stack.engine.notify_king_captured()
        await asyncio.sleep(0.01)

        assert any(isinstance(event, RoomGameOver) for event in received)

    asyncio.run(body())


def test_room_broadcaster_forwards_encoded_messages_to_current_sessions():
    async def body():
        bus = Bus()
        stack = build_game_stack()
        EngineEventRelay(stack.engine, bus, "test-room")
        session = _RecordingSession()
        RoomBroadcaster(bus, "test-room", lambda: [session])

        result = stack.engine.request_move(Position(6, 4), Position(5, 4))
        assert result.is_accepted
        await asyncio.sleep(0.01)

        assert len(session.sent) == 1
        assert '"event": "move_accepted"' in session.sent[0]

    asyncio.run(body())


def test_encode_room_event_for_match_ready():
    message = json.loads(_encode_room_event("test-room", RoomMatchReady(ts=0.0, room_id="test-room")))
    assert message == {"type": "broadcast", "event": "match_ready", "room_id": "test-room", "data": {}}


def test_encode_room_event_for_state_tick_includes_motions_and_cooldowns():
    event = RoomStateTick(
        ts=0.0, room_id="test-room",
        board_grid=[[None]], active_motions=[{"piece": "wQ"}], cooldowns=[{"square": "e5"}],
        game_over=False,
    )
    message = json.loads(_encode_room_event("test-room", event))
    assert message["data"]["active_motions"] == [{"piece": "wQ"}]
    assert message["data"]["cooldowns"] == [{"square": "e5"}]


def test_room_broadcaster_close_stops_forwarding():
    async def body():
        bus = Bus()
        stack = build_game_stack()
        EngineEventRelay(stack.engine, bus, "test-room")
        session = _RecordingSession()
        broadcaster = RoomBroadcaster(bus, "test-room", lambda: [session])
        broadcaster.close()

        stack.engine.request_move(Position(6, 4), Position(5, 4))
        await asyncio.sleep(0.01)

        assert session.sent == []

    asyncio.run(body())
