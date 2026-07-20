# Pure matchmaking core — no asyncio, no Clock reference. Callers pass a
# plain float `now`; the async driver (matchmaker.py) is the only thing
# that ever calls a real clock. This makes the queue trivially testable
# with literal floats, no FakeClock needed.
from __future__ import annotations

from dataclasses import dataclass

from server.network.session import ClientSession


@dataclass(frozen=True)
class QueueEntry:
    session: ClientSession
    elo: int
    joined_at: float


class MatchmakingQueue:
    def __init__(self, elo_range: int = 100) -> None:
        self._elo_range = elo_range
        self._entries: list[QueueEntry] = []

    def enqueue(self, session: ClientSession, elo: int, now: float) -> None:
        self._entries.append(QueueEntry(session=session, elo=elo, joined_at=now))

    def cancel(self, session: ClientSession) -> bool:
        for entry in self._entries:
            if entry.session is session:
                self._entries.remove(entry)
                return True
        return False

    def contains(self, session: ClientSession) -> bool:
        return any(entry.session is session for entry in self._entries)

    def find_pairings(self, now: float) -> list[tuple[QueueEntry, QueueEntry]]:
        # FIFO-priority within +/-elo_range: walk oldest-first, pair each
        # still-unmatched entry with the earliest still-unmatched entry
        # within range found scanning forward. No auto-widening — `now` is
        # accepted for signature symmetry with expire() and as a hook for a
        # future widening policy, but plays no role in this phase's rule.
        del now
        pairs: list[tuple[QueueEntry, QueueEntry]] = []
        matched_ids: set[int] = set()

        for i, entry_a in enumerate(self._entries):
            if id(entry_a) in matched_ids:
                continue
            for entry_b in self._entries[i + 1:]:
                if id(entry_b) in matched_ids:
                    continue
                if abs(entry_a.elo - entry_b.elo) <= self._elo_range:
                    pairs.append((entry_a, entry_b))
                    matched_ids.add(id(entry_a))
                    matched_ids.add(id(entry_b))
                    break

        if matched_ids:
            self._entries = [entry for entry in self._entries if id(entry) not in matched_ids]
        return pairs

    def expire(self, now: float, timeout_seconds: float = 60.0) -> list[QueueEntry]:
        expired = [entry for entry in self._entries if now - entry.joined_at >= timeout_seconds]
        if expired:
            expired_ids = {id(entry) for entry in expired}
            self._entries = [entry for entry in self._entries if id(entry) not in expired_ids]
        return expired
