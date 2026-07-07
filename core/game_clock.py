class GameClock:
    """
    Monostate: every instance shares the same _tick class variable.
    Inject an instance via DI — callers never import a global.
    Call GameClock.reset() between tests to wipe shared state.
    """
    _tick: int = 0

    def advance(self, ms: int) -> None:
        GameClock._tick += ms

    def now(self) -> int:
        return GameClock._tick

    @classmethod
    def reset(cls) -> None:
        cls._tick = 0
