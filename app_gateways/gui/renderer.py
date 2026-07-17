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

_PANEL_WIDTH = 340

# Player bars, drawn above (Black / Player 2) and below (White / Player 1) the board.
TOP_BAR_H    = 64
BOTTOM_BAR_H = 64
_BAR_BG      = (32, 30, 28, 255)          # BGRA
_ACCENT_STRIP_W = 6
_CAPTURED_ICON   = 26
_CAPTURED_GAP    = 4
_CAPTURED_START_X = 260

_SCORE_ICON_SIZE = 32
_BAR_H           = 6
_COOLDOWN_MS     = 1000

_HISTORY_ROW_H       = 15
_HISTORY_WHITE_COLOR = (235, 235, 235, 255)   # BGRA
_HISTORY_BLACK_COLOR = (0, 165, 255, 255)     # BGRA — amber, readable on the dark panel

_PLAYER_NAME  = {Color.WHITE: "PLAYER 1", Color.BLACK: "PLAYER 2"}
_PLAYER_ACCENT = {Color.WHITE: _HISTORY_WHITE_COLOR, Color.BLACK: _HISTORY_BLACK_COLOR}


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
        scores: dict,
        history: list,
    ) -> None:
        cs         = self._cell_size
        board_px_w = snapshot.board_width  * cs
        board_px_h = snapshot.board_height * cs
        board_y0   = TOP_BAR_H
        total_w    = board_px_w + _PANEL_WIDTH
        total_h    = TOP_BAR_H + board_px_h + BOTTOM_BAR_H

        canvas.img = np.zeros((total_h, total_w, 4), dtype=np.uint8)

        self._draw_player_bar(
            canvas, 0, 0, board_px_w, TOP_BAR_H,
            color=Color.BLACK, score=scores[Color.BLACK], captured=captured[Color.BLACK],
        )
        self._draw_player_bar(
            canvas, 0, TOP_BAR_H + board_px_h, board_px_w, BOTTOM_BAR_H,
            color=Color.WHITE, score=scores[Color.WHITE], captured=captured[Color.WHITE],
        )

        self._draw_board(canvas, board_px_w, board_px_h, board_y0)
        self._draw_selection(canvas, snapshot, board_y0)
        self._draw_idle_pieces(canvas, snapshot, animators, motions, board_y0)
        self._draw_moving_pieces(canvas, animators, motions, board_y0)
        self._draw_cooldown_bars(canvas, cooldowns, snapshot, board_y0)
        self._draw_side_panel(canvas, history, board_px_w, total_h)

        if snapshot.game_over:
            self._draw_game_over(canvas, board_px_w, board_px_h, board_y0)

    # ----------------------------------------------------------------- private

    def _draw_player_bar(
        self,
        canvas: Img,
        x0: int, y0: int, width: int, height: int,
        color: Color, score: int, captured: list,
    ) -> None:
        cv2.rectangle(canvas.img, (x0, y0), (x0 + width, y0 + height), _BAR_BG, -1)
        accent = _PLAYER_ACCENT[color]
        cv2.rectangle(canvas.img, (x0, y0), (x0 + _ACCENT_STRIP_W, y0 + height), accent, -1)

        name_x = x0 + 20
        name_y = y0 + int(height * 0.42)
        canvas.put_text(_PLAYER_NAME[color], name_x, name_y, 0.6, accent, 2)

        score_y = y0 + int(height * 0.78)
        canvas.put_text(f"Score: {score}", name_x, score_y, 0.42, (200, 200, 200, 255), 1)

        self._draw_captured_row(canvas, captured, x0 + _CAPTURED_START_X, y0, height)

    def _draw_captured_row(
        self, canvas: Img, entries: list, start_x: int, bar_y0: int, bar_h: int
    ) -> None:
        s   = _CAPTURED_ICON
        y   = bar_y0 + (bar_h - s) // 2
        for i, entry in enumerate(entries):
            x = start_x + i * (s + _CAPTURED_GAP)
            if x + s > canvas.img.shape[1]:
                break
            icon = self._load_piece_icon(entry.piece, s)
            if icon is not None:
                self._blit(canvas, icon, x, y)

    def _draw_board(self, canvas: Img, w: int, h: int, y0: int) -> None:
        board_copy     = Img()
        board_copy.img = cv2.resize(
            self._board_base.img, (w, h), interpolation=cv2.INTER_AREA
        )
        if board_copy.img.shape[2] == 3:
            board_copy.img = cv2.cvtColor(board_copy.img, cv2.COLOR_BGR2BGRA)
        board_copy.draw_on(canvas, 0, y0)

    def _draw_selection(self, canvas: Img, snapshot: GameSnapshot, y0: int) -> None:
        if snapshot.selected_cell is None:
            return
        cs  = self._cell_size
        row = snapshot.selected_cell.row
        col = snapshot.selected_cell.col
        x, y = col * cs, y0 + row * cs
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
        y0: int,
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
                self._blit(canvas, anim.get_frame(), col * cs, y0 + row * cs)

    def _draw_moving_pieces(
        self,
        canvas: Img,
        animators: dict[tuple[int, int], PieceAnimator],
        motions: list[Motion],
        y0: int,
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
            py = y0 + int((sr + (dr - sr) * ratio) * cs)
            anim = animators.get((sr, sc))
            if anim is None:
                continue
            self._blit(canvas, anim.get_frame(), px, py)

    def _draw_cooldown_bars(
        self,
        canvas: Img,
        cooldowns: dict[Position, int],
        snapshot: GameSnapshot,
        y0: int,
    ) -> None:
        cs = self._cell_size
        for pos, remaining_ms in cooldowns.items():
            row, col = pos.row, pos.col
            if row >= snapshot.board_height or col >= snapshot.board_width:
                continue
            ratio = max(0.0, min(1.0, remaining_ms / _COOLDOWN_MS))
            x  = col * cs
            y  = y0 + row * cs + cs - _BAR_H
            bw = int(cs * ratio)
            # dark background
            cv2.rectangle(canvas.img, (x, y), (x + cs, y + _BAR_H), (40, 40, 40, 220), -1)
            # colored fill: green → red as cooldown drains
            g = int(200 * ratio)
            r = int(200 * (1.0 - ratio))
            cv2.rectangle(canvas.img, (x, y), (x + bw, y + _BAR_H), (0, g, r, 230), -1)

    def _draw_side_panel(
        self,
        canvas: Img,
        history: list,
        board_px_w: int,
        total_h: int,
    ) -> None:
        px = board_px_w
        cv2.rectangle(canvas.img, (px, 0), (px + _PANEL_WIDTH, total_h),
                      (25, 25, 25, 255), -1)
        cv2.line(canvas.img, (px, 0), (px, total_h), (70, 70, 70, 255), 1)
        self._draw_move_history_panel(canvas, history, px, 0, total_h)

    def _draw_move_history_panel(
        self,
        canvas: Img,
        history: list,
        px: int,
        y0: int,
        section_h: int,
    ) -> None:
        canvas.put_text("MOVE HISTORY", px + 8, y0 + 26, 0.55, (255, 255, 255, 255), 1)

        col_w    = _PANEL_WIDTH // 2
        white_x  = px + 8
        black_x  = px + col_w + 8
        header_y = y0 + 50
        canvas.put_text(_PLAYER_NAME[Color.WHITE], white_x, header_y, 0.42, _HISTORY_WHITE_COLOR, 1)
        canvas.put_text(_PLAYER_NAME[Color.BLACK], black_x, header_y, 0.42, _HISTORY_BLACK_COLOR, 1)
        cv2.line(canvas.img, (px + col_w, y0 + 38), (px + col_w, y0 + section_h),
                  (70, 70, 70, 255), 1)

        rows_top = header_y + 12
        max_rows = max(0, (y0 + section_h - rows_top) // _HISTORY_ROW_H)
        white_col = [r for r in history if r.color == Color.WHITE][-max_rows:]
        black_col = [r for r in history if r.color == Color.BLACK][-max_rows:]

        for i in range(max(len(white_col), len(black_col))):
            y = rows_top + i * _HISTORY_ROW_H
            if i < len(white_col):
                canvas.put_text(white_col[i].display_text(), white_x, y,
                                 0.34, _HISTORY_WHITE_COLOR, 1)
            if i < len(black_col):
                canvas.put_text(black_col[i].display_text(), black_x, y,
                                 0.34, _HISTORY_BLACK_COLOR, 1)

    def _load_piece_icon(self, piece, size: int = _SCORE_ICON_SIZE) -> Img | None:
        path = (get_piece_dir(piece, self._assets_dir)
                / "states" / "idle" / "sprites" / "1.png")
        if not path.exists():
            return None
        return Img().read(str(path), size=(size, size))

    def _draw_game_over(self, canvas: Img, w: int, h: int, y0: int) -> None:
        sub  = canvas.img[y0:y0 + h, :w]
        dark = np.zeros_like(sub)
        dark[:] = (0, 0, 0, 200)
        cv2.addWeighted(dark, 0.6, sub, 0.4, 0, sub)
        canvas.img[y0:y0 + h, :w] = sub
        canvas.put_text("GAME  OVER", w // 2 - 150, y0 + h // 2,
                        1.8, (255, 255, 255, 255), 3)

    @staticmethod
    def _blit(canvas: Img, sprite: Img, x: int, y: int) -> None:
        h, w = sprite.img.shape[:2]
        H, W = canvas.img.shape[:2]
        if x < 0 or y < 0 or x + w > W or y + h > H:
            return
        sprite.draw_on(canvas, x, y)
