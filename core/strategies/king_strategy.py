from core.interfaces.i_movement_strategy import IMovementStrategy


class KingStrategy(IMovementStrategy):
    def is_shape_valid(self, dr: int, dc: int) -> bool:
        return max(dr, dc) == 1
