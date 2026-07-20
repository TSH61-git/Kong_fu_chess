# Pure Elo math — no I/O, no clock.
from __future__ import annotations

from typing import Optional

from server import config


def expected_score(rating_a: float, rating_b: float) -> float:
    return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))


def update_ratings(
    white_elo: int, black_elo: int, white_won: Optional[bool], k: int = config.ELO_K_FACTOR,
) -> tuple[int, int]:
    # white_won: True white wins, False black wins, None a draw.
    expected_white = expected_score(white_elo, black_elo)
    expected_black = 1 - expected_white

    if white_won is True:
        actual_white, actual_black = 1.0, 0.0
    elif white_won is False:
        actual_white, actual_black = 0.0, 1.0
    else:
        actual_white, actual_black = 0.5, 0.5

    new_white_elo = round(white_elo + k * (actual_white - expected_white))
    new_black_elo = round(black_elo + k * (actual_black - expected_black))
    return new_white_elo, new_black_elo
