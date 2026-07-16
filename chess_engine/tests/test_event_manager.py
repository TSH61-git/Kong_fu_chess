from dataclasses import dataclass

from chess_engine.engine.event_manager import EventManager


@dataclass(frozen=True)
class _Ping:
    value: int


@dataclass(frozen=True)
class _Pong:
    value: int


class TestEventManagerDispatch:
    def test_subscriber_receives_published_event(self):
        events = EventManager()
        received = []
        events.subscribe(_Ping, received.append)

        events.publish(_Ping(value=1))

        assert received == [_Ping(value=1)]

    def test_multiple_subscribers_all_receive_the_event(self):
        events = EventManager()
        received_a, received_b = [], []
        events.subscribe(_Ping, received_a.append)
        events.subscribe(_Ping, received_b.append)

        events.publish(_Ping(value=1))

        assert received_a == [_Ping(value=1)]
        assert received_b == [_Ping(value=1)]

    def test_subscribers_only_receive_their_own_event_type(self):
        events = EventManager()
        received = []
        events.subscribe(_Ping, received.append)

        events.publish(_Pong(value=1))

        assert received == []

    def test_publishing_with_no_subscribers_does_not_raise(self):
        events = EventManager()
        events.publish(_Ping(value=1))
