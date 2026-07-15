from __future__ import annotations
import pathlib
import time

import cv2
import numpy as np

from app_gateways.gui.img import Img
from app_gateways.gui.animation.anim_state import AnimState
from app_gateways.gui.animation.piece_animator import PieceAnimator
from app_gateways.gui.translator import piece_dir as get_piece_dir
from chess_engine.engine.helpers.snapshot_models import GameSnapshot
from chess_engine.model.piece import Color
from chess_engine.model.position import Position
from chess_engine.realtime.motion import Motion

_PANEL_WIDTH     = 220
_SCORE_ICON_SIZE = 32
_BAR_H           = 6
_COOLDOWN_MS     = 1000


class Renderer:
    def __init__(self, board_img: Img, cell_size: int, assets_dir: pathlib.Path) -> None:
        self._board_base = board_img
        self._cell_size  = cell_size
        self._assets_dir = assets_dir

    # ------------------------------------------------------------------ public

    def draw(
        self,
        canvas: Img,
        snapshot: GameSnapshot,
        animators: dict[tuple[int, int], PieceAnimator],
        motions: list[Motion],
        cooldowns: dict[Position, int],
        captured: dict,
    ) -> None:
        cs         = self._cell_size
        board_px_w = snapshot.board_width  * cs
        board_px_h = snapshot.board_height * cs
        total_w    = board_px_w + _PANEL_WIDTH

        canvas.img = np.zeros((board_px_h, total_w, 4), dtype=np.uint8)

        self._draw_board(canvas, board_px_w, board_px_h)
        self._draw_selection(canvas, snapshot)
        self._draw_idle_pieces(canvas, snapshot, animators, motions)
        self._draw_moving_pieces(canvas, animators, motions)
        self._draw_cooldown_bars(canvas, cooldowns, snapshot)
        self._draw_score_panel(canvas, captured, board_px_w, board_px_h)

        if snapshot.game_over:
            self._draw_game_over(canvas, board_px_w, board_px_h)

    # ----------------------------------------------------------------- private

    def _draw_board(self, canvas: Img, w: int, h: int) -> None:
        board_copy     = Img()
        board_copy.img = cv2.resize(
            self._board_base.img, (w, h), interpolation=cv2.INTER_AREA
        )
        if board_copy.img.shape[2] == 3:
            board_copy.img = cv2.cvtColor(board_copy.img, cv2.COLOR_BGR2BGRA)
        board_copy.draw_on(canvas, 0, 0)

    def _draw_selection(self, canvas: Img, snapshot: GameSnapshot) -> None:
        if snapshot.selected_cell is None:
            return
        cs  = self._cell_size
        row = snapshot.selected_cell.row
        col = snapshot.selected_cell.col
        x, y = col * cs, row * cs
        sub = canvas.img[y:y + cs, x:x + cs]
        highlight = np.zeros_like(sub)
        highlight[:] = (0, 210, 210, 255)
        cv2.addWeighted(highlight, 0.4, sub, 0.6, 0, sub)
        canvas.img[y:y + cs, x:x + cs] = sub

    def _draw_idle_pieces(
        self,
        canvas: Img,
        snapshot: GameSnapshot,
        animators: dict[tuple[int, int], PieceAnimator],
        motions: list[Motion],
    ) -> None:
        moving_sources = {(m.source.row, m.source.col) for m in motions}
        cs = self._cell_size
        for row in range(snapshot.board_height):
            for col in range(snapshot.board_width):
                if (row, col) in moving_sources:
                    continue
                if snapshot.board_grid[row][col] is None:
                    continue
                anim = animators.get((row, col))
                if anim is None:
                    continue
                self._blit(canvas, anim.get_frame(), col * cs, row * cs)

    def _draw_moving_pieces(
        self,
        canvas: Img,
        animators: dict[tuple[int, int], PieceAnimator],
        motions: list[Motion],
    ) -> None:
        cs = self._cell_size
        for motion in motions:
            sr, sc = motion.source.row, motion.source.col
            dr, dc = motion.destination.row, motion.destination.col
            ratio  = (
                motion.elapsed_ms / motion.duration_ms
                if motion.duration_ms > 0 else 1.0
            )
            ratio = max(0.0, min(1.0, ratio))
            px = int((sc + (dc - sc) * ratio) * cs)
            py = int((sr + (dr - sr) * ratio) * cs)
            anim = animators.get((sr, sc))
            if anim is None:
                continue
            self._blit(canvas, anim.get_frame(), px, py)

    def _draw_cooldown_bars(
        self,
        canvas: Img,
        cooldowns: dict[Position, int],
        snapshot: GameSnapshot,
    ) -> None:
        cs = self._cell_size
        for pos, remaining_ms in cooldowns.items():
            row, col = pos.row, pos.col
            if row >= snapshot.board_height or col >= snapshot.board_width:
                continue
            ratio = max(0.0, min(1.0, remaining_ms / _COOLDOWN_MS))
            x  = col * cs
            y  = row * cs + cs - _BAR_H
            bw = int(cs * ratio)
            # dark background
            cv2.rectangle(canvas.img, (x, y), (x + cs, y + _BAR_H), (40, 40, 40, 220), -1)
            # colored fill: green → red as cooldown drains
            g = int(200 * ratio)
            r = int(200 * (1.0 - ratio))
            cv2.rectangle(canvas.img, (x, y), (x + bw, y + _BAR_H), (0, g, r, 230), -1)

    def _draw_score_panel(
        self,
        canvas: Img,
        captured: dict,
        board_px_w: int,
        board_px_h: int,
    ) -> None:
        px = board_px_w
        cv2.rectangle(canvas.img, (px, 0), (px + _PANEL_WIDTH, board_px_h),
                      (25, 25, 25, 255), -1)

        canvas.put_text("White captured:", px + 8, 22, 0.5, (255, 255, 255, 255), 1)
        self._draw_captured_list(canvas, captured[Color.WHITE], px + 8, 36)

        mid = board_px_h // 2
        cv2.line(canvas.img, (px, mid), (px + _PANEL_WIDTH, mid), (70, 70, 70, 255), 1)

        canvas.put_text("Black captured:", px + 8, mid + 22, 0.5, (200, 200, 200, 255), 1)
        self._draw_captured_list(canvas, captured[Color.BLACK], px + 8, mid + 36)

    def _draw_captured_list(
        self, canvas: Img, entries: list, start_x: int, start_y: int
    ) -> None:
        s   = _SCORE_ICON_SIZE
        now = time.time()
        for i, entry in enumerate(entries):
            ci = i % 5
            ri = i // 5
            x  = start_x + ci * (s + 2)
            y  = start_y + ri * (s + 14)
            icon = self._load_piece_icon(entry.piece)
            if icon is not None:
                self._blit(canvas, icon, x, y)
            elapsed = int(now - entry.timestamp)
            label   = f"{elapsed}s" if elapsed < 60 else f"{elapsed // 60}m"
            canvas.put_text(label, x, y + s + 10, 0.3, (160, 160, 160, 255), 1)

    def _load_piece_icon(self, piece) -> Img | None:
        path = (get_piece_dir(piece, self._assets_dir)
                / "states" / "idle" / "sprites" / "1.png")
        if not path.exists():
            return None
        return Img().read(str(path), size=(_SCORE_ICON_SIZE, _SCORE_ICON_SIZE))

    def _draw_game_over(self, canvas: Img, w: int, h: int) -> None:
        sub  = canvas.img[:h, :w]
        dark = np.zeros_like(sub)
        dark[:] = (0, 0, 0, 200)
        cv2.addWeighted(dark, 0.6, sub, 0.4, 0, sub)
        canvas.img[:h, :w] = sub
        canvas.put_text("GAME  OVER", w // 2 - 150, h // 2,
                        1.8, (255, 255, 255, 255), 3)

    @staticmethod
    def _blit(canvas: Img, sprite: Img, x: int, y: int) -> None:
        h, w = sprite.img.shape[:2]
        H, W = canvas.img.shape[:2]
        if x < 0 or y < 0 or x + w > W or y + h > H:
            return
        sprite.draw_on(canvas, x, y)
