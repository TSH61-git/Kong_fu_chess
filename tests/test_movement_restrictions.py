import pytest
from core.game_service import GameService
from core.game_clock import GameClock
from core.interfaces.i_movement_validator import IMovementValidator

class MockValidator(IMovementValidator):
    """A deterministic mock validator that approves any move shape/path."""
    def is_valid_move(self, board, piece, from_pos, to_pos) -> bool:
        return True

@pytest.fixture
def setup_game():
    GameClock.reset()
    clock = GameClock()
    validator = MockValidator()
    # 3x4 board layout for standard testing
    board = [
        ['wR', '.', '.', 'bR'],
        ['.',  '.', '.', '.'],
        ['.',  '.', '.', '.']
    ]
    game = GameService(board, validator, clock)
    return game, clock

def test_piece_movement_over_time(setup_game):
    game, clock = setup_game
    
    # Move wR from (0,0) to (0,2) -> distance = 2 cells -> travel time = 2000ms
    game.handle_click(0, 0)   # Select (col 0, row 0)
    game.handle_click(200, 0) # Target (col 2, row 0)
    
    # At 1000ms, the piece should still be at its source cell (Lazy Evaluation)
    game.handle_wait(1000)
    board_lines = game.get_board_lines()
    assert board_lines[0] == "wR . . bR"
    
    # Advance another 1000ms to reach the 2000ms arrival time
    game.handle_wait(1000)
    
    # The piece must now atomically land at its destination
    board_lines = game.get_board_lines()
    assert board_lines[0] == ". . wR bR"

def test_no_redirect_while_in_flight(setup_game):
    game, clock = setup_game
    
    # Start moving wR from (0,0) to (0,2)
    game.handle_click(0, 0)
    game.handle_click(200, 0)
    
    game.handle_wait(500) # Mid-flight
    
    # Attempting to re-select or re-route the in-flight piece must be ignored
    game.handle_click(0, 0)
    game.handle_click(100, 0) # Try to divert to (0,1)
    
    game.handle_wait(1500) # Wait until original 2000ms trip finishes
    board_lines = game.get_board_lines()
    # Piece must land at its original destination (0,2), not the diverted one
    assert board_lines[0] == ". . wR bR"

def test_opposite_colors_cannot_move_concurrently(setup_game):
    game, clock = setup_game
    
    # Dispatch white piece movement
    game.handle_click(0, 0)
    game.handle_click(200, 0)
    
    # Try to dispatch black piece immediately after while white is in-flight
    game.handle_click(300, 0) # Select bR at (0,3)
    game.handle_click(100, 0) # Target (0,1)
    
    game.handle_wait(2000)
    board_lines = game.get_board_lines()
    # White landed, but Black's move command should have been dropped entirely
    assert board_lines[0] == ". . wR bR"