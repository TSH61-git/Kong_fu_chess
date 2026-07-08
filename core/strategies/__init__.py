from core.strategies.king_strategy import KingStrategy
from core.strategies.rook_strategy import RookStrategy
from core.strategies.bishop_strategy import BishopStrategy
from core.strategies.queen_strategy import QueenStrategy
from core.strategies.knight_strategy import KnightStrategy
from core.strategies.pawn_strategy import PawnStrategy
from core.interfaces.i_movement_strategy import IMovementStrategy
from typing import Dict


def build_default_registry(total_rows: int) -> Dict[str, IMovementStrategy]:
    return {
        'K': KingStrategy(),
        'R': RookStrategy(),
        'B': BishopStrategy(),
        'Q': QueenStrategy(),
        'N': KnightStrategy(),
        'P': PawnStrategy(total_rows),
    }
