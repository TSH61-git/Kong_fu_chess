# Home Screen shown between authentication and an actual match: a Play
# button that sends queue_join, a status line reflecting the matchmaking
# state, and a "no opponent found" message on queue_timeout. Deliberately
# has nothing to do with Renderer/GameSnapshot/animators — a lobby has no
# board state — but reuses gui_runner's letterbox/window-mapping helpers and
# the shared _WINDOW name so the same OpenCV window carries straight into
# gameplay with no visible resize.
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

import cv2
import numpy as np

from app_gateways.gui.gui_runner import _WINDOW, letterbox_transform, window_to_native
from app_gateways.gui.renderer import BOTTOM_BAR_H, TOP_BAR_H, _PANEL_WIDTH
from config import CELL_SIZE

SendEnvelope = Callable[[dict[str, Any]], Awaitable[None]]

_BOARD_CELLS = 8
_CANVAS_W = CELL_SIZE * _BOARD_CELLS + _PANEL_WIDTH
_CANVAS_H = TOP_BAR_H + CELL_SIZE * _BOARD_CELLS + BOTTOM_BAR_H

_BG_COLOR = (32, 30, 28, 255)          # BGRA
_BUTTON_COLOR = (60, 150, 60, 255)
_BUTTON_TEXT_COLOR = (255, 255, 255, 255)
_STATUS_COLOR = (220, 220, 220, 255)
_BUTTON_W, _BUTTON_H = 220, 70

_STATUS_TEXT = {
    "idle": "Click PLAY to find an opponent",
    "searching": "Searching for an opponent...",
    "timeout": "No opponent found - try again",
}


class LobbyRunner:
    IDLE = "idle"
    SEARCHING = "searching"
    TIMEOUT = "timeout"

    def __init__(
        self,
        send_envelope: SendEnvelope,
        match_ready: asyncio.Event,
        queue_timeout: asyncio.Event,
    ) -> None:
        self._send_envelope = send_envelope
        self._match_ready = match_ready
        self._queue_timeout = queue_timeout
        self._status = self.IDLE
        self._queued = False
        self._display_scale = 1.0
        self._display_offset = (0, 0)
        button_x = (_CANVAS_W - _BUTTON_W) // 2
        button_y = (_CANVAS_H - _BUTTON_H) // 2
        self._button_rect = (button_x, button_y, _BUTTON_W, _BUTTON_H)
        self._canvas = np.zeros((_CANVAS_H, _CANVAS_W, 4), dtype=np.uint8)

    async def run(self) -> None:
        cv2.namedWindow(_WINDOW, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(_WINDOW, self._on_mouse)
        cv2.resizeWindow(_WINDOW, _CANVAS_W, _CANVAS_H)

        while not self._match_ready.is_set():
            if self._queue_timeout.is_set():
                self._queue_timeout.clear()
                self._queued = False
                self._status = self.TIMEOUT

            self._draw()
            self._present()

            if cv2.waitKey(16) == 27 or self._is_window_closed():
                if self._queued:
                    await self._send_envelope({"type": "queue_cancel", "data": {}})
                return
            # Yields to the event loop each frame so the websocket receive
            # loop (and a pending queue_join/queue_cancel send) keeps running
            # concurrently, mirroring GuiRunner's own frame pacing.
            await asyncio.sleep(0)

    # ----------------------------------------------------------------- private

    def _is_window_closed(self) -> bool:
        try:
            return cv2.getWindowProperty(_WINDOW, cv2.WND_PROP_VISIBLE) < 1
        except cv2.error:
            return True

    def _on_mouse(self, event: int, x: int, y: int, flags: int, param) -> None:
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        cx, cy = window_to_native(
            x, y, self._display_scale, *self._display_offset, _CANVAS_W, _CANVAS_H,
        )
        if cx is None:
            return
        if self._status not in (self.IDLE, self.TIMEOUT):
            return  # already queued (SEARCHING) - Play clicks are ignored
        if not self._hit_button(cx, cy):
            return
        self._queued = True
        self._status = self.SEARCHING
        asyncio.create_task(self._send_envelope({"type": "queue_join", "data": {}}))

    def _hit_button(self, x: int, y: int) -> bool:
        bx, by, bw, bh = self._button_rect
        return bx <= x <= bx + bw and by <= y <= by + bh

    def _draw(self) -> None:
        self._canvas[:] = _BG_COLOR
        bx, by, bw, bh = self._button_rect
        cv2.rectangle(self._canvas, (bx, by), (bx + bw, by + bh), _BUTTON_COLOR, -1)
        label = "PLAY"
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        cv2.putText(
            self._canvas, label,
            (bx + (bw - text_w) // 2, by + (bh + text_h) // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, _BUTTON_TEXT_COLOR, 2, cv2.LINE_AA,
        )

        status = _STATUS_TEXT[self._status]
        (status_w, _), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)
        cv2.putText(
            self._canvas, status,
            ((_CANVAS_W - status_w) // 2, by + bh + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, _STATUS_COLOR, 1, cv2.LINE_AA,
        )

    def _present(self) -> None:
        try:
            _, _, window_w, window_h = cv2.getWindowImageRect(_WINDOW)
        except cv2.error:
            window_w, window_h = _CANVAS_W, _CANVAS_H
        if window_w <= 0 or window_h <= 0:
            window_w, window_h = _CANVAS_W, _CANVAS_H

        scale, offset_x, offset_y = letterbox_transform(_CANVAS_W, _CANVAS_H, window_w, window_h)
        self._display_scale = scale
        self._display_offset = (offset_x, offset_y)

        scaled_w = int(_CANVAS_W * scale)
        scaled_h = int(_CANVAS_H * scale)
        scaled = cv2.resize(self._canvas, (scaled_w, scaled_h), interpolation=cv2.INTER_AREA)

        frame = np.zeros((window_h, window_w, 4), dtype=np.uint8)
        frame[offset_y:offset_y + scaled_h, offset_x:offset_x + scaled_w] = scaled
        cv2.imshow(_WINDOW, frame)
