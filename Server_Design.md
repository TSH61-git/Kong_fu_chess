# Kong Fu Chess — Production System Design & Implementation Plan

**Status:** Approved design, ready for build-out
**Scope:** Take Kong Fu Chess from its current state — a single-process
asyncio server (`server/`) backed by SQLite, talking WebSocket to a text
CLI/GUI client — to a distributed, containerized platform serving
real-time play at global scale.

**Targets:**

| Requirement | Value |
|---|---|
| Registered users | 100,000,000 |
| Concurrent players (CCU) | 10,000,000 |
| Move cadence | ~1 move / player / 2 seconds |
| Match duration | 30–90 seconds (avg. ~60s) |

This document is split into two parts. **Part 1** records the architectural
decisions for *this* project as Architecture Decision Records (ADRs) — not
a survey of options, but the actual choices made, why, and what they cost.
**Part 2** turns those decisions into artifacts that can be run today: a
repository layout, Dockerfiles, a `docker-compose.yml` for local
development, Kubernetes/K3s manifests, and a step-by-step build-out
checklist.

Throughout, "today" refers to the existing `server/` package in this repo
(`server/main.py`, `server/network`, `server/matchmaking`, `server/game`,
`server/db`, `server/auth`, `server/rating`, `server/rooms`) — a single
asyncio process, SQLite-backed, that already implements auth, matchmaking,
a live match loop over `chess_engine`, disconnect handling, and Elo rating.
That module boundary is not incidental: it is the actual seam this design
splits along when it goes distributed, and Part 2 §1 maps every module to
the service it becomes.

---

## Table of contents

**Part 1 — Architectural Design and ADRs**
- [ADR-001: Reject SQLite; adopt managed, sharded Postgres](#adr-001-reject-sqlite-adopt-managed-sharded-postgres)
- [ADR-002: Decompose the monolith into four services](#adr-002-decompose-the-monolith-into-four-services)
- [ADR-003: Redis as the presence registry and matchmaking queue](#adr-003-redis-as-the-presence-registry-and-matchmaking-queue)
- [ADR-004: Regionally-sharded Kubernetes/K3s clusters, no global cluster](#adr-004-regionally-sharded-kubernetesk3s-clusters-no-global-cluster)
- [ADR-005: Live match state is in-memory only — no volume, no per-match durability](#adr-005-live-match-state-is-in-memory-only--no-volume-no-per-match-durability)
- [ADR-006: Binary wire protocol over JSON](#adr-006-binary-wire-protocol-over-json)
- [ADR-007: Graceful draining, not eviction, for the Game Server tier](#adr-007-graceful-draining-not-eviction-for-the-game-server-tier)
- [ADR-008: Event sourcing between Game Server and the database](#adr-008-event-sourcing-between-game-server-and-the-database)

**Part 2 — Concrete Implementation and Execution Plan**
1. [Project / library structure](#1-project--library-structure)
2. [Container and Docker implementation](#2-container-and-docker-implementation)
3. [Local development setup (Docker Compose)](#3-local-development-setup-docker-compose)
4. [Production orchestration (Kubernetes / K3s manifests)](#4-production-orchestration-kubernetes--k3s-manifests)
5. [Step-by-step deployment and execution checklist](#5-step-by-step-deployment-and-execution-checklist)

---

# Part 1: Architectural Design and Decision Records

Each ADR below is a final decision for this project: it states the context
that forced the decision, the decision itself, and the consequences we are
explicitly accepting — including the ones that are downsides. These are
not theoretical trade-off surveys; they are the choices this system is
built on.

---

## ADR-001: Reject SQLite; adopt managed, sharded Postgres

**Status:** Decided.

**Context.** `server/db/connection.py` currently opens a single
`sqlite3.connect(DB_PATH, check_same_thread=False)` and repository methods
run via `asyncio.to_thread`. That is the correct choice for a single
process serving a handful of concurrent matches during development — it is
disqualified the moment there is more than one server process, which is
true of every deployment target beyond a developer's laptop. SQLite has
one writer at a time, lives on one machine's local disk, and has no network
protocol: two `kfc-*` pods cannot share `server/kfchess.db` at all, let
alone under load from 10M CCU.

**Decision.** Replace SQLite with a managed, replicated relational
database — PostgreSQL (Amazon Aurora PostgreSQL or Google Cloud SQL for
Postgres in the first deployment; CockroachDB/Spanner considered only if
cross-region synchronous writes become a bottleneck later). It runs as a
managed service **outside** the Kubernetes cluster.

- Sizing: a user record (id, password hash, display name, rating,
  aggregate stats — the union of `server/db/users_repository.py` and
  `server/rating/elo.py`'s needs) is ~0.5–2 KB. 100M users ≈ **100–200 GB**.
  This fits on a single large Postgres instance; the reason to shard is
  concurrency, not volume.
- One **primary + read replicas per region**, matching the regional
  cluster topology in ADR-004.
- Shard by `hash(user_id)` across N Postgres clusters only if/when a single
  primary's write throughput becomes the bottleneck — user rows never need
  a cross-shard join (profile, rating, and match history are all keyed off
  the owning user), so this shards cleanly when needed and is deferred
  until it is.
- A Redis-backed cache sits in front of it for session/auth lookups
  (ADR-003), so the login/reconnect hot path rarely touches Postgres at
  all.

**Consequences.**
- *Accepted cost:* an external managed dependency with its own bill and
  operational surface, instead of a file shipped with the app.
- *Accepted cost:* schema migrations now need a real migration tool
  (Alembic) and a rollout process, not a `CREATE TABLE IF NOT EXISTS` run
  at process start (`server/db/schema.py` today).
- *Benefit:* horizontal read scaling, online failover, point-in-time
  recovery, and the ability for every `kfc-*` pod in a region to share one
  source of truth.

---

## ADR-002: Decompose the monolith into four services

**Status:** Decided.

**Context.** `server/main.py` boots one process that owns the WebSocket
accept loop (`server/network/server.py`), matchmaking
(`server/matchmaking/matchmaker.py`, `queue.py`), live match state
(`server/game/match.py`, `engine_bridge.py`, `registry.py`), auth
(`server/auth/service.py`), and rating (`server/rating/elo.py`) in one
address space. That is exactly right for a single-node prototype and
exactly wrong at 10M CCU: connection count, matchmaking throughput, and
live-simulation CPU all scale on different curves and need to scale
independently, and a crash in one concern (say, a bug in engine
simulation) should not take the WebSocket accept loop down with it.

**Decision.** Split along the module boundaries that already exist in
`server/`, into four independently deployable services:

| Service | Absorbs today's module(s) | State |
|---|---|---|
| `kfc-gateway` | `server/network/*`, `server/core/protocol.py` | Stateless |
| `kfc-matchmaker` | `server/matchmaking/*`, `server/rooms/*` | Stateless (state in Redis) |
| `kfc-game-server` | `server/game/*`, embeds `chess_engine/*` unchanged | Stateful, in-memory |
| `kfc-event-consumer` | `server/db/*`, `server/rating/*` | Stateless |

`server/auth/*` (hashing, credential checks) is used by both `kfc-gateway`
(login/session validation) and, indirectly, by `kfc-event-consumer` (no
game-time auth writes) — it ships as a **shared library**, not a fifth
service, since it has no independent scaling curve of its own (see Part 2
§1 for the shared-package layout).

`chess_engine/` does not change. `GameEngine.advance_time`, the event
system, and `arbiter` logic move into `kfc-game-server` as-is; the
container boundary is drawn *around* the engine, not *through* it — this
is the same "engine stays unaware of its host" property the engine
already has with respect to the GUI (per `CLAUDE.md`), now true with
respect to the network topology too.

**Consequences.**
- *Accepted cost:* what was one process is now four, communicating over
  the network (WebSocket client↔gateway, gateway↔matchmaker, gateway↔game
  server, game server↔event bus) instead of function calls — real
  serialization and real network-failure modes appear where there were
  none.
- *Accepted cost:* local development now needs multiple processes running
  together (Part 2 §3), not `python -m server.main`.
- *Benefit:* each tier scales on its own metric (ADR-004/Part 2 §4), and a
  Game Server crash no longer takes matchmaking or new logins down with
  it.

---

## ADR-003: Redis as the presence registry and matchmaking queue

**Status:** Decided.

**Context.** In the monolith, `server/matchmaking/queue.py` and
`server/game/registry.py` are in-process data structures — a queued
session and "which match is this session in" are just Python objects
reachable from one process's memory. Once matchmaking (ADR-002) and game
hosting are different pods, "who is queued" and "which pod holds room X"
must live somewhere every Gateway and Matchmaker pod can see.

**Decision.** A Redis cluster is the shared coordination layer, holding
exactly three things, namespaced by key prefix within the same cluster
(not three separate systems to operate):

1. **Matchmaking queue** — replaces `server/matchmaking/queue.py`'s
   in-memory structure with a Redis sorted set keyed by Elo (mirrors
   `QUEUE_ELO_RANGE` in `server/config.py`), so any `kfc-matchmaker` pod
   can pop a compatible pair.
2. **Presence/session registry** — `user_id` / `room_id` → owning
   `kfc-game-server` pod address, written once at room creation
   (replaces `server/game/registry.py`), read by any `kfc-gateway` pod to
   route a message or a spectator into the right room.
3. **Auth/session cache** — short-TTL cache of validated session tokens,
   fronting Postgres for the hot reconnect path (ADR-001).

Sizing: 10M live presence entries at a few hundred bytes each is a few GB
of hot key space — comfortably inside a modest Redis Cluster.

**Consequences.**
- *Accepted cost:* Redis becomes a hard dependency for correctness, not
  just a cache — losing it mid-operation strands live connections with no
  way to resolve rooms. This is why it gets a `PersistentVolumeClaim` and
  primary/replica failover in Part 2 §4, unlike the fully stateless tiers.
- *Benefit:* this is the mechanism that answers "how do you know which
  players are on which server" — a lookup, not a search — and the
  mechanism that makes "everyone can play everyone" true: the queue and
  registry are logical, not tied to any one server.

---

## ADR-004: Regionally-sharded Kubernetes/K3s clusters, no global cluster

**Status:** Decided.

**Context.** 10,000,000 concurrent players × 1 move/2s = **5,000,000
moves/sec**. At a realistic ~150 bytes on the wire per move (JSON payload +
WebSocket framing + TCP/IP headers), that is **~6 Gbps inbound**, and
because each move is relayed to at least an opponent, **~12 Gbps** total
through whatever ingress handles it. A compact binary protocol (ADR-006)
cuts this to **~4 Gbps**, but even that number, concentrated through one
cluster's ingress, is large — while being *negligible* for the internet's
actual backbone capacity (100–400+ Gbps per link; global aggregate traffic
in the terabit/petabit range). The conclusion is not "the internet can't
carry this," it's "our own ingress shouldn't have to carry all of it in
one place," and separately, players on opposite sides of the planet should
not be routed through a single mid-ocean cluster for latency's sake.

**Decision.** Deploy one independent Kubernetes (or K3s) cluster per major
geography (`us-east`, `eu-west`, `ap-south`, …). GeoDNS routes each client
to its nearest region. `kfc-matchmaker` prefers same-region pairing and
only matches cross-region when no same-region partner appears within a
short wait window (3–5s). Redis (ADR-003) replicates presence data
cross-region so a spectator or reconnect request can still resolve a room
hosted in another region.

- K3s (single binary, embedded state store, no bundled cloud integrations)
  is used for smaller/edge regional points-of-presence; full managed K8s
  (EKS/GKE/AKS) is used for major regions. Same container images, same
  manifests (templated via Helm/Kustomize), different cluster footprint —
  this is an infrastructure-sizing choice, not an architectural fork.

**Consequences.**
- *Accepted cost:* N clusters to operate instead of one, and genuine
  cross-region coordination (Redis replication, GeoDNS) instead of a
  single control plane.
- *Benefit:* ~12 Gbps in one place becomes a few hundred Mbps–few Gbps per
  region; a regional outage never cascades (no cross-region synchronous
  dependency on the hot path — see ADR-008 and Part 1 resilience notes
  folded into ADR-007).

---

## ADR-005: Live match state is in-memory only — no volume, no per-match durability

**Status:** Decided.

**Context.** 5,000,000 concurrent games at ~60s average lifetime means the
system creates and tears down rooms at:

```
5,000,000 games / 60s ≈ 83,000 room creations/sec
```

The reflexive instinct — "a match has state, state gets a volume" — is
wrong at this rate. Persisting every match's live state (or running one
container per match, `server/game/match.py`'s `MatchSession` promoted to a
process) would mean ~83k container-creations/sec or ~83k
volume-provisioning operations/sec, either of which is orders of magnitude
too slow and too heavy for an object that may live 30 seconds.

**Decision.** A live match is an in-memory task inside an already-running
`kfc-game-server` pod (one pod hosts many rooms, the same relationship
`GameEngine.advance_time` already has to many concurrent motions, one
level up). It is:

- **Not written to a `PersistentVolumeClaim`.** No Docker volume, no disk
  I/O, for the duration of the match.
- **Not synchronously written to Postgres.** Only a durable event stream
  receives per-move events (ADR-008); the database is updated
  asymptotically after the match ends.
- **Lost on pod crash, by design.** If a `kfc-game-server` pod dies
  mid-match, both clients' Gateway connections detect the lost
  room-heartbeat, surface a `room_lost` event, and both players are
  automatically re-queued by `kfc-matchmaker`.

**Consequences.**
- *Accepted cost:* a rare pod crash loses in-flight matches (a handful of
  60-second games in a fleet of thousands of pods) rather than resuming
  them. This is a deliberate, bounded cost, not an oversight.
- *Benefit:* room creation/teardown pays zero disk or volume-provisioning
  cost, which is the only way 83k/sec is sustainable; Game Server pods are
  trivially reschedulable (no volume to reattach), which is what makes
  ADR-007's graceful draining simple instead of a live-migration problem.

---

## ADR-006: Binary wire protocol over JSON

**Status:** Decided.

**Context.** `server/core/protocol.py` currently encodes/decodes JSON
envelopes over `websockets`. That's the right choice for development
ergonomics and the current single-digit-connection test suite. At
5,000,000 moves/sec, a JSON move message (~80–100 bytes payload, ~150
bytes on the wire with framing/headers) costs **~6 Gbps inbound / ~12 Gbps
total**, against **~4 Gbps total** for a packed binary frame (square as 6
bits, piece type as a few bits, fixed-size, no key names) — roughly a 3x
reduction.

**Decision.** The production wire protocol between client↔`kfc-gateway`
and internally between `kfc-gateway`↔`kfc-game-server` for move traffic is
a fixed-size binary frame, not JSON. `server/core/protocol.py`'s envelope
*shape* (command type, payload, correlation id) is preserved conceptually,
but its encoding is replaced for the high-frequency move path. Low-
frequency messages (auth, matchmaking requests, room admin) may remain
JSON — they don't move the traffic number.

**Consequences.**
- *Accepted cost:* a protocol version negotiation step at connection time,
  and less human-debuggable wire traffic (needs a decoder tool, no more
  reading frames in a browser dev-console network tab).
- *Benefit:* ~3x reduction in the dominant traffic source, which is the
  cheapest lever available (a protocol decision) compared to the
  alternative (more ingress capacity) for the same load.

---

## ADR-007: Graceful draining, not eviction, for the Game Server tier

**Status:** Decided.

**Context.** `kfc-game-server` is the one stateful compute tier
(ADR-002/ADR-005). Standard Kubernetes rolling updates and scale-down
`SIGTERM` a pod and give it a short grace period before `SIGKILL` — fine
for `kfc-gateway`/`kfc-matchmaker`, unacceptable for a pod mid-match,
because killing it triggers the `room_lost` fallback (ADR-005) for every
room it holds, not just the rare crash case.

**Decision.** Exploit the fact that no match outlives 90 seconds:

1. `kfc-game-server` exposes a `preStop` hook that deregisters the pod
   from `kfc-matchmaker`'s capacity pool (stop accepting *new* rooms) but
   keeps serving in-flight rooms.
2. `terminationGracePeriodSeconds: 120` — comfortably above the 90s
   worst-case match length — gives Kubernetes patience to wait instead of
   force-killing.
3. The hook polls the pod's own in-flight room count and exits as soon as
   it reaches zero (typically well under the grace period, since the
   average match is 60s).
4. `RollingUpdate` with `maxUnavailable: 0` plus a `PodDisruptionBudget`
   ensures voluntary disruptions (deploys, node drains, cluster-autoscaler
   scale-down) never remove capacity faster than new capacity replaces it.

Exact manifests and the `drain.sh` script are in Part 2 §4.

**Consequences.**
- *Accepted cost:* deploys take longer than an instant restart (up to ~2
  minutes per pod to fully drain) and require the extra `preStop`/health
  endpoint surface on `kfc-game-server`.
- *Benefit:* genuinely zero-downtime deploys and scale-downs for the one
  tier where "downtime" means "dropped a live game" — this is the direct
  payoff of ADR-005's short-lived, in-memory-only room design.

---

## ADR-008: Event sourcing between Game Server and the database

**Status:** Decided.

**Context.** `server/game/events.py` and the engine's own
`MoveAccepted`/`PieceCaptured`/`GameOver` events (see `CLAUDE.md`'s event
system section) already decouple score/history bookkeeping from the core
simulation loop *within* one process, via `EventManager`. Writing every
move synchronously to Postgres from `kfc-game-server` would mean 5,000,000
DB writes/sec — an unnecessary and unsustainable load, since only the
*result* of a match (not every intermediate move) needs to land durably
in the user-facing database on the timescale players care about.

**Decision.** `kfc-game-server` publishes the same domain events it
already produces onto a durable, ordered event bus (Kafka topic or Redis
Stream) instead of writing to Postgres directly. A separate,
independently-scaled pool of `kfc-event-consumer` pods drains that bus,
batches records, and writes final match results, rating deltas
(`server/rating/elo.py`), and move history to Postgres asynchronously.

This drops the write rate the database actually sees from 5,000,000/sec
to ~83,000 game-results/sec (ADR-005's room-creation rate), further
reduced by batching in `kfc-event-consumer` before it hits Postgres.

**Consequences.**
- *Accepted cost:* match results are eventually consistent in Postgres —
  a player's profile page may lag their just-finished match by up to a
  few seconds (consumer lag), not reflect it instantaneously.
- *Benefit:* the database write path scales independently of move
  frequency, and this is the same architectural pattern (`EventManager`)
  already proven inside the engine — extended across a process boundary
  rather than reinvented.

---

# Part 2: Concrete Implementation and Execution Plan

## 1. Project / library structure

The single `server/` package is retired in favor of one directory per
deployable service, plus shared libraries that no service owns
exclusively. `chess_engine/` does not move — every service that needs it
depends on it as-is, unchanged, exactly as `app_gateways/text_cli` and
`app_gateways/gui` already do today.

```
Kong_fu_chess/
├── chess_engine/                  # UNCHANGED — engine, rules, events, wire notation
│   ├── engine/
│   ├── input/
│   ├── model/
│   ├── realtime/
│   ├── rules/
│   └── wire/
│
├── app_gateways/                  # UNCHANGED — local text CLI / OpenCV GUI clients
│   ├── text_cli/
│   └── gui/
│
├── libs/                          # Shared code, imported by 2+ services, owned by none
│   ├── kfc_common/
│   │   ├── protocol.py            # binary wire frame (ADR-006), envelope shape
│   │   ├── auth.py                # from server/auth/* — hashing, token validation
│   │   ├── config.py              # env-var driven settings (12-factor), replaces server/config.py
│   │   └── logging.py             # structured JSON logging, trace-id propagation
│   └── kfc_proto/                 # generated types (protobuf/flatbuffers) shared gateway<->game-server
│
├── services/
│   ├── kfc-gateway/                        # ADR-002, ADR-006
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── src/kfc_gateway/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                     # entrypoint: serve_forever()
│   │   │   ├── connection_handler.py       # from server/network/server.py
│   │   │   ├── dispatch.py                 # from server/network/dispatch.py
│   │   │   ├── session.py                  # from server/network/session.py
│   │   │   ├── presence_client.py          # Redis presence lookups (ADR-003)
│   │   │   └── health.py                   # /healthz/live, /healthz/ready, /metrics
│   │   └── tests/
│   │
│   ├── kfc-matchmaker/                     # ADR-002, ADR-003
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── src/kfc_matchmaker/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── queue.py                    # from server/matchmaking/queue.py, Redis-backed
│   │   │   ├── matchmaker.py               # from server/matchmaking/matchmaker.py
│   │   │   ├── rooms.py                    # from server/rooms/*
│   │   │   ├── capacity_pool.py            # tracks kfc-game-server pod capacity
│   │   │   └── health.py
│   │   └── tests/
│   │
│   ├── kfc-game-server/                    # ADR-002, ADR-005, ADR-007
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── src/kfc_game_server/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── room_registry.py            # from server/game/registry.py — LOCAL rooms only
│   │   │   ├── match_session.py            # from server/game/match.py
│   │   │   ├── engine_bridge.py            # from server/game/engine_bridge.py (imports chess_engine)
│   │   │   ├── engine_factory.py           # from server/game/engine_factory.py
│   │   │   ├── event_publisher.py          # publishes to Kafka/Redis Streams (ADR-008)
│   │   │   ├── admin.py                    # /admin/drain, /admin/capacity — used by preStop hook
│   │   │   └── health.py
│   │   └── tests/
│   │
│   ├── kfc-event-consumer/                 # ADR-002, ADR-008
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── src/kfc_event_consumer/
│   │   │   ├── __init__.py
│   │   │   ├── main.py
│   │   │   ├── consumer.py                 # Kafka/Redis Streams consumer group
│   │   │   ├── batch_writer.py             # batches into Postgres
│   │   │   ├── matches_repository.py       # from server/db/matches_repository.py
│   │   │   ├── users_repository.py         # from server/db/users_repository.py
│   │   │   ├── rating.py                   # from server/rating/elo.py
│   │   │   └── health.py
│   │   └── tests/
│   │
│   └── kfc-migrations/                     # Alembic migrations for Postgres (ADR-001)
│       ├── alembic.ini
│       └── versions/
│
├── deploy/
│   ├── docker-compose.yml                  # local dev — Part 2 §3
│   ├── compose.env.example
│   └── k8s/
│       ├── base/                           # Kustomize base manifests — Part 2 §4
│       │   ├── namespace.yaml
│       │   ├── gateway/
│       │   │   ├── deployment.yaml
│       │   │   ├── service.yaml
│       │   │   └── hpa.yaml
│       │   ├── matchmaker/
│       │   │   ├── deployment.yaml
│       │   │   ├── service.yaml
│       │   │   └── hpa.yaml
│       │   ├── game-server/
│       │   │   ├── deployment.yaml
│       │   │   ├── service.yaml
│       │   │   ├── hpa.yaml
│       │   │   ├── pdb.yaml
│       │   │   └── drain.sh
│       │   ├── event-consumer/
│       │   │   ├── deployment.yaml
│       │   │   └── hpa.yaml
│       │   └── redis/
│       │       └── statefulset.yaml
│       └── overlays/
│           ├── us-east/
│           ├── eu-west/
│           └── ap-south/
│
├── chess_engine/tests/ ...
├── app_gateways/*/tests/ ...
├── CLAUDE.md
├── README.md
└── Server_Design.md
```

**Mapping note (traceability from ADR-002):** every file under
`services/*/src/` that isn't new infrastructure code (health checks, Redis
clients, event publishing) is a near-direct move of an existing
`server/*` module, renamed into its new service, with in-process function
calls at the old boundaries replaced by network calls (WebSocket/Redis/
Kafka) at the new ones. `chess_engine/` and `app_gateways/` are untouched —
this refactor is entirely about how `server/` is hosted and split, not
about game logic.

---

## 2. Container and Docker implementation

### 2.1 Dockerfile pattern (all four services)

Every service follows the same multi-stage shape: a `builder` stage
installs dependencies into a venv (mirroring this repo's existing
`./venv` convention), and a slim runtime stage copies only the venv plus
application code — small final image, no build toolchain in production,
reproducible pinned dependencies.

**`services/kfc-gateway/Dockerfile`**

```dockerfile
# ---- builder ----
FROM python:3.12-slim AS builder

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY services/kfc-gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- runtime ----
FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 kfc
WORKDIR /app

COPY --from=builder /venv /venv
COPY libs/kfc_common /app/libs/kfc_common
COPY chess_engine /app/chess_engine
COPY services/kfc-gateway/src/kfc_gateway /app/kfc_gateway

ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

USER kfc
EXPOSE 8080 9090

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9090/healthz/live')" || exit 1

ENTRYPOINT ["python", "-m", "kfc_gateway.main"]
```

**`services/kfc-game-server/Dockerfile`** — same shape, with the engine
copied in (it's a dependency, not vendored separately) and no `EXPOSE` of
a public port, since it's only reachable from Gateway pods inside the
cluster network:

```dockerfile
FROM python:3.12-slim AS builder

WORKDIR /build
RUN python -m venv /venv
ENV PATH="/venv/bin:$PATH"

COPY services/kfc-game-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim AS runtime

RUN useradd --create-home --uid 10001 kfc
WORKDIR /app

COPY --from=builder /venv /venv
COPY libs/kfc_common /app/libs/kfc_common
COPY chess_engine /app/chess_engine
COPY services/kfc-game-server/src/kfc_game_server /app/kfc_game_server

ENV PATH="/venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONUNBUFFERED=1

USER kfc
EXPOSE 8081 9090

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9090/healthz/live')" || exit 1

ENTRYPOINT ["python", "-m", "kfc_game_server.main"]
```

`kfc-matchmaker` and `kfc-event-consumer` are identical in structure with
their own `requirements.txt`/`src` paths substituted — omitted here for
brevity since they add no new pattern.

### 2.2 Volume strategy (ADR-005, ADR-003, ADR-001)

This is the deliberate rule this project follows — a volume exists only
where losing the data would be worse than the cost of persisting it:

| Component | Volume? | Mechanism |
|---|---|---|
| `kfc-gateway`, `kfc-matchmaker`, `kfc-event-consumer` | **None** | Fully stateless containers; at most an `emptyDir` for scratch space, wiped on pod exit. |
| `kfc-game-server` | **None for match state.** An `emptyDir` volume template only, for local scratch (e.g. crash dumps, temp buffers) — never for room/board state, which stays in process memory and is intentionally lost on crash (ADR-005). | `emptyDir: {}` in the pod spec — ephemeral by construction, not a `PersistentVolumeClaim`. |
| Redis (presence + matchmaking queue, ADR-003) | **Yes** | `StatefulSet` with `volumeClaimTemplates`, one PVC per replica, RDB snapshot + AOF for crash recovery. |
| Postgres (users, ratings, match history, ADR-001) | **Yes, but managed by the cloud provider** | Not a raw K8s PVC — Aurora/Cloud SQL storage, backups, and failover are the provider's job, deliberately kept outside the cluster's own volume story. |
| Container images | **Read-only, immutable layers** | A rolling deploy replaces the image; nothing mutates a running container's filesystem. |
| Logs | **None** | stdout/stderr shipped off-pod immediately by a node-level Fluent Bit agent — pod filesystems are ephemeral by Kubernetes design. |

The two volume-bearing manifests referenced above (`postgres` is
external/managed and has no manifest in this repo; Redis's
`StatefulSet` does) are given in full in Part 2 §4.4. `kfc-game-server`'s
pod template explicitly declares only an `emptyDir`, never a
`PersistentVolumeClaim` — see Part 2 §4.3.

---

## 3. Local development setup (Docker Compose)

`deploy/docker-compose.yml` brings up the full stack — Postgres, Redis, and
all four services — on a developer machine, wired the same way production
is wired (same images, same env-var driven config from `kfc_common.config`),
just without Kubernetes.

```yaml
# deploy/docker-compose.yml
version: "3.9"

x-python-common: &python-common
  environment:
    PYTHONUNBUFFERED: "1"
    LOG_LEVEL: "debug"

services:
  postgres:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: kfchess
      POSTGRES_USER: kfchess
      POSTGRES_PASSWORD: kfchess_dev_password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U kfchess"]
      interval: 5s
      timeout: 3s
      retries: 10

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: ["redis-server", "--appendonly", "yes"]
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10

  kfc-migrations:
    build:
      context: ..
      dockerfile: services/kfc-migrations/Dockerfile
    <<: *python-common
    environment:
      DATABASE_URL: postgresql://kfchess:kfchess_dev_password@postgres:5432/kfchess
    depends_on:
      postgres:
        condition: service_healthy
    command: ["alembic", "upgrade", "head"]
    restart: "no"

  kfc-gateway:
    build:
      context: ..
      dockerfile: services/kfc-gateway/Dockerfile
    <<: *python-common
    environment:
      HOST: "0.0.0.0"
      PORT: "8080"
      REDIS_URL: redis://redis:6379/0
      MATCHMAKER_URL: kfc-matchmaker:9091
      GAME_SERVER_DISCOVERY: redis   # gateway resolves rooms via Redis presence
    ports:
      - "8080:8080"   # client-facing WebSocket
      - "9090:9090"   # /healthz, /metrics
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  kfc-matchmaker:
    build:
      context: ..
      dockerfile: services/kfc-matchmaker/Dockerfile
    <<: *python-common
    environment:
      REDIS_URL: redis://redis:6379/0
      QUEUE_ELO_RANGE: "100"
      QUEUE_POLL_INTERVAL_SECONDS: "1.0"
      QUEUE_TIMEOUT_SECONDS: "60.0"
    ports:
      - "9091:9091"
      - "9190:9090"   # /healthz, /metrics (host port shifted to avoid clash)
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped

  kfc-game-server:
    build:
      context: ..
      dockerfile: services/kfc-game-server/Dockerfile
    <<: *python-common
    environment:
      REDIS_URL: redis://redis:6379/0
      TICK_MS: "50"
      EVENT_BUS_URL: redis://redis:6379/1   # Redis Streams standing in for Kafka locally
      MAX_ROOMS_PER_POD: "1500"
    ports:
      - "8081:8081"
      - "9290:9090"
    depends_on:
      redis:
        condition: service_healthy
    restart: unless-stopped
    deploy:
      replicas: 2   # simulate >1 game-server pod locally

  kfc-event-consumer:
    build:
      context: ..
      dockerfile: services/kfc-event-consumer/Dockerfile
    <<: *python-common
    environment:
      DATABASE_URL: postgresql://kfchess:kfchess_dev_password@postgres:5432/kfchess
      EVENT_BUS_URL: redis://redis:6379/1
      ELO_K_FACTOR: "32"
    ports:
      - "9390:9090"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      kfc-migrations:
        condition: service_completed_successfully
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

Bring the whole stack up locally with:

```bash
docker compose -f deploy/docker-compose.yml up --build
```

A local text/GUI client (`app_gateways/text_cli`, `app_gateways/gui`)
points at `ws://localhost:8080` exactly as it points at the monolith's
`server/config.py` `HOST`/`PORT` today — from the client's point of view,
nothing about the protocol changed, only what's behind the socket.

---

## 4. Production orchestration (Kubernetes / K3s manifests)

All manifests below live under `deploy/k8s/base/` and are templated per
region via Kustomize overlays (`deploy/k8s/overlays/us-east/`, etc.), per
ADR-004. Namespace: `kfchess`.

### 4.1 Gateway — Deployment, Service, HPA

```yaml
# deploy/k8s/base/gateway/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kfc-gateway
  namespace: kfchess
  labels: { app: kfc-gateway }
spec:
  replicas: 20
  selector:
    matchLabels: { app: kfc-gateway }
  strategy:
    type: RollingUpdate
    rollingUpdate: { maxUnavailable: 10%, maxSurge: 25% }
  template:
    metadata:
      labels: { app: kfc-gateway }
    spec:
      containers:
        - name: kfc-gateway
          image: registry.internal/kfc-gateway:1.0.0
          ports:
            - { name: ws, containerPort: 8080 }
            - { name: metrics, containerPort: 9090 }
          envFrom:
            - configMapRef: { name: kfc-gateway-config }
            - secretRef: { name: kfc-redis-credentials }
          resources:
            requests: { cpu: "500m", memory: "256Mi" }
            limits: { cpu: "2", memory: "512Mi" }
          readinessProbe:
            httpGet: { path: /healthz/ready, port: metrics }
            periodSeconds: 5
          livenessProbe:
            httpGet: { path: /healthz/live, port: metrics }
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: kfc-gateway
  namespace: kfchess
spec:
  type: ClusterIP
  selector: { app: kfc-gateway }
  ports:
    - { name: ws, port: 8080, targetPort: 8080 }
    - { name: metrics, port: 9090, targetPort: 9090 }
```

```yaml
# deploy/k8s/base/gateway/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: kfc-gateway-hpa
  namespace: kfchess
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: kfc-gateway }
  minReplicas: 20
  maxReplicas: 2000
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 60 } }
    - type: Pods
      pods:
        metric: { name: websocket_open_connections }
        target: { type: AverageValue, averageValue: "5000" }
  behavior:
    scaleUp: { stabilizationWindowSeconds: 15, policies: [{ type: Percent, value: 100, periodSeconds: 30 }] }
    scaleDown: { stabilizationWindowSeconds: 300 }
```

`kfc-matchmaker`'s Deployment/Service/HPA follow the identical shape, with
`websocket_open_connections` replaced by a `matchmaking_queue_depth`
custom metric as the scaling signal (ADR-003), and no client-facing port.

### 4.2 Game Server — Deployment with graceful drain (ADR-007)

```yaml
# deploy/k8s/base/game-server/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kfc-game-server
  namespace: kfchess
  labels: { app: kfc-game-server }
spec:
  replicas: 500
  selector:
    matchLabels: { app: kfc-game-server }
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 0     # never drop capacity mid-rollout — ADR-007
      maxSurge: 10%
  template:
    metadata:
      labels: { app: kfc-game-server }
    spec:
      terminationGracePeriodSeconds: 120   # > 90s worst-case match length — ADR-007
      containers:
        - name: kfc-game-server
          image: registry.internal/kfc-game-server:1.0.0
          ports:
            - { name: internal-ws, containerPort: 8081 }
            - { name: metrics, containerPort: 9090 }
          envFrom:
            - configMapRef: { name: kfc-game-server-config }
            - secretRef: { name: kfc-redis-credentials }
          volumeMounts:
            - { name: scratch, mountPath: /tmp/kfc-scratch }
          resources:
            requests: { cpu: "1", memory: "1Gi" }
            limits: { cpu: "4", memory: "2Gi" }
          readinessProbe:
            httpGet: { path: /healthz/ready, port: metrics }
            periodSeconds: 5
          livenessProbe:
            httpGet: { path: /healthz/live, port: metrics }
            periodSeconds: 10
          lifecycle:
            preStop:
              exec:
                command: ["/app/scripts/drain.sh"]
      volumes:
        - name: scratch
          emptyDir: {}   # ADR-005 / Part 2 §2.2 — scratch only, never room state
---
apiVersion: v1
kind: Service
metadata:
  name: kfc-game-server
  namespace: kfchess
spec:
  type: ClusterIP
  clusterIP: None      # headless — Gateway resolves specific pods via presence registry, not round-robin
  selector: { app: kfc-game-server }
  ports:
    - { name: internal-ws, port: 8081, targetPort: 8081 }
    - { name: metrics, port: 9090, targetPort: 9090 }
```

**`deploy/k8s/base/game-server/drain.sh`** — the exact graceful-drain
mechanism referenced in ADR-007:

```bash
#!/usr/bin/env bash
# preStop hook for kfc-game-server. Runs on SIGTERM (rollout, scale-down,
# node drain). Stops taking NEW rooms immediately, then waits for
# in-flight rooms to finish naturally (max ~90s) before letting the
# container exit, so Kubernetes never kills a pod mid-match.
set -euo pipefail

ADMIN_URL="http://localhost:9090"
POLL_INTERVAL_SECONDS=2
# terminationGracePeriodSeconds is 120s; stop polling with margin to spare
MAX_WAIT_SECONDS=110

echo "[drain] deregistering from matchmaker capacity pool"
curl -fsS -X POST "${ADMIN_URL}/admin/drain/start" >/dev/null

elapsed=0
while (( elapsed < MAX_WAIT_SECONDS )); do
  in_flight=$(curl -fsS "${ADMIN_URL}/admin/rooms/count" | python3 -c "import sys,json; print(json.load(sys.stdin)['count'])")
  echo "[drain] in-flight rooms: ${in_flight} (elapsed ${elapsed}s)"
  if [[ "${in_flight}" -eq 0 ]]; then
    echo "[drain] all rooms finished, exiting cleanly"
    exit 0
  fi
  sleep "${POLL_INTERVAL_SECONDS}"
  elapsed=$(( elapsed + POLL_INTERVAL_SECONDS ))
done

echo "[drain] grace period nearly exhausted with ${in_flight} room(s) still active — exiting anyway"
exit 0
```

`/admin/drain/start` (implemented in `kfc_game_server/admin.py`) does two
things synchronously before returning: it removes the pod from
`kfc-matchmaker`'s capacity pool in Redis (so no *new* room is ever
assigned to it after this point), and flips a local flag that
`/admin/rooms/count` reads. Both endpoints are on the same `metrics` port
already used for health checks — no new port to open.

```yaml
# deploy/k8s/base/game-server/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: kfc-game-server-hpa
  namespace: kfchess
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: kfc-game-server }
  minReplicas: 500
  maxReplicas: 20000
  metrics:
    - type: Resource
      resource: { name: cpu, target: { type: Utilization, averageUtilization: 65 } }
    - type: Pods
      pods:
        metric: { name: in_flight_rooms }
        target: { type: AverageValue, averageValue: "1500" }
  behavior:
    scaleUp: { stabilizationWindowSeconds: 15, policies: [{ type: Percent, value: 50, periodSeconds: 30 }] }
    scaleDown: { stabilizationWindowSeconds: 600 }   # slow — let draining pods actually finish
```

```yaml
# deploy/k8s/base/game-server/pdb.yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: kfc-game-server-pdb
  namespace: kfchess
spec:
  minAvailable: 90%
  selector:
    matchLabels: { app: kfc-game-server }
```

### 4.3 Confirming the volume rule at the manifest level

Note what is absent from `game-server/deployment.yaml` above: no
`volumeClaimTemplates`, no `PersistentVolumeClaim`. The only `volumes:`
entry is `emptyDir: {}` for scratch space. This is the manifest-level
enforcement of ADR-005 — a room's board/motion/cooldown state exists only
in the container's process memory and is gone the moment the container
exits, by construction, not by omission.

### 4.4 Redis — StatefulSet with persistent volumes (ADR-003)

```yaml
# deploy/k8s/base/redis/statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kfc-redis
  namespace: kfchess
spec:
  serviceName: kfc-redis
  replicas: 6   # 3 shards x (1 primary + 1 replica)
  selector:
    matchLabels: { app: kfc-redis }
  template:
    metadata:
      labels: { app: kfc-redis }
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          args: ["--appendonly", "yes", "--cluster-enabled", "yes"]
          ports:
            - { name: redis, containerPort: 6379 }
            - { name: cluster-bus, containerPort: 16379 }
          volumeMounts:
            - { name: redis-data, mountPath: /data }
          resources:
            requests: { cpu: "500m", memory: "2Gi" }
            limits: { cpu: "2", memory: "4Gi" }
  volumeClaimTemplates:
    - metadata: { name: redis-data }
      spec:
        accessModes: ["ReadWriteOnce"]
        storageClassName: fast-ssd
        resources:
          requests: { storage: 20Gi }
```

Postgres has no manifest here by design (ADR-001/§2.2): it is provisioned
and operated as a managed cloud service, referenced by connection string
via a `Secret`, not run as a workload inside the cluster.

### 4.5 Event Consumer

```yaml
# deploy/k8s/base/event-consumer/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kfc-event-consumer
  namespace: kfchess
spec:
  replicas: 10
  selector:
    matchLabels: { app: kfc-event-consumer }
  template:
    metadata:
      labels: { app: kfc-event-consumer }
    spec:
      containers:
        - name: kfc-event-consumer
          image: registry.internal/kfc-event-consumer:1.0.0
          envFrom:
            - configMapRef: { name: kfc-event-consumer-config }
            - secretRef: { name: kfc-postgres-credentials }
            - secretRef: { name: kfc-redis-credentials }
          resources:
            requests: { cpu: "500m", memory: "512Mi" }
            limits: { cpu: "2", memory: "1Gi" }
```

```yaml
# deploy/k8s/base/event-consumer/hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: kfc-event-consumer-hpa
  namespace: kfchess
spec:
  scaleTargetRef: { apiVersion: apps/v1, kind: Deployment, name: kfc-event-consumer }
  minReplicas: 10
  maxReplicas: 200
  metrics:
    - type: Pods
      pods:
        metric: { name: event_bus_consumer_lag }
        target: { type: AverageValue, averageValue: "5000" }
```

---

## 5. Step-by-step deployment and execution checklist

A chronological build path from the current monolith to the running
production platform. Each phase is independently verifiable before moving
to the next.

**Phase 0 — Baseline (today)**
- [ ] Confirm `./venv/Scripts/python.exe -m pytest -q` passes on `main`
      (existing `server/` + `chess_engine/` test suites green).
- [ ] Tag this state as the reference implementation for behavior
      parity — every extracted service must match it functionally.

**Phase 1 — Extract libraries and services (code, no infra yet)**
- [ ] Create `libs/kfc_common/` and move `server/config.py` →
      `kfc_common/config.py`, converting hardcoded values (`HOST`, `PORT`,
      `DB_PATH`, …) to environment-variable-driven settings (12-factor).
- [ ] Create `libs/kfc_common/auth.py` from `server/auth/hashing.py` +
      relevant parts of `service.py`.
- [ ] Create the four `services/kfc-*/src` packages per the Part 2 §1
      layout, moving (not rewriting) the corresponding `server/*` modules.
- [ ] Replace in-process calls at the old module boundaries
      (`registry.py` lookups, `queue.py` pushes) with a Redis client
      (ADR-003) behind the same function signatures where possible, to
      keep the diff reviewable.
- [ ] Introduce the binary frame codec in `kfc_common/protocol.py`
      (ADR-006), behind a protocol-version flag, so JSON remains available
      for local debugging.
- [ ] Add `kfc_game_server/event_publisher.py` publishing the engine's
      existing `MoveAccepted`/`PieceCaptured`/`GameOver` events (already
      defined per `CLAUDE.md`) onto Redis Streams/Kafka (ADR-008).
- [ ] Unit-test each service package in isolation (`services/kfc-*/tests`),
      mocking Redis/Postgres/Kafka at the boundary.

**Phase 2 — Data layer migration (ADR-001)**
- [ ] Stand up a managed Postgres instance (dev/staging tier first).
- [ ] Write Alembic migrations under `services/kfc-migrations/versions/`
      reproducing `server/db/schema.py`'s schema.
- [ ] Point `kfc_event_consumer`'s `users_repository.py` /
      `matches_repository.py` (ported from `server/db/*`) at Postgres via
      `asyncpg`/SQLAlchemy instead of `sqlite3`.
- [ ] Run a data migration script, one-time, from `server/kfchess.db` into
      the new Postgres instance for any data worth carrying over from
      development/staging.

**Phase 3 — Containerize (Part 2 §2)**
- [ ] Write and build each `Dockerfile`; verify image size and a clean
      `docker run` boot for each service against a local Redis/Postgres.
- [ ] Wire up `deploy/docker-compose.yml` (Part 2 §3); run the full local
      stack and validate an end-to-end match: connect two
      `app_gateways/text_cli` clients through `kfc-gateway`, matched via
      `kfc-matchmaker`, played on `kfc-game-server`, result persisted by
      `kfc-event-consumer`.
- [ ] Add the same `docker compose up` flow to CI as an integration-test
      stage, replacing/augmenting the current in-process integration
      tests (`server/tests/test_integration_phase1.py`,
      `test_integration_phase2.py`).

**Phase 4 — Cluster provisioning**
- [ ] Provision the first regional cluster (start with one region, e.g.
      `us-east`, full managed K8s) via Infrastructure-as-Code (Terraform).
- [ ] Install cluster add-ons: metrics-server, `prometheus-adapter` (for
      custom-metric HPAs), an Ingress controller, Fluent Bit (log
      shipping), Prometheus + Grafana.
- [ ] Apply `deploy/k8s/base/namespace.yaml` and the Redis
      `StatefulSet` (§4.4); verify Redis Cluster health before deploying
      anything that depends on it.
- [ ] Create `Secret`s for Postgres and Redis credentials
      (`kfc-postgres-credentials`, `kfc-redis-credentials`), sourced from
      the cluster's secret manager (Vault/cloud KMS), never committed to
      the repo.

**Phase 5 — Deploy services (Part 2 §4)**
- [ ] Apply `kfc-event-consumer` first (no player-facing dependency on
      it existing yet) and confirm it drains a synthetic event and writes
      to Postgres.
- [ ] Apply `kfc-game-server`; confirm `/healthz/ready`, `/admin/drain/start`,
      and `/admin/rooms/count` all respond before allowing traffic.
- [ ] Apply `kfc-matchmaker`, confirm it can see `kfc-game-server`
      capacity in Redis.
- [ ] Apply `kfc-gateway` last; confirm it can open a WebSocket, run
      login/matchmaking/a full match end-to-end against the real cluster.
- [ ] Apply all `HorizontalPodAutoscaler` and `PodDisruptionBudget`
      resources; verify HPA custom metrics are actually populated
      (`kubectl get hpa` shows real current values, not `<unknown>`).

**Phase 6 — Validate the zero-downtime drain path (ADR-007)**
- [ ] Start a synthetic load test producing continuous matches against
      `kfc-game-server`.
- [ ] Trigger a rolling update (`kubectl rollout restart deployment/kfc-game-server`)
      mid-load and confirm via logs/metrics that: no pod is force-killed
      before its rooms finish, `in_flight_rooms` on draining pods trends
      to zero before pod exit, and the synthetic clients report **zero**
      `room_lost` events attributable to the deploy (as opposed to the
      expected background rate from genuine crashes/chaos testing).

**Phase 7 — Load and chaos testing**
- [ ] Load-test `kfc-gateway`/`kfc-matchmaker` to the HPA's configured
      ceilings and confirm scale-up latency matches expectations (new
      pods `Ready` and absorbing traffic within the ~15s stabilization
      window).
- [ ] Chaos-test `kfc-game-server` pod kills (`SIGKILL`, not graceful) to
      confirm the `room_lost` → auto-requeue path (ADR-005) behaves
      correctly end-to-end, including on the client side.
- [ ] Validate the traffic math from ADR-004/ADR-006 against real
      measurements: confirm actual bytes/sec per Gateway pod under
      synthetic load roughly matches the ~4 Gbps (binary protocol)
      projection at the target CCU, and that per-region ingress capacity
      is provisioned with headroom above it.

**Phase 8 — Repeat for additional regions**
- [ ] Re-run Phases 4–7 for `eu-west`, `ap-south`, and subsequent regions,
      using the same Kustomize base with per-region overlays
      (`deploy/k8s/overlays/<region>/`).
- [ ] Configure GeoDNS across all live regions and confirm client routing
      resolves to the nearest healthy region.
- [ ] Enable cross-region Redis replication for presence lookups (ADR-003)
      and validate a spectator in one region can resolve a room hosted in
      another.

**Phase 9 — Cutover**
- [ ] Run the new platform in shadow (mirrored, non-authoritative) traffic
      alongside the existing monolith, if a live monolith deployment
      exists, comparing outcomes.
- [ ] Cut client traffic over region by region, monitoring the
      dashboards from Phase 7 continuously.
- [ ] Decommission the monolithic `server/` deployment path once all
      regions are stable on the distributed platform; retain `server/` in
      the repo only as the reference/local-dev implementation if useful,
      or remove it once the split services have full behavior parity
      confirmed by Phase 0's baseline.
