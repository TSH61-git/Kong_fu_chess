import pytest
# Updated imports to match your project's directory hierarchy
from core.game_service import GameService
from core.game_clock import GameClock
from core.interfaces.i_movement_validator import IMovementValidator

class MockValidator(IMovementValidator):
    def is_valid_move(self, board, piece, from_pos, to_pos) -> bool:
        return True

@pytest.fixture
def setup_game_over_scenario():
    GameClock.reset()
    clock = GameClock()
    validator = MockValidator()
    # wR ready to capture bK, bR sits on row 1
    board = [
        ['wR', '.', 'bK'],
        ['bR', '.', '.']
    ]
    game = GameService(board, validator, clock)
    return game, clock

def test_king_capture_triggers_game_over(setup_game_over_scenario):
    game, clock = setup_game_over_scenario
    
    # wR captures bK at (0,2) -> distance = 2 cells -> 2000ms travel
    game.handle_click(0, 0)
    game.handle_click(200, 0)
    
    game.handle_wait(2000)
    board_lines = game.get_board_lines()
    
    # King must be replaced by the winning piece
    assert board_lines[0] == ". . wR"
    assert game._game_over is True

def test_input_blocked_after_game_over(setup_game_over_scenario):
    game, clock = setup_game_over_scenario
    
    # Terminate the game by capturing the king
    game.handle_click(0, 0)
    game.handle_click(200, 0)
    game.handle_wait(2000)
    
    # Attempt to move the remaining bR from (1,0) to (1,1) after Game Over
    game.handle_click(0, 100)
    game.handle_click(100, 100)
    
    game.handle_wait(1000)
    board_lines = game.get_board_lines()
    
    # The board must remain completely frozen as it was at game over time
    assert board_lines[1] == "bR . ."