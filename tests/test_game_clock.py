import pytest
# Updated to import directly from the core directory
from core.game_clock import GameClock

@pytest.fixture(autouse=True)
def reset_clock():
    """Automatically resets the shared clock state before each test."""
    GameClock.reset()

def test_clock_initialization():
    clock = GameClock()
    assert clock.now() == 0

def test_clock_advance():
    clock = GameClock()
    clock.advance(500)
    assert clock.now() == 500
    clock.advance(1000)
    assert clock.now() == 1500

def test_clock_monostate_shared_state():
    clock1 = GameClock()
    clock2 = GameClock()
    
    clock1.advance(200)
    # Both instances must reflect the same shared tick counter
    assert clock2.now() == 200
    
    clock2.advance(300)
    assert clock1.now() == 500