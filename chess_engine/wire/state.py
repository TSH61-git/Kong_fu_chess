# Wire (de)serialization for in-flight motions and cooldowns — the runtime
# state a network client needs (alongside the board) to animate the game
# smoothly rather than only seeing pieces "jump" between resting positions.
from __future__ import annotations

from typing import Any

from chess_engine.model.position import Position
from chess_engine.realtime.motion import Motion
from chess_engine.wire.notation import piece_to_wire_token, position_to_square, square_to_position, wire_token_to_piece


def serialize_motions(motions: list[Motion]) -> list[dict[str, Any]]:
    return [
        {
            "piece": piece_to_wire_token(motion.piece),
            "source": position_to_square(motion.source),
            "destination": position_to_square(motion.destination),
            "elapsed_ms": motion.elapsed_ms,
            "duration_ms": motion.duration_ms,
        }
        for motion in motions
    ]


def deserialize_motions(entries: list[dict[str, Any]]) -> list[Motion]:
    return [
        Motion(
            piece=wire_token_to_piece(entry["piece"]),
            source=square_to_position(entry["source"]),
            destination=square_to_position(entry["destination"]),
            elapsed_ms=entry["elapsed_ms"],
            duration_ms=entry["duration_ms"],
        )
        for entry in entries
    ]


def serialize_cooldowns(cooldowns: dict[Position, int]) -> list[dict[str, Any]]:
    return [
        {"square": position_to_square(position), "remaining_ms": remaining_ms}
        for position, remaining_ms in cooldowns.items()
    ]


def deserialize_cooldowns(entries: list[dict[str, Any]]) -> dict[Position, int]:
    return {square_to_position(entry["square"]): entry["remaining_ms"] for entry in entries}
