from server.core.clock import FakeClock, RealClock


class TestRealClock:
    def test_now_is_non_decreasing(self):
        clock = RealClock()
        first = clock.now()
        second = clock.now()
        assert second >= first


class TestFakeClock:
    def test_starts_at_given_value(self):
        clock = FakeClock(start=10.0)
        assert clock.now() == 10.0

    def test_defaults_to_zero(self):
        assert FakeClock().now() == 0.0

    def test_advance_moves_time_forward(self):
        clock = FakeClock(start=0.0)
        clock.advance(5)
        assert clock.now() == 5

    def test_advance_is_cumulative(self):
        clock = FakeClock(start=0.0)
        clock.advance(5)
        clock.advance(3)
        assert clock.now() == 8
