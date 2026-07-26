# Shared wire-payload DTOs. Every message body that crosses the WebSocket
# boundary (server -> client broadcasts/notices, and the room-state ack
# payload) has a frozen dataclass here with explicit to_dict()/from_dict()
# conversions, so json.dumps/json.loads (raw dict/JSON primitives) never
# leak past server/network/protocol/__init__.py's encode_* functions on the server side,
# or past the receive boundary (DevClient._handle_message) on the client
# side. Both server and client import this module — it's the single typed
# source of truth for wire-payload shape, replacing hand-built dicts that
# used to drift independently on each side.
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class MoveAcceptedPayload:
    color: str
    piece_type: str
    source: str
    destination: str
    is_capture: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "color": self.color, "piece_type": self.piece_type,
            "source": self.source, "destination": self.destination,
            "is_capture": self.is_capture,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MoveAcceptedPayload":
        return cls(
            color=data["color"], piece_type=data["piece_type"],
            source=data["source"], destination=data["destination"],
            is_capture=data["is_capture"],
        )


@dataclass(frozen=True)
class PieceCapturedPayload:
    piece_type: str
    piece_color: str
    captured_by: str

    def to_dict(self) -> dict[str, Any]:
        return {"piece_type": self.piece_type, "piece_color": self.piece_color, "captured_by": self.captured_by}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PieceCapturedPayload":
        return cls(piece_type=data["piece_type"], piece_color=data["piece_color"], captured_by=data["captured_by"])


@dataclass(frozen=True)
class GameOverPayload:
    reason: str
    winner_username: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "winner_username": self.winner_username}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "GameOverPayload":
        return cls(reason=data.get("reason"), winner_username=data.get("winner_username"))


@dataclass(frozen=True)
class StateTickPayload:
    board_grid: list
    active_motions: list
    cooldowns: list
    game_over: bool
    frozen: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "board_grid": self.board_grid, "active_motions": self.active_motions,
            "cooldowns": self.cooldowns, "game_over": self.game_over, "frozen": self.frozen,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StateTickPayload":
        return cls(
            board_grid=data["board_grid"], active_motions=data["active_motions"],
            cooldowns=data["cooldowns"], game_over=data["game_over"], frozen=data.get("frozen", False),
        )


@dataclass(frozen=True)
class MatchReadyPayload:
    white_username: str
    black_username: str

    def to_dict(self) -> dict[str, Any]:
        return {"white_username": self.white_username, "black_username": self.black_username}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchReadyPayload":
        return cls(white_username=data["white_username"], black_username=data["black_username"])


@dataclass(frozen=True)
class OpponentDisconnectedPayload:
    role: str
    countdown_seconds: float

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role, "countdown_seconds": self.countdown_seconds}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpponentDisconnectedPayload":
        return cls(role=data["role"], countdown_seconds=data["countdown_seconds"])


@dataclass(frozen=True)
class OpponentReconnectedPayload:
    role: str

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OpponentReconnectedPayload":
        return cls(role=data["role"])


@dataclass(frozen=True)
class MatchStatePayload:
    # Included in every room_create/room_join ack (not just the viewer path)
    # so any joiner gets the current player names and score in the same
    # response that seats/spectates them.
    white_username: Optional[str]
    black_username: Optional[str]
    white_score: int
    black_score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "white_username": self.white_username, "black_username": self.black_username,
            "white_score": self.white_score, "black_score": self.black_score,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MatchStatePayload":
        return cls(
            white_username=data.get("white_username"), black_username=data.get("black_username"),
            white_score=data.get("white_score", 0), black_score=data.get("black_score", 0),
        )
