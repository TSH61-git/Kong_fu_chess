import sys
import pathlib
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).parent))

try:
    from app_gateways.gui.translator import standard_board
    from app_gateways.gui.bootstrap import bootstrap_gui

    r = bootstrap_gui(board=standard_board())
    r.run()

except Exception:
    traceback.print_exc()
    input("Press Enter to close...")
