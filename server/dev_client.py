# Reference CLI client. Login/connection and the pre-game wait happen in the
# shell exactly like any other client of this protocol; once the server
# announces the match is ready, gameplay hands off to the OpenCV GUI — moves
# from then on come from clicks in that window, not typed commands.
#
# The GUI modules are imported here at module load time rather than lazily
# inside run_gui_phase(): run_shell_phase() leaves an abandoned background
# thread behind (a still-blocked sys.stdin.readline() call that can't be
# force-stopped once match_ready fires — see the comment there), and
# importing cv2 for the first time while that thread is alive reliably
# deadlocks on Windows. Importing everything up front, before that thread
# ever exists, avoids the ordering entirely.
from __future__ import annotations

import asyncio
import json
import sys

from websockets.asyncio.client import connect

from app_gateways.gui.gui_runner import GuiRunner
from app_gateways.gui.network_facade import build_network_runtime
from chess_engine.model.board import Board
from chess_engine.model.piece import Color, PieceType
from chess_engine.wire.notation import square_to_position


def _line_to_envelope(command: str) -> dict:
    if command == "ping":
        return {"type": "ping", "data": {}}
    if command.startswith("jump "):
        # "jump WPe2" -> cmd "WPe2e2": notation.parse_move_command always
        # expects a source and a destination square, so a jump's square is
        # duplicated into both halves before it's sent.
        square_command = command.split(" ", 1)[1]
        return {"type": "jump", "data": {"cmd": square_command + square_command[-2:]}}
    return {"type": "move", "data": {"cmd": command}}


class DevClient:
    def __init__(self, websocket) -> None:
        self._websocket = websocket
        self._board = Board(rows=8, cols=8)
        self._facade = None
        self._match_ready = asyncio.Event()
        self._pending_response: asyncio.Future | None = None
        self._player_names: tuple[str, str] | None = None

    async def _send_envelope(self, envelope: dict) -> None:
        await self._websocket.send(json.dumps(envelope))

    async def _send_and_wait(self, envelope: dict) -> dict:
        # Only the auth step needs a request/response round trip (to decide
        # whether to prompt again) — everything else here is fire-and-forget,
        # with replies just printed as they arrive in _handle_message.
        loop = asyncio.get_running_loop()
        self._pending_response = loop.create_future()
        await self._send_envelope(envelope)
        try:
            return await self._pending_response
        finally:
            self._pending_response = None

    async def receive_loop(self) -> None:
        async for raw_message in self._websocket:
            self._handle_message(json.loads(raw_message))

    def _handle_message(self, message: dict) -> None:
        message_type = message.get("type")
        event = message.get("event")
        data = message.get("data", {})

        if message_type in ("ack", "error") and self._pending_response is not None:
            if not self._pending_response.done():
                self._pending_response.set_result(message)
            return

        if message_type == "notice" and event == "seated":
            print(f"Seated as {data['role'].upper()}.")
            return
        if message_type == "broadcast" and event == "match_ready":
            self._player_names = (data["white_username"], data["black_username"])
            self._match_ready.set()
            return
        if message_type == "error":
            print(f"< error: {message.get('code')} {message.get('message', '')}".rstrip())
            return
        if message_type == "ack":
            if data:
                print(f"< ok {data}")
            else:
                print("< ok")
            return

        if self._facade is None:
            return  # pre-game broadcasts (e.g. the tick loop's own state_tick) — nothing to feed yet

        if event == "state_tick":
            self._facade.apply_state_tick(
                data["board_grid"], data["active_motions"], data["cooldowns"], data["game_over"],
            )
        elif event == "move_accepted":
            self._facade.apply_move_accepted(
                Color[data["color"].upper()],
                PieceType[data["piece_type"].upper()],
                square_to_position(data["source"]),
                square_to_position(data["destination"]),
                data["is_capture"],
            )
        elif event == "piece_captured":
            self._facade.apply_piece_captured(
                PieceType[data["piece_type"].upper()],
                Color[data["piece_color"].upper()],
                Color[data["captured_by"].upper()],
            )
        elif event == "game_over":
            self._facade.apply_game_over(data.get("winner_username"))

    async def _read_line(self) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, sys.stdin.readline)

    async def _authenticate(self) -> bool:
        """Prompts Register vs Login, collects credentials, and retries on
        failure. Returns False only if stdin closes (e.g. piped input ran
        out) before authentication succeeds."""
        while True:
            print("Choose an option: [1] Register  [2] Login")
            choice_line = await self._read_line()
            if not choice_line:
                return False
            choice = choice_line.strip()
            if choice not in ("1", "2"):
                print("Please enter 1 or 2.")
                continue
            command_type = "register" if choice == "1" else "login"

            print("Username:")
            username_line = await self._read_line()
            if not username_line:
                return False
            username = username_line.strip()

            print("Password:")
            password_line = await self._read_line()
            if not password_line:
                return False
            password = password_line.strip()

            if not username or not password:
                print("Username and password are required.")
                continue

            reply = await self._send_and_wait(
                {"type": command_type, "data": {"username": username, "password": password}},
            )
            if reply.get("type") == "ack":
                verb = "Registered" if command_type == "register" else "Logged in"
                print(f"{verb} as {username}.")
                return True
            print(f"< error: {reply.get('code')} {reply.get('message', '')}".rstrip())

    async def run_shell_phase(self) -> bool:
        """Authenticates, then reads shell commands until the match is ready
        or stdin closes. Returns True if it exited because the match became
        ready."""
        print("Connected.")
        if not await self._authenticate():
            return False
        if self._match_ready.is_set():
            return True

        print("Type a move like 'WQe2e5', 'jump WPe2', or 'ping'.")
        print("Waiting for an opponent - the game window opens once both players are seated.")
        return await self._wait_for_match_ready()

    async def _wait_for_match_ready(self) -> bool:
        """Reads shell commands until the match is ready or stdin closes.
        Returns True if it exited because the match became ready."""
        loop = asyncio.get_running_loop()
        while not self._match_ready.is_set():
            read_future = loop.run_in_executor(None, sys.stdin.readline)
            ready_task = asyncio.create_task(self._match_ready.wait())
            done, pending = await asyncio.wait({read_future, ready_task}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()  # a still-blocked stdin read can't be force-stopped; it's simply abandoned
            if ready_task in done:
                return True
            line = read_future.result()
            if not line:
                return False
            command = line.strip()
            if command:
                await self._send_envelope(_line_to_envelope(command))
        return True

    async def run_gui_phase(self) -> None:
        runtime = build_network_runtime(self._board, self._send_envelope)
        self._facade = runtime.engine
        if self._player_names is not None:
            self._facade.apply_match_ready(*self._player_names)
        print("Match ready - opening the game window.")
        await GuiRunner(runtime).run()


async def run(uri: str) -> None:
    async with connect(uri) as websocket:
        client = DevClient(websocket)
        receive_task = asyncio.create_task(client.receive_loop())
        match_ready = await client.run_shell_phase()
        if match_ready:
            await client.run_gui_phase()
        receive_task.cancel()


def main() -> None:
    uri = sys.argv[1] if len(sys.argv) > 1 else "ws://localhost:8765"
    try:
        asyncio.run(run(uri))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
