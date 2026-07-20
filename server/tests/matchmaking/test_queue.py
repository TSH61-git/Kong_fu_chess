from server.matchmaking.queue import MatchmakingQueue


def _session(name: str):
    # Identity is all MatchmakingQueue cares about — a bare marker object
    # is enough, no need for a real ClientSession here.
    return object()


class TestFindPairings:
    def test_pairs_two_entries_within_range(self):
        queue = MatchmakingQueue(elo_range=100)
        a, b = _session("a"), _session("b")
        queue.enqueue(a, elo=1200, now=0.0)
        queue.enqueue(b, elo=1250, now=1.0)

        pairs = queue.find_pairings(now=2.0)

        assert len(pairs) == 1
        paired_sessions = {pairs[0][0].session, pairs[0][1].session}
        assert paired_sessions == {a, b}
        assert not queue.contains(a)
        assert not queue.contains(b)

    def test_does_not_pair_entries_outside_range(self):
        queue = MatchmakingQueue(elo_range=100)
        a, b = _session("a"), _session("b")
        queue.enqueue(a, elo=1200, now=0.0)
        queue.enqueue(b, elo=1400, now=1.0)

        pairs = queue.find_pairings(now=2.0)

        assert pairs == []
        assert queue.contains(a)
        assert queue.contains(b)

    def test_fifo_priority_skips_an_out_of_range_middle_entry(self):
        queue = MatchmakingQueue(elo_range=50)
        a, b, c = _session("a"), _session("b"), _session("c")
        queue.enqueue(a, elo=1000, now=0.0)   # oldest
        queue.enqueue(b, elo=1200, now=1.0)   # out of range for a
        queue.enqueue(c, elo=1010, now=2.0)   # in range for a

        pairs = queue.find_pairings(now=3.0)

        assert len(pairs) == 1
        paired_sessions = {pairs[0][0].session, pairs[0][1].session}
        assert paired_sessions == {a, c}
        assert queue.contains(b)  # left alone, still queued


class TestCancelAndContains:
    def test_cancel_removes_a_queued_session(self):
        queue = MatchmakingQueue()
        a = _session("a")
        queue.enqueue(a, elo=1200, now=0.0)

        assert queue.cancel(a) is True
        assert queue.contains(a) is False

    def test_cancel_of_an_unqueued_session_returns_false(self):
        queue = MatchmakingQueue()
        assert queue.cancel(_session("stranger")) is False


class TestExpire:
    def test_expires_entries_past_the_timeout(self):
        queue = MatchmakingQueue()
        stale, fresh = _session("stale"), _session("fresh")
        queue.enqueue(stale, elo=1200, now=0.0)
        queue.enqueue(fresh, elo=1200, now=59.0)

        expired = queue.expire(now=60.0, timeout_seconds=60.0)

        assert [entry.session for entry in expired] == [stale]
        assert queue.contains(fresh)
        assert not queue.contains(stale)
