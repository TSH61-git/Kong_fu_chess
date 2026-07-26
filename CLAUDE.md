# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

Kong Fu Chess is a real-time, cooldown-driven chess variant: pieces move continuously as in-flight motions with a duration budget rather than in alternating turns. `README.md` at the repo root has a very detailed (but partially stale — see below) architecture writeup; read it for background on the text-CLI/engine layers. This file covers commands and the parts that have evolved since the README was last updated (event system, GUI).

## Commands

Run everything through the venv's Python (`opencv-python`/`numpy` are only installed there):

```bash
./venv/Scripts/python.exe -m pytest -q                      # full suite
./venv/Scripts/python.exe -m pytest chess_engine/tests/ app_gateways/text_cli/tests/ app_gateways/gui/tests/ -v
./venv/Scripts/python.exe -m pytest chess_engine/tests/test_cooldown.py -q   # single file
./venv/Scripts/python.exe -m pytest chess_engine/tests/test_cooldown.py::test_name -q  # single test
```

Run the game:

```bash
./venv/Scripts/python.exe main.py            # text CLI, reads board/commands from stdin
./venv/Scripts/python.exe main.py --gui      # OpenCV GUI, standard starting position
./venv/Scripts/python.exe run_gui.py         # GUI entry point used when double-clicked/frozen
```

There is no lint/build step configured beyond pytest.

## Architecture beyond the README

The README's layer breakdown (`app_gateways/text_cli`, `chess_engine/{engine,input,model,realtime,rules}`) is accurate for the core simulation. Two things have since been added on top of it:

### Event system (`chess_engine/engine/event_manager.py`, `events.py`)

`GameEngine` no longer owns score/history bookkeeping directly — it publishes domain events through an in-process, synchronous `EventManager` (`subscribe(type, handler)` / `publish(event)`), and dedicated helpers subscribe to them:

- `MoveAccepted` — published from `request_move`/`request_jump` right after `arbiter.start_motion` succeeds. Consumed by `MoveHistory` (`chess_engine/engine/helpers/move_history.py`) to build the chronological move feed (`display_text()` gives algebraic-ish notation like `Nxe5`).
- `PieceCaptured` — published from `advance_time` for every capture the arbiter reports via `take_captures()`. Consumed by `ScoreManager` (`chess_engine/engine/helpers/score_manager.py`) to accumulate material score per color (`PIECE_VALUES` table) and the captured-piece list.
- `GameOver` — published from `notify_king_captured`.

`GameEngine` constructs its own `EventManager`, `MoveHistory`, and `ScoreManager` in `__init__` (an external `EventManager` can be injected, mainly for tests). Public read accessors: `history_entries()`, `get_scores()`, `get_captured(color)`.

`PieceInfo` (`chess_engine/engine/helpers/piece_info.py`) is a frozen `(piece_type, color)` DTO used at the engine→GUI boundary (e.g. inside `CapturedEntry`) so display code can't reach for a live `Piece`'s mutable `.state`.

Because game-over is driven by a king-capture event and pieces move continuously, `request_move`/`request_jump` also check `arbiter.is_destination_claimed(destination, color)` before starting a motion, rejecting with `destination_claimed` — this guards against two friendly pieces racing to the same empty square.

### GUI (`app_gateways/gui/`)

OpenCV/numpy-based renderer, layered on top of the same `GameRuntime` the text CLI bootstraps (`app_gateways/gui/bootstrap.py` builds one via `app_gateways.text_cli.bootstrap.GameRuntime`, then wraps it in `GuiRunner`). The engine remains completely unaware of OpenCV/pixels.

- `gui_runner.py` — main loop: each frame calls `engine.advance_time(delta_ms)`, pulls a `GameSnapshot` + active motions + cooldowns, feeds them to the renderer, and pumps `cv2.waitKey`. Mouse clicks are translated from window space to native canvas space (`letterbox_transform` / `window_to_native`) before being forwarded to `runtime.controller.click(x, y)`, because the canvas is letterboxed to fit an arbitrarily resized window while staying aspect-correct.
- `renderer.py` — pure drawing given a snapshot + animator states; no engine calls.
- `translator.py` — GUI-side board/asset helpers (`standard_board()`, `piece_dir()`, `board_to_grid()`); analogous in spirit to the text CLI's `translator.py` but produces pixels/paths instead of tokens.
- `animation/` — per-piece sprite-sheet animation state machine, independent of game rules:
  - `AnimState`: `IDLE → MOVE|JUMP → LONG_REST|SHORT_REST → IDLE`. `MOVE`/`JUMP` correspond to an active `Motion`; `LONG_REST` follows a linear move, `SHORT_REST` follows a jump; both rest states auto-transition back to `IDLE` when their sprite sheet (non-looping) finishes.
  - `PieceAnimator` owns one sheet per state and drives `_frame_index` off accumulated `delta_ms`; `rest_progress` (1.0→0.0) is read by the renderer to draw a cooldown bar.
  - `GuiRunner._sync_animators` reconciles animator objects (keyed by board cell) against the current list of active `Motion`s and the board every frame — including relocating an animator from source to destination when a motion completes, rebuilding it if a pawn promoted on arrival, and dropping it if the piece was captured mid-route instead of arriving.

### Working across the engine/GUI boundary

When adding a new piece of engine state that the GUI needs to display, prefer exposing it as a new event + helper (as done for score/history) or a new field on `GameSnapshot`/a frozen DTO like `PieceInfo`/`CapturedEntry`, rather than handing the GUI a live `Piece`/`Board` reference — the existing code deliberately keeps mutable domain objects on the engine side of the boundary.

### Multiplayer server (`server/`)

A real, working single-process asyncio WebSocket server sits alongside the local-only `text_cli`/`gui` gateways — `chess_engine` stays 100% unaware of it (zero imports of `websockets`/`asyncio`/`server.*` anywhere under `chess_engine/`), and the GUI stays a plain client of the wire protocol (`app_gateways/gui/` never imports from `server/`). Run it with `python -m server.main`; the reference client is `python -m server.dev_client` (shell auth, then hands off to the same OpenCV GUI via `app_gateways/gui/network_facade.py`).

`server/network/` is split into three sub-packages so the transport can be swapped without touching dispatch/protocol logic:
- `transport/` — `server.py` (accept loop, `serve_forever`) and `session.py` (`ClientSession`, `Role`). Owns zero game rules.
- `protocol/` — envelope encode/decode and the `ErrorCode` vocabulary (`Envelope`, `encode_ack/error/broadcast/notice`, `decode_envelope`).
- `dispatch/` — the command-type → handler table (`dispatch()`) that `transport/server.py` calls per inbound message.
- `server/network/server_context.py` — `ServerContext`, the shared per-process object (auth service, bus, registry, queue, matches repo) handed to every dispatch handler; kept outside the three sub-packages since it's cross-cutting, not owned by one of them.

Other top-level `server/` packages: `core/` (shared `Bus` pub/sub, `Clock`, server-level domain events, `wire_events.py`'s `MessageType`/`WireEvent`/`CommandType`/`GameOverReason` enums, and `messages.py`'s wire-payload DTOs — the single typed source of truth for message shape, imported by both `server/game/engine_bridge.py` on the send side and `server/dev_client.py` on the receive side), `game/` (`MatchSession`, `EngineEventRelay`/`RoomBroadcaster` bridging chess_engine's synchronous `EventManager` onto the async `Bus`), `matchmaking/`, `rooms/` (custom room codes), `auth/`, `db/` (SQLite), `rating/` (Elo).

Move/game-over reason vocabulary is centralized in `chess_engine/rules/reasons.py` (`MoveRejectReason`) and `server/core/wire_events.py` (`GameOverReason`) rather than passed as raw strings; the GUI keeps its own local mirror (`app_gateways/gui/game_over_reason.py`) instead of importing the server's, to preserve the one-way gateway → engine dependency direction.

`Server_Design.md` at the repo root is a separate, largely unimplemented proposal for decomposing this single-process server into a distributed microservices/K8s platform — it describes a future target, not the code under `server/` today.
