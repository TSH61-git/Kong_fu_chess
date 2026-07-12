# Git Repository URL: https://github.com/TSH61-git/Kong_fu_chess

"""Console entry point for the refactored Kung Fu Chess application."""
from __future__ import annotations

from app_factory import bootstrap_game_system


if __name__ == "__main__":
    runner = bootstrap_game_system()
    runner.run()
