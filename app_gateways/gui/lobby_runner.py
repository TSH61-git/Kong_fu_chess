# Home Screen shown between authentication and an actual match: a Play
# button that sends queue_join, a Room button that opens a Create/Join modal
# for custom rooms, a status line reflecting the matchmaking state, and a
# "no opponent found" message on queue_timeout. Deliberately has nothing to
# do with Renderer/GameSnapshot/animators — a lobby has no board state — but
# reuses gui_runner's letterbox/window-mapping helpers and the shared
# _WINDOW name so the same OpenCV window carries straight into gameplay with
# no visible resize.
from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Optional

import cv2
import numpy as np

from app_gateways.gui.gui_runner import _WINDOW, letterbox_transform, window_to_native
from app_gateways.gui.renderer import BOTTOM_BAR_H, TOP_BAR_H, _PANEL_WIDTH
from config import CELL_SIZE

SendEnvelope = Callable[[dict[str, Any]], Awaitable[None]]
SendRequest = Callable[[dict[str, Any]], Awaitable[dict]]

_BOARD_CELLS = 8
_CANVAS_W = CELL_SIZE * _BOARD_CELLS + _PANEL_WIDTH
_CANVAS_H = TOP_BAR_H + CELL_SIZE * _BOARD_CELLS + BOTTOM_BAR_H

_BG_COLOR = (32, 30, 28, 255)          # BGRA
_BUTTON_COLOR = (60, 150, 60, 255)
_BUTTON_TEXT_COLOR = (255, 255, 255, 255)
_STATUS_COLOR = (220, 220, 220, 255)
_BUTTON_W, _BUTTON_H = 220, 70
_BUTTON_GAP = 20

_STATUS_TEXT = {
    "idle": "Click PLAY to find an opponent",
    "searching": "Searching for an opponent...",
    "timeout": "No opponent found - try again",
}

# Mirrors server/rooms/codes.py's alphabet — kept as a local literal rather
# than importing across the client/server boundary for one constant.
_ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
_MODAL_INPUT_MAX_LEN = 12  # covers both a 6-char generated join code and a custom create alias (up to 12)

_MODAL_W, _MODAL_H = 420, 220
_MODAL_OVERLAY_COLOR = (0, 0, 0, 160)
_MODAL_PANEL_COLOR = (48, 46, 44, 255)
_MODAL_BOX_COLOR = (20, 20, 20, 255)
_MODAL_TEXT_COLOR = (255, 255, 255, 255)
_MODAL_ERROR_COLOR = (0, 90, 220, 255)   # BGRA amber/red-ish, readable on dark panel
_MODAL_BUTTON_COLOR = (70, 70, 70, 255)
_MODAL_BUTTON_W, _MODAL_BUTTON_H = 110, 50


class LobbyRunner:
    IDLE = "idle"
    SEARCHING = "searching"
    TIMEOUT = "timeout"

    def __init__(
        self,
        send_envelope: SendEnvelope,
        send_and_wait: SendRequest,
        match_ready: asyncio.Event,
        queue_timeout: asyncio.Event,
    ) -> None:
        self._send_envelope = send_envelope
        self._send_and_wait = send_and_wait
        self._match_ready = match_ready
        self._queue_timeout = queue_timeout
        self._status = self.IDLE
        self._queued = False
        self._display_scale = 1.0
        self._display_offset = (0, 0)

        button_x = (_CANVAS_W - _BUTTON_W) // 2
        button_y = (_CANVAS_H - _BUTTON_H) // 2
        self._button_rect = (button_x, button_y, _BUTTON_W, _BUTTON_H)
        self._room_button_rect = (button_x, button_y + _BUTTON_H + _BUTTON_GAP, _BUTTON_W, _BUTTON_H)

        self._modal_open = False
        self._modal_text = ""
        self._modal_error: Optional[str] = None
        self._room_result: Optional[dict] = None
        # Distinct from match_ready: that event is also set externally by
        # DevClient whenever a broadcast/match_ready arrives (the ordinary
        # matchmaking signal) — including, incidentally, when a 2nd player
        # joins THIS room, since a seated Black also receives that broadcast.
        # Without its own event, run()'s loop could see match_ready flip on
        # due to that incidental broadcast and exit before the room_join/
        # room_create ack itself (which carries the actual room_id/role) has
        # been processed, returning a None result. See _handle_room_reply.
        self._room_ready = asyncio.Event()

        panel_x = (_CANVAS_W - _MODAL_W) // 2
        panel_y = (_CANVAS_H - _MODAL_H) // 2
        self._modal_panel_rect = (panel_x, panel_y, _MODAL_W, _MODAL_H)
        self._modal_box_rect = (panel_x + 30, panel_y + 55, _MODAL_W - 60, 50)

        row_w = 3 * _MODAL_BUTTON_W + 2 * _BUTTON_GAP
        row_x = panel_x + (_MODAL_W - row_w) // 2
        row_y = panel_y + 135
        self._create_button_rect = (row_x, row_y, _MODAL_BUTTON_W, _MODAL_BUTTON_H)
        self._join_button_rect = (row_x + _MODAL_BUTTON_W + _BUTTON_GAP, row_y, _MODAL_BUTTON_W, _MODAL_BUTTON_H)
        self._cancel_button_rect = (
            row_x + 2 * (_MODAL_BUTTON_W + _BUTTON_GAP), row_y, _MODAL_BUTTON_W, _MODAL_BUTTON_H,
        )

        self._canvas = np.zeros((_CANVAS_H, _CANVAS_W, 4), dtype=np.uint8)

    async def run(self) -> Optional[dict]:
        cv2.namedWindow(_WINDOW, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(_WINDOW, self._on_mouse)
        cv2.resizeWindow(_WINDOW, _CANVAS_W, _CANVAS_H)

        while not self._room_ready.is_set() and not (self._queued and self._match_ready.is_set()):
            if self._queue_timeout.is_set():
                self._queue_timeout.clear()
                self._queued = False
                self._status = self.TIMEOUT

            self._draw()
            self._present()

            key = cv2.waitKey(16)
            if self._is_window_closed():
                if self._queued:
                    await self._send_envelope({"type": "queue_cancel", "data": {}})
                return None
            if self._modal_open:
                self._handle_modal_key(key)
            elif key == 27:
                if self._queued:
                    await self._send_envelope({"type": "queue_cancel", "data": {}})
                return None
            # Yields to the event loop each frame so the websocket receive
            # loop (and a pending queue_join/queue_cancel/room send) keeps
            # running concurrently, mirroring GuiRunner's own frame pacing.
            await asyncio.sleep(0)

        return self._room_result

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

        if self._modal_open:
            self._handle_modal_click(cx, cy)
            return

        if self._status not in (self.IDLE, self.TIMEOUT):
            return  # already queued (SEARCHING) - Play/Room clicks are ignored

        if self._hit_rect(self._button_rect, cx, cy):
            self._queued = True
            self._status = self.SEARCHING
            asyncio.create_task(self._send_envelope({"type": "queue_join", "data": {}}))
        elif self._hit_rect(self._room_button_rect, cx, cy):
            self._modal_open = True
            self._modal_text = ""
            self._modal_error = None

    def _handle_modal_click(self, x: int, y: int) -> None:
        if self._hit_rect(self._create_button_rect, x, y):
            asyncio.create_task(self._do_room_create())
        elif self._hit_rect(self._join_button_rect, x, y):
            if self._modal_text:
                asyncio.create_task(self._do_room_join(self._modal_text))
        elif self._hit_rect(self._cancel_button_rect, x, y):
            self._modal_open = False
            self._modal_text = ""
            self._modal_error = None

    def _handle_modal_key(self, key: int) -> None:
        if key == 27:  # Esc closes just the modal, not the whole lobby
            self._modal_open = False
            self._modal_text = ""
            self._modal_error = None
        elif key in (8, 127):  # Backspace
            self._modal_text = self._modal_text[:-1]
        elif 32 <= key < 127 and len(self._modal_text) < _MODAL_INPUT_MAX_LEN:
            ch = chr(key).upper()
            if ch in _ROOM_ALPHABET:
                self._modal_text += ch

    async def _do_room_create(self) -> None:
        # Whatever is typed in the shared code/name box is sent as the
        # requested alias; an empty string tells the server to auto-generate
        # a code instead (see server/rooms/commands.py's handle_room_create).
        reply = await self._send_and_wait({"type": "room_create", "data": {"room_id": self._modal_text}})
        self._handle_room_reply(reply)

    async def _do_room_join(self, code: str) -> None:
        reply = await self._send_and_wait({"type": "room_join", "data": {"room_id": code}})
        self._handle_room_reply(reply)

    def _handle_room_reply(self, reply: dict) -> None:
        if reply.get("type") == "ack":
            self._room_result = reply["data"]
            self._modal_open = False
            self._room_ready.set()
        else:
            self._modal_error = reply.get("message") or reply.get("code", "error")

    @staticmethod
    def _hit_rect(rect: tuple[int, int, int, int], x: int, y: int) -> bool:
        rx, ry, rw, rh = rect
        return rx <= x <= rx + rw and ry <= y <= ry + rh

    def _draw(self) -> None:
        self._canvas[:] = _BG_COLOR
        self._draw_button(self._button_rect, "PLAY")
        self._draw_button(self._room_button_rect, "ROOM")

        status = _STATUS_TEXT[self._status]
        (status_w, _), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1)
        by = self._room_button_rect[1] + _BUTTON_H
        cv2.putText(
            self._canvas, status,
            ((_CANVAS_W - status_w) // 2, by + 40),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, _STATUS_COLOR, 1, cv2.LINE_AA,
        )

        if self._modal_open:
            self._draw_modal()

    def _draw_button(self, rect: tuple[int, int, int, int], label: str) -> None:
        bx, by, bw, bh = rect
        cv2.rectangle(self._canvas, (bx, by), (bx + bw, by + bh), _BUTTON_COLOR, -1)
        (text_w, text_h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)
        cv2.putText(
            self._canvas, label,
            (bx + (bw - text_w) // 2, by + (bh + text_h) // 2),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, _BUTTON_TEXT_COLOR, 2, cv2.LINE_AA,
        )

    def _draw_modal(self) -> None:
        overlay = self._canvas.copy()
        overlay[:] = _MODAL_OVERLAY_COLOR
        cv2.addWeighted(overlay, 0.6, self._canvas, 0.4, 0, self._canvas)

        px, py, pw, ph = self._modal_panel_rect
        cv2.rectangle(self._canvas, (px, py), (px + pw, py + ph), _MODAL_PANEL_COLOR, -1)
        cv2.putText(
            self._canvas, "Room Code (Join) / Name (Create, optional)", (px + 20, py + 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, _MODAL_TEXT_COLOR, 1, cv2.LINE_AA,
        )

        bx, by, bw, bh = self._modal_box_rect
        cv2.rectangle(self._canvas, (bx, by), (bx + bw, by + bh), _MODAL_BOX_COLOR, -1)
        cv2.putText(
            self._canvas, self._modal_text + "_", (bx + 12, by + bh - 16),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, _MODAL_TEXT_COLOR, 2, cv2.LINE_AA,
        )

        for rect, label in (
            (self._create_button_rect, "Create"),
            (self._join_button_rect, "Join"),
            (self._cancel_button_rect, "Cancel"),
        ):
            rx, ry, rw, rh = rect
            cv2.rectangle(self._canvas, (rx, ry), (rx + rw, ry + rh), _MODAL_BUTTON_COLOR, -1)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.putText(
                self._canvas, label,
                (rx + (rw - tw) // 2, ry + (rh + th) // 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, _MODAL_TEXT_COLOR, 1, cv2.LINE_AA,
            )

        if self._modal_error:
            (ew, _), _ = cv2.getTextSize(self._modal_error, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.putText(
                self._canvas, self._modal_error,
                (px + (pw - ew) // 2, by + bh + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, _MODAL_ERROR_COLOR, 1, cv2.LINE_AA,
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
