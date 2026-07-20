from __future__ import annotations
import asyncio
import pathlib
import time

import cv2
import numpy as np

from app_gateways.gui.img import Img
from app_gateways.gui.animation.anim_state import AnimState
from app_gateways.gui.animation.piece_animator import PieceAnimator
from app_gateways.gui.renderer import Renderer, TOP_BAR_H
from app_gateways.text_cli.bootstrap import GameRuntime
from app_gateways.gui.translator import piece_dir
from chess_engine.model.piece import Color, PieceState
from chess_engine.realtime.motion import Motion
from config import CELL_SIZE

_ASSETS_DIR = pathlib.Path(__file__).parent / "assets"
_WINDOW     = "Kong Fu Chess"
_TARGET_FPS = 60


def letterbox_transform(
    native_w: int, native_h: int, window_w: int, window_h: int
) -> tuple[float, int, int]:
    """Uniform scale + centering offsets to fit native_w x native_h into
    window_w x window_h while preserving aspect ratio (letterboxed)."""
    window_w = max(1, window_w)
    window_h = max(1, window_h)
    scale = min(window_w / native_w, window_h / native_h)
    scaled_w = int(native_w * scale)
    scaled_h = int(native_h * scale)
    offset_x = (window_w - scaled_w) // 2
    offset_y = (window_h - scaled_h) // 2
    return scale, offset_x, offset_y


def window_to_native(
    x: int, y: int,
    scale: float, offset_x: int, offset_y: int,
    native_w: int, native_h: int,
) -> tuple[int | None, int | None]:
    """Invert letterbox_transform: map a window-space point back to native
    canvas pixel space, or (None, None) if it falls in the letterbox bars."""
    nx = (x - offset_x) / scale
    ny = (y - offset_y) / scale
    if nx < 0 or ny < 0 or nx >= native_w or ny >= native_h:
        return None, None
    return int(nx), int(ny)


class GuiRunner:
    def __init__(self, runtime: GameRuntime) -> None:
        self._runtime  = runtime
        self._canvas   = Img()
        self._animators: dict[tuple[int, int], PieceAnimator] = {}
        self._prev_by_source: dict[tuple[int, int], Motion] = {}
        # Current native-canvas -> window letterbox transform, updated each
        # frame in _present() and inverted by _on_mouse() to map clicks back.
        self._display_scale   = 1.0
        self._display_offset  = (0, 0)
        board_img      = Img()
        board_img.img  = cv2.imdecode(
            np.fromfile(str(_ASSETS_DIR / "board.png"), dtype=np.uint8),
            cv2.IMREAD_UNCHANGED,
        )
        self._renderer = Renderer(
            board_img  = board_img,
            cell_size  = CELL_SIZE,
            assets_dir = _ASSETS_DIR,
        )

    # ------------------------------------------------------------------ public

    async def run(self) -> None:
        cv2.namedWindow(_WINDOW, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(_WINDOW, self._on_mouse)
        self._window_sized = False

        # init animators from starting board
        board = self._runtime.board
        for row in range(board.rows):
            for col in range(board.cols):
                from chess_engine.model.position import Position
                p = board.get(Position(row, col))
                if p is not None:
                    self._animators[(row, col)] = self._make_animator(p)

        prev_time = time.perf_counter()
        frame_ms  = 1000.0 / _TARGET_FPS

        while True:
            now       = time.perf_counter()
            delta_ms  = (now - prev_time) * 1000.0
            prev_time = now

            self._runtime.engine.advance_time(int(delta_ms))

            snapshot  = self._runtime.engine.get_snapshot(
                self._runtime.controller.selected_cell
            )
            motions   = self._runtime.arbiter.get_active_motions()
            cooldowns = self._runtime.arbiter.get_cooldowns()

            self._sync_animators(motions)
            self._update_animators(delta_ms)

            self._renderer.draw(
                self._canvas, snapshot, self._animators, motions, cooldowns,
                {
                    Color.WHITE: self._runtime.engine.get_captured(Color.WHITE),
                    Color.BLACK: self._runtime.engine.get_captured(Color.BLACK),
                },
                self._runtime.engine.get_scores(),
                self._runtime.engine.history_entries(),
            )

            if not self._window_sized:
                h, w = self._canvas.img.shape[:2]
                cv2.resizeWindow(_WINDOW, w, h)
                self._window_sized = True

            self._present()
            wait = max(1, int(frame_ms - (time.perf_counter() - now) * 1000))
            if cv2.waitKey(wait) == 27:
                break
            # Yields to the event loop once per frame so a concurrently
            # running coroutine (e.g. a network client's receive loop) gets
            # to run between frames — cv2.waitKey itself already paces us,
            # this just stops that pacing from starving the rest of asyncio.
            await asyncio.sleep(0)

        cv2.destroyAllWindows()

    # ----------------------------------------------------------------- private

    def _present(self) -> None:
        """Letterbox the native-resolution canvas to fit the current window
        size ourselves, so the image handed to imshow always exactly fills
        the window (scale-by-1 as far as the backend is concerned) — this
        keeps the mouse callback's coordinate space unambiguous regardless
        of how the window has been resized.
        """
        native_h, native_w = self._canvas.img.shape[:2]
        try:
            _, _, window_w, window_h = cv2.getWindowImageRect(_WINDOW)
        except cv2.error:
            window_w, window_h = native_w, native_h

        if window_w <= 0 or window_h <= 0:
            window_w, window_h = native_w, native_h

        scale, offset_x, offset_y = letterbox_transform(
            native_w, native_h, window_w, window_h
        )
        self._display_scale  = scale
        self._display_offset = (offset_x, offset_y)

        scaled_w = int(native_w * scale)
        scaled_h = int(native_h * scale)
        scaled = cv2.resize(self._canvas.img, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

        frame = np.zeros((window_h, window_w, self._canvas.img.shape[2]), dtype=np.uint8)
        frame[offset_y:offset_y + scaled_h, offset_x:offset_x + scaled_w] = scaled

        cv2.imshow(_WINDOW, frame)

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if self._canvas.img is None:
            return
        native_h, native_w = self._canvas.img.shape[:2]
        offset_x, offset_y = self._display_offset
        cx, cy = window_to_native(
            x, y, self._display_scale, offset_x, offset_y, native_w, native_h
        )
        if cx is None:
            return
        self._runtime.controller.click(cx, cy - TOP_BAR_H)

    def _make_animator(self, piece) -> PieceAnimator:
        return PieceAnimator(piece_dir(piece, _ASSETS_DIR), CELL_SIZE)

    def _sync_animators(self, motions: list[Motion]) -> None:
        board      = self._runtime.board
        by_source  = {(m.source.row, m.source.col): m for m in motions}
        by_dest    = {(m.destination.row, m.destination.col): m for m in motions}

        from chess_engine.model.position import Position

        # 0. Motions that were active last frame but finished this frame:
        #    relocate their (still MOVE/JUMP-state) animator from the source
        #    cell to the destination cell, so it can transition into rest.
        #    A motion can "finish" two different ways: it actually arrived,
        #    or it was captured mid-route (e.g. by a defending jump) and
        #    never reached its destination at all. Only relocate the
        #    animator when the piece now standing at the destination is
        #    still this motion's own piece (same color) — otherwise the
        #    motion's piece was captured, so its animator must be dropped
        #    instead of overwriting the actual survivor's animator there.
        for key, prev_motion in self._prev_by_source.items():
            if key in by_source:
                continue
            anim = self._animators.pop(key, None)
            if anim is None:
                continue
            dest_key = (prev_motion.destination.row, prev_motion.destination.col)
            dest_piece = board.get(Position(*dest_key))
            if dest_piece is not None and dest_piece.color == prev_motion.piece.color:
                if dest_piece.piece_type != prev_motion.piece.piece_type:
                    # pawn promoted on arrival — the old animator was built
                    # from the pawn's sprite set, so it must be rebuilt from
                    # the promoted piece (e.g. queen) instead of reused.
                    # Seed it in MOVE so it flows into the same rest
                    # transition as any other arriving piece this frame.
                    new_anim = self._make_animator(dest_piece)
                    new_anim.transition_to(AnimState.MOVE)
                    self._animators[dest_key] = new_anim
                else:
                    self._animators[dest_key] = anim
            # else: this motion's piece was captured mid-route — its
            # animator is discarded, leaving the survivor's animator
            # (already correctly keyed at dest_key) untouched.
        self._prev_by_source = by_source

        # 1. For every active motion — ensure animator exists at source key
        for (sr, sc), motion in by_source.items():
            if (sr, sc) not in self._animators:
                self._animators[(sr, sc)] = self._make_animator(motion.piece)
            anim     = self._animators[(sr, sc)]
            is_jump  = motion.source == motion.destination
            target   = AnimState.JUMP if is_jump else AnimState.MOVE
            if anim.current_state not in (AnimState.MOVE, AnimState.JUMP):
                anim.transition_to(target)

        # 2. For every cell on the board — sync idle animators
        for row in range(board.rows):
            for col in range(board.cols):
                key   = (row, col)
                piece = board.get(Position(row, col))

                if key in by_source:
                    continue  # handled above

                if piece is None:
                    # cell is empty and no motion — remove stale animator
                    if key in self._animators and key not in by_dest:
                        del self._animators[key]
                    continue

                # piece is sitting idle on this cell
                if key not in self._animators:
                    self._animators[key] = self._make_animator(piece)

                anim = self._animators[key]

                # piece just arrived (was in motion, now idle) → long_rest
                if anim.current_state in (AnimState.MOVE, AnimState.JUMP):
                    rest = (AnimState.SHORT_REST
                            if anim.current_state == AnimState.JUMP
                            else AnimState.LONG_REST)
                    anim.transition_to(rest)

                # piece state is MOVING but no motion entry — stale, reset
                if piece.state == PieceState.IDLE and anim.current_state in (
                    AnimState.MOVE, AnimState.JUMP
                ):
                    anim.transition_to(AnimState.LONG_REST)

    def _update_animators(self, delta_ms: float) -> None:
        for anim in self._animators.values():
            anim.update(delta_ms)