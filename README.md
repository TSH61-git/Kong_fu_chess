# Kong Fu Chess

![WIP](https://img.shields.io/badge/status-Work%20in%20Progress%20%2F%20Active%20Development-yellow)

> This repository is currently under active development. The architecture, real-time motion model, and guard rails are intentionally designed for extensibility, clarity, and deterministic concurrency handling.

## PROJECT OVERVIEW

Kong Fu Chess is a real-time, cooldown-driven variant of traditional chess in which actions are not gated by turns. Instead, pieces move continuously through the board as asynchronous motions, each constrained by timing, route safety, and arrival semantics. The game emphasizes immediate intent, non-blocking motion, and deterministic resolution when multiple trajectories overlap or complete at nearly the same instant.

### Core Gameplay Mechanics

- Pieces move in a real-time simulation rather than a turn-based exchange.
- Motion is represented as an in-flight trajectory with an explicit duration budget, allowing the system to advance the clock continuously.
- In-place jumps are supported as zero-distance motions with a fixed duration, enabling immediate, local re-positioning without a traditional move-turn cycle.
- The board resolves arrivals atomically at the exact completion instant, ensuring captures and promotions occur predictably.
- The engine enforces safety guards so that overlapping motions and shared routes do not corrupt the board state.
- Physical constants (`CELL_SIZE`, `PIECE_SPEED`) are centralized in `config.py` and drive all duration calculations.

### Design Intent

The project is structured around a clear separation of concerns:

- Input and interaction are captured independently from game rules.
- Motion timing and arrival resolution are handled by a dedicated real-time arbiter.
- Movement legality and promotion logic are implemented as pure, stateless rules.
- The domain model remains simple, grid-based, and easy to reason about.
- All text I/O is isolated behind a CLI gateway; the chess engine itself is fully string-blind.

---

## SYSTEM ARCHITECTURE & COMPONENT BREAKDOWN

The system is organized as a clean, decoupled multi-layer architecture that mirrors the responsibilities of a production-grade real-time game engine.

```
app_gateways/text_cli/   CLI gateway (I/O boundary)
chess_engine/engine/     Application service orchestration
chess_engine/input/      Interaction and board-coordinate mapping
chess_engine/model/      Domain objects: board, piece, position
chess_engine/realtime/   Motion tracking and atomic arrival resolution
chess_engine/rules/      Stateless movement and promotion rules
chess_engine/tests/      Unit and integration coverage
config.py                Global physical constants
main.py                  Entry point
```

---

### 1. CLI Gateway — `app_gateways/text_cli/`

The sole boundary between raw text tokens and the typed engine. Nothing outside this package ever handles raw string tokens.

| Module | Responsibility |
|---|---|
| [translator.py](app_gateways/text_cli/translator.py) | Converts token strings ↔ typed `Piece` objects; parses and serializes `Board` |
| [bootstrap.py](app_gateways/text_cli/bootstrap.py) | Factory that wires the full engine stack into a `GameRuntime` dataclass |
| [console_runner.py](app_gateways/text_cli/console_runner.py) | Reads `board:` / `commands:` sections from stdin and dispatches commands |
| [command_registry.py](app_gateways/text_cli/command_registry.py) | O(1) dispatch table mapping command names to handler functions |

**Token format:** `wK`, `bQ`, `wR`, `bP`, etc. — color prefix + piece-type letter. Empty cells are `.`.

**Bootstrap wiring order:**
1. `Board` is created (or injected).
2. `RuleEngine` is instantiated.
3. `RealTimeArbiter` is created with the board (game engine reference set later).
4. `GameEngine` is created with board, rule engine, and arbiter.
5. `arbiter.attach_game_engine(engine)` closes the circular reference.
6. `BoardMapper` and `Controller` are created and wrapped in `GameRuntime`.

---

### 2. Application Service Layer — `chess_engine/engine/`

The engine orchestrates all gameplay flow between input, rules, and motion handling.

| Module | Responsibility |
|---|---|
| [game_engine.py](chess_engine/engine/game_engine.py) | Validates and dispatches moves; owns game-over state |
| [helpers/snapshot_models.py](chess_engine/engine/helpers/snapshot_models.py) | Frozen DTOs: `MoveResult`, `GameSnapshot` |
| [helpers/snapshot_helpers.py](chess_engine/engine/helpers/snapshot_helpers.py) | Pure builder functions for read-only board snapshots |

**`GameEngine` public API:**

- `request_move(source, destination) → MoveResult` — full guard chain + arbiter dispatch
- `request_jump(position) → MoveResult` — in-place cooldown jump
- `wait(ms)` / `advance_time(ms)` — delegates clock ticks to the arbiter
- `get_snapshot(selected_cell) → GameSnapshot` — read-only board view
- `notify_king_captured()` — sets the game-over flag (called by the arbiter on king capture)

**Guard chain in `request_move` / `request_jump`:**
1. Game-over check → `game_over`
2. Cooldown check via `arbiter.is_in_cooldown(source)` → `cooldown_active`
3. In-flight check via `_is_piece_in_flight(arbiter, source)` → `motion_in_progress`
4. Rule validation via `RuleEngine.validate_move` → propagated reason string
5. `arbiter.start_motion(...)` on success → `ok`

**`IRealTimeArbiter` protocol** is defined in `game_engine.py`, keeping the engine decoupled from the concrete arbiter implementation.

---

### 3. Input Layer — `chess_engine/input/`

Translates raw pixel events into semantic game operations. This layer is intentionally thin and does not evaluate board rules or timing.

| Module | Responsibility |
|---|---|
| [controller.py](chess_engine/input/controller.py) | Two-click selection state machine; forwards validated intents to the engine |
| [board_mapper.py](chess_engine/input/board_mapper.py) | Converts pixel coordinates to `Position` using `CELL_SIZE` from `config.py` |

**Controller click semantics:**
- First click on a piece → sets `selected_cell`.
- Second click outside board → clears selection.
- Second click on a friendly piece → swaps selection to that piece (no move request).
- Second click on any other cell → calls `engine.request_move(source, destination)` and clears selection.

---

### 4. Real-Time Layer — `chess_engine/realtime/`

The real-time arbiter is the heart of the simulation. It is the only layer that mutates the board during active motion.

| Module | Responsibility |
|---|---|
| [arbiter.py](chess_engine/realtime/arbiter.py) | Clock-driven motion manager; resolves arrivals atomically |
| [motion.py](chess_engine/realtime/motion.py) | Mutable dataclass tracking a single in-flight piece movement |

#### `Motion` dataclass

```python
@dataclass(eq=False)
class Motion:
    piece: Piece
    source: Position
    destination: Position
    elapsed_ms: int = 0
    duration_ms: int = 0
```

Identity is by object reference (`eq=False`), not by field values, so two motions to the same cell are always distinct.

#### `RealTimeArbiter` internals

| Field | Type | Purpose |
|---|---|---|
| `_active_motions` | `list[Motion]` | All currently in-flight motions |
| `_motion_pieces` | `dict[Motion, Piece]` | Tracks the shadow `MOVING` piece per motion for state reset on arrival |
| `_cooldowns` | `dict[Position, int]` | Remaining cooldown ms per cell |

**Duration calculation:** `steps × CELL_SIZE / PIECE_SPEED × 1000 ms`, where `steps = max(Δrow, Δcol)`.

**`advance_time(ms)` sequence:**
1. Tick down all cooldown counters; drop expired entries.
2. Increment `elapsed_ms` on every active motion.
3. Run `_resolve_mid_route_collisions()`.
4. Collect completed motions (elapsed ≥ duration); sort by `(priority, index)` — linear arrivals (`priority=0`) before jump arrivals (`priority=1`).
5. Call `_resolve_arrival(motion)` for each completed motion in order.

**`is_in_cooldown(pos)` — piece-state-aware lookup:**
```python
def is_in_cooldown(self, pos: Position) -> bool:
    if pos not in self._cooldowns:
        return False
    piece = self._board.get(pos)
    return piece is not None and piece.state != PieceState.MOVING
```
A cooldown is only active when a piece is physically present on the cell **and** that piece is not currently `MOVING`. This allows a piece in transit that targets a cell to proceed without being blocked by a pre-existing cooldown on its destination, and allows vacant cells to be entered freely.

**`_resolve_arrival(motion)` — atomic transition:**
1. Clear source cell.
2. Check destination for a king → call `game_engine.notify_king_captured()` if found.
3. Apply pawn promotion via `_promoted(piece, row, board.rows)`.
4. Place final piece at destination.
5. Set `_cooldowns[destination] = 1000 ms`.
6. Reset shadow piece state to `IDLE`.

**`_cancel_motion(motion, land_at)` — mid-route stop:**
- Removes motion from active list.
- Places piece at `land_at` (last safe cell before collision).
- Sets cooldown on `land_at`.
- Resets shadow piece state to `IDLE`.

---

### 5. Rules Layer — `chess_engine/rules/`

Deliberately stateless and pure. No board mutation occurs here.

| Module | Responsibility |
|---|---|
| [engine.py](chess_engine/rules/engine.py) | `RuleEngine` — iterates the guard pipeline and returns `MoveValidation` |
| [movement.py](chess_engine/rules/movement.py) | Legal destination computation per piece type via a functional registry |
| [trajectory.py](chess_engine/rules/trajectory.py) | Linear path generation and route-overlap detection |
| [guards/boundary_guard.py](chess_engine/rules/guards/boundary_guard.py) | Rejects out-of-bounds source or destination |
| [guards/empty_source_guard.py](chess_engine/rules/guards/empty_source_guard.py) | Rejects moves from empty cells |
| [guards/friendly_fire_guard.py](chess_engine/rules/guards/friendly_fire_guard.py) | Rejects moves onto friendly-occupied cells |
| [guards/legal_move_guard.py](chess_engine/rules/guards/legal_move_guard.py) | Rejects destinations outside the piece's legal movement set |

#### Guard Pipeline

`RuleEngine.validate_move` iterates `_GUARDS` in order and returns the first failing reason:

```
boundary_guard → empty_source_guard → friendly_fire_guard → legal_move_guard
```

Each guard module exposes a single `check(board, source, destination) → str | None` function. Returning `None` means the guard passes.

#### Movement Registry

`movement.py` uses a `_REGISTRY: dict[PieceType, RuleFn]` for O(1) dispatch:

| Piece | Strategy |
|---|---|
| ROOK | `_slide` along 4 cardinal directions |
| BISHOP | `_slide` along 4 diagonal directions |
| QUEEN | `_slide` along all 8 directions |
| KNIGHT | Fixed L-shape offsets, no sliding |
| KING | All 8 adjacent cells, one step |
| PAWN | Forward step, optional double step from start row, diagonal captures only |

`legal_destinations(board, from_pos, piece)` is the single public entry point.

#### Trajectory Module

- `linear_path(source, destination) → list[Position]` — generates the ordered list of cells along a straight or diagonal line.
- `has_route_conflict(src_a, dst_a, src_b, dst_b) → bool` — returns `True` if two linear paths share any cell. Non-linear (knight/king) moves never conflict.

---

### 6. Domain Model — `chess_engine/model/`

Minimal, explicit, and string-blind throughout.

| Module | Key types |
|---|---|
| [position.py](chess_engine/model/position.py) | `Position(row, col)` — frozen dataclass, hashable, immutable |
| [piece.py](chess_engine/model/piece.py) | `Piece(piece_type, color)`, `PieceType` enum, `Color` enum, `PieceState` enum |
| [board.py](chess_engine/model/board.py) | `Board(rows, cols)` — matrix of `Piece \| None`; raises on out-of-bounds access |

**`PieceState` enum:**

| Value | Meaning |
|---|---|
| `IDLE` | Piece is at rest on the board |
| `MOVING` | Piece has an active in-flight motion (shadow piece tracked by arbiter) |
| `CAPTURED` | Piece has been removed from play |

`Piece.__eq__` and `__hash__` are based on `(piece_type, color)` only — state is mutable and excluded from identity.

---

## DESIGN PATTERNS IMPLEMENTED

### Functional Registry Pattern

Both movement dispatch and guard sequencing replace large decision trees with compact, constant-time registries.

- `movement.py` uses `_REGISTRY: dict[PieceType, RuleFn]` for O(1) piece-type dispatch.
- `engine.py` uses `_GUARDS: list[module]` for ordered, short-circuit guard evaluation.
- `command_registry.py` uses a `dict[str, CommandFn]` for O(1) CLI command dispatch.

### Real-Time Cooldown / Motion Queue State Machine

Each motion transitions through three logical states:

```
pending → in-flight (elapsed < duration) → resolved (elapsed ≥ duration)
```

The arbiter advances the simulation clock and evaluates completion thresholds on every `advance_time` call. Cooldowns are a separate time-keyed dict that decays independently of active motions.

### Atomic Arrival & Concurrency Resolution

Arrival handling is a single consistent transition:

1. Clear source.
2. Check for king capture.
3. Apply promotion.
4. Place piece at destination.
5. Set cooldown.

Linear arrivals are resolved before jump arrivals in the same tick, preventing race-like ordering artifacts.

### Piece-State-Aware Cooldown Guard

`is_in_cooldown` consults both the cooldown registry and the live board state. A cell with a cooldown entry but no piece (vacated mid-flight) returns `False`, and a cell occupied by a `MOVING` piece also returns `False`. This cleanly separates spatial grid locking from piece-level action gating and is the foundation for future multi-piece coordination.

### Protocol-Based Dependency Inversion

`GameEngine` depends on `IRealTimeArbiter` (a `Protocol`) rather than the concrete `RealTimeArbiter`. `Controller` depends on `IGameEngine` (a `Protocol`). This keeps each layer independently testable and substitutable.

### Immutable DTOs

`MoveResult` and `GameSnapshot` are `@dataclass(frozen=True)`. `Position` is a `@dataclass(frozen=True)`. `MoveValidation` in `rules/engine.py` is also frozen. No mutable state leaks across layer boundaries through these objects.

---

## CONCURRENCY & ROUTING GUARDS

### Same-Piece Lockout

If a source cell already has an active motion (`_is_piece_in_flight`), the request is rejected with `motion_in_progress`. This prevents double-queuing a single piece.

### Cooldown Lockout

After a piece arrives or is cancelled, its destination cell enters a 1000 ms cooldown. `is_in_cooldown` blocks new move requests from that cell until the cooldown expires and the piece is idle.

### Shared Linear Route Collision

`has_route_conflict` in `trajectory.py` detects overlapping linear paths before a motion is accepted. In-place jumps (`source == destination`) are non-linear and never participate in route-conflict checks.

### Mid-Route Collision Resolution

`_resolve_mid_route_collisions` runs on every `advance_time` tick:

- Computes the current interpolated cell for each active motion via `_current_cell`.
- When two motions occupy the same cell:
  - **Enemy pieces:** the later-arriving motion is cancelled to the collision cell; if the earlier is a stationary jump, the linear motion is cancelled instead.
  - **Friendly pieces:** the later motion is cancelled to its last legal stop before the collision cell, computed by `_last_legal_stop_before`.
- Jump motions are always treated as "earlier" than linear motions at the same cell.

---

## VERIFICATION & TESTING

```bash
python -m pytest chess_engine/tests/ app_gateways/text_cli/tests/ -v
```

### Test Modules

| File | Coverage area |
|---|---|
| `test_model.py` | `Position`, `Piece`, `PieceType`, `Color`, `PieceState`, `Board` |
| `test_piece_rules.py` | Legal destinations for all six piece types |
| `test_promotion_rules.py` | Pawn promotion at back rank for both colors and all board sizes |
| `test_rule_engine.py` | Full guard pipeline: boundary, empty source, friendly fire, illegal move |
| `test_board_mapper.py` | Pixel-to-cell mapping, boundary acceptance, out-of-bounds rejection |
| `test_controller.py` | Two-click state machine, selection swap, request_move forwarding |
| `test_game_engine.py` | Guard chain, game-over flag, snapshot, king-capture notification |
| `test_cooldown.py` | Cooldown lifecycle, expiry, engine-level cooldown rejection |
| `test_real_time_arbiter.py` | Motion tracking, atomic arrival, king capture, jump vs linear ordering |
| `test_collisions.py` | Linear path, route conflict, mid-route enemy/friendly collision, arrival ordering |
| `test_text_scripts.py` | End-to-end CLI script execution against expected output snapshots |

Current count: **223 tests, all passing**.

---

## QUICK START

```bash
python main.py
```

Input is read from stdin in the following format:

```
board:
wR . . . bR
. . . . .
. . wK . .
. . . . .
bK . . . .

commands:
click 0 0
wait 500
print board
```

---

## SUMMARY

Kong Fu Chess combines:

- a decoupled multi-layer architecture with strict string-blindness in the engine,
- pure stateless rules with a functional registry and SRP guard pipeline,
- deterministic motion arbitration with atomic arrival and piece-state-aware cooldown,
- protocol-based dependency inversion for testability,
- and explicit safety guards for concurrency, routing, and multi-piece coordination.
