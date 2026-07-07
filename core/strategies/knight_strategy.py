from core.interfaces.i_movement_strategy import IMovementStrategy


class KnightStrategy(IMovementStrategy):
    def is_shape_valid(self, dr: int, dc: int) -> bool:
        return (dr == 1 and dc == 2) or (dr == 2 and dc == 1)
