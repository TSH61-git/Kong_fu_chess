from __future__ import annotations
import json
import pathlib
from dataclasses import dataclass, field

from app_gateways.gui.animation.anim_state import AnimState
from app_gateways.gui.img import Img


@dataclass
class SpriteSheet:
    frames: list[Img]
    fps: float
    is_loop: bool
    next_state: AnimState

    @property
    def frame_duration_ms(self) -> float:
        return 1000.0 / self.fps if self.fps > 0 else 1000.0


def load_sheet(state_dir: pathlib.Path, cell_size: int) -> SpriteSheet:
    with open(state_dir / "config.json") as f:
        cfg = json.load(f)

    sprites_dir = state_dir / "sprites"
    png_files = sorted(sprites_dir.glob("*.png"), key=lambda p: int(p.stem))
    frames = [Img().read(str(p), size=(cell_size, cell_size)) for p in png_files]

    next_state = AnimState(cfg["physics"]["next_state_when_finished"])
    return SpriteSheet(
        frames=frames,
        fps=cfg["graphics"]["frames_per_sec"],
        is_loop=cfg["graphics"]["is_loop"],
        next_state=next_state,
    )
