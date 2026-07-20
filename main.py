# Git Repository URL: https://github.com/TSH61-git/Kong_fu_chess

from __future__ import annotations
import asyncio
import sys

if __name__ == "__main__":
    if "--gui" in sys.argv:
        from app_gateways.gui.bootstrap import bootstrap_gui
        asyncio.run(bootstrap_gui().run())
    else:
        from app_gateways.text_cli.bootstrap import bootstrap_game_system
        bootstrap_game_system().run()
