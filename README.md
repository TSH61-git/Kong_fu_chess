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

### Design Intent

The project is structured around a clear separation of concerns:

- Input and interaction are captured independently from game rules.
- Motion timing and arrival resolution are handled by a dedicated real-time arbiter.
- Movement legality and promotion logic are implemented as pure, stateless rules.
- The domain model remains simple, grid-based, and easy to reason about.

---

## SYSTEM ARCHITECTURE & COMPONENT BREAKDOWN

The system is organized as a clean, decoupled multi-layer architecture that mirrors the responsibilities of a production-grade real-time game engine.

### 1. Presentation / Controller Layer

The input layer is responsible for translating user intent into semantic game operations.

- The controller captures raw interaction events and converts them into move requests.
- It maintains lightweight selection state and forwards validated intents to the application service.
- This layer is intentionally thin: it does not evaluate board rules, movement geometry, or timing.

Key modules:
- [input/controller.py](input/controller.py)
- [input/board_mapper.py](input/board_mapper.py)

### 2. Application Service Layer

The engine orchestrates all gameplay flow between input, rules, and motion handling.

- It validates moves before dispatching them.
- It enforces application-level guards, including game-over state and motion routing conflicts.
- It coordinates board snapshots and delegates time progression to the real-time arbiter.

Key module:
- [engine/game_engine.py](engine/game_engine.py)

### 3. Core Real-Time Layer

The real-time arbiter is the heart of the simulation.

- It tracks multiple in-flight motions concurrently without blocking the rest of the engine.
- It acts as a clock-driven motion manager, advancing elapsed time and resolving arrivals when completion thresholds are met.
- It is the only layer that mutates the board during active motion, which keeps state transitions centralized and deterministic.

Key module:
- [realtime/real_time_arbiter.py](realtime/real_time_arbiter.py)

### 4. Rules Layer

The rules subsystem is deliberately stateless and pure.

- Movement rules compute legal destinations from geometry and board occupancy.
- Promotion rules determine transformation outcomes based on piece type, row, color, and board size.
- This layer does not mutate the board and can be reasoned about independently from the simulation clock.

Key modules:
- [rules/movement_rules.py](rules/movement_rules.py)
- [rules/promotion_rules.py](rules/promotion_rules.py)
- [rules/rule_engine.py](rules/rule_engine.py)

### 5. Domain Model Layer

The domain model is intentionally minimal and explicit.

- Positions are represented as immutable coordinate objects.
- The board is a matrix-based logical grid that stores piece tokens.
- Pieces encapsulate identity and state without embedding movement logic or timing concerns.

Key modules:
- [model/position.py](model/position.py)
- [model/board.py](model/board.py)
- [model/piece.py](model/piece.py)

---

## DESIGN PATTERNS IMPLEMENTED

The implementation uses a small but powerful set of patterns to preserve clarity while handling real-time complexity.

### Functional Registry Pattern

Both movement and promotion logic replace large hardcoded decision trees with compact, constant-time registries.

- [rules/movement_rules.py](rules/movement_rules.py) uses a dispatch table keyed by piece type, enabling $O(1)$ lookup for rook, bishop, queen, knight, king, and pawn movement strategies.
- [rules/promotion_rules.py](rules/promotion_rules.py) uses a similar registry for promotion outcomes, ensuring the logic remains extensible and declarative.

This pattern dramatically improves maintainability while avoiding brittle if/else chains.

### Real-Time Cooldown / Motion Queue State Machine

The real-time layer behaves as a clock-driven state machine.

- Each motion is tracked as a stateful object with elapsed time and a total duration budget.
- The arbiter advances the simulation and evaluates whether a motion has reached its completion threshold.
- From a state-machine perspective, the motion transitions from pending to in-flight to resolved at the exact arrival boundary.

Conceptually, the system evaluates a remaining-time budget derived from elapsed versus total duration, ensuring that no motion is resolved too early or too late.

### Atomic Arrival & Concurrency Resolution

Arrival handling is intentionally atomic.

- The arbiter clears the source cell, checks for captures, places the moving piece at the destination, and applies promotion as one consistent transition.
- Linear trajectories are resolved before in-place jump completions, which prevents race-like ordering artifacts when multiple motions finish in the same window.
- This yields deterministic board resolution even under concurrent arrival conditions.

In practice, this means the engine resolves moves in a stable order: first standard linear paths, then jump arrivals from above, avoiding partial-state visibility and preserving the integrity of the board snapshot.

---

## CONCURRENCY & ROUTING GUARDS

Real-time routing safety is enforced with explicit guards so that motion semantics remain coherent under load.

### Same-Piece Lockout

The engine prevents a piece from being commanded again while it already has an active motion.

- If a source cell is currently in flight, the request is rejected with a `motion_in_progress` outcome.
- This avoids double-queuing a single piece and eliminates ambiguous source ownership during transit.

### Shared Linear Route Collision

Linear motions are checked against one another before they are accepted.

- Sliding pieces share path occupancy rules and cannot begin routes that intersect an active linear path.
- In-place jumps are non-blocking by design and do not participate in the same route-collision semantics.

This ensures that moving pieces do not create conflicting travel corridors or cause hidden board corruption during simultaneous motion.

---

## VERIFICATION & TESTING

The project includes a comprehensive, layered test suite covering rules, controller behavior, engine orchestration, real-time arbiter behavior, and integration scripts.

### Running the Test Suite

```bash
python -m pytest
```

### Current Verification Snapshot

The repository currently collects 227 tests through pytest, covering:

- Integration scenarios
- Edge-case handling
- Matrix-driven rule validation
- Real-time motion and arrival resolution
- Board input/output and controller state transitions

This makes the codebase suitable for iterative development while maintaining strong regression protection around the real-time motion model.

---

## PROJECT LAYOUT

```text
engine/          Application service orchestration
input/           Interaction and board-coordinate mapping
model/           Domain objects: board, piece, position
realtime/        Motion tracking and atomic arrival resolution
rules/           Stateless movement and promotion rules
text_io/         Board parsing and rendering
tests/           Unit and integration coverage
```

---

## QUICK START

A typical execution flow uses the console entry point in [main.py](main.py):

```bash
python main.py
```

Input is expected to follow the project’s structured board/command format, and the engine will emit state updates and board snapshots accordingly.

---

## SUMMARY

Kong Fu Chess is a deliberately engineered real-time chess variant that combines:

- a decoupled multi-layer architecture,
- pure stateless rules,
- deterministic motion arbitration,
- and explicit safety guards for concurrency and routing.

The result is a codebase that is both architecturally expressive and robust under real-time constraints.
