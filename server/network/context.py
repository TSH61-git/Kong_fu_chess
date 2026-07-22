# ServerContext — the shared, per-process object handed to every dispatch
# handler in place of Phase 1-2's single MatchSession. Deliberately minimal:
# only what a handler actually reads. A move/jump handler never needs this
# at all — it finds its match via session.current_match instead (set by
# MatchSession.try_seat at seating time).
from __future__ import annotations

from dataclasses import dataclass

from server.auth.service import AuthService
from server.core.bus import Bus
from server.core.clock import Clock
from server.db.matches_repository import MatchesRepository
from server.game.registry import MatchRegistry
from server.matchmaking.queue import MatchmakingQueue


@dataclass(frozen=True)
class ServerContext:
    auth_service: AuthService
    clock: Clock
    queue: MatchmakingQueue
    registry: MatchRegistry
    bus: Bus
    matches_repo: MatchesRepository
