from core.interfaces.i_movement_strategy import IMovementStrategy


class RookStrategy(IMovementStrategy):
    @property
    def needs_path_check(self) -> bool:
        return True

    def is_shape_valid(self, dr: int, dc: int) -> bool:
        return dr == 0 or dc == 0
