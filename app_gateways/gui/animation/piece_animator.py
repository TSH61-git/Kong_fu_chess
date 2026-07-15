from __future__ import annotations
import pathlib

from app_gateways.gui.animation.anim_state import AnimState
from app_gateways.gui.animation.sprite_sheet import SpriteSheet, load_sheet
from app_gateways.gui.img import Img


class PieceAnimator:
    def __init__(self, piece_dir: pathlib.Path, cell_size: int) -> None:
        self._sheets: dict[AnimState, SpriteSheet] = {
            state: load_sheet(piece_dir / "states" / state.value, cell_size)
            for state in AnimState
        }
        self._state = AnimState.IDLE
        self._frame_index = 0
        self._elapsed_ms = 0.0

    def transition_to(self, new_state: AnimState) -> None:
        if new_state == self._state:
            return
        self._state = new_state
        self._frame_index = 0
        self._elapsed_ms = 0.0

    def update(self, delta_ms: float) -> None:
        sheet = self._sheets[self._state]
        self._elapsed_ms += delta_ms
        while self._elapsed_ms >= sheet.frame_duration_ms:
            self._elapsed_ms -= sheet.frame_duration_ms
            self._frame_index += 1
            if self._frame_index >= len(sheet.frames):
                if sheet.is_loop:
                    self._frame_index = 0
                else:
                    self._frame_index = len(sheet.frames) - 1
                    self.transition_to(sheet.next_state)
                    return

    def get_frame(self) -> Img:
        return self._sheets[self._state].frames[self._frame_index]

    @property
    def current_state(self) -> AnimState:
        return self._state

    @property
    def rest_progress(self) -> float:
        """1.0 = just entered rest, 0.0 = about to finish. Used for cooldown bar."""
        sheet = self._sheets[self._state]
        if not sheet.frames:
            return 0.0
        total_frames = len(sheet.frames)
        remaining    = total_frames - 1 - self._frame_index
        return remaining / max(total_frames - 1, 1)
