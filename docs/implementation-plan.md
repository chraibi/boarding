# Airplane Boarding Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reproduce Steffen's airplane boarding-method comparison in JuPedSim as a reproducible study in `jupedsim-scenarios`, recovering the method *ranking* and *relative* speedups.

**Architecture:** A standalone `boarding/` subpackage builds a parametric single-aisle fuselage (Shapely), generates per-method passenger release orders, and runs a custom direct-steering loop where each agent holds at its row for `luggage_time + seat_interference_penalty` (blocking the aisle behind it) before moving into its seat. A sweep over methods × paired seeds yields boarding times; analysis ranks methods and emits replayable SQLite trajectories.

**Tech Stack:** Python ≥3.11, `jupedsim>=1.4` (raw API, `CollisionFreeSpeedModel`, direct steering), Shapely, pandas, matplotlib, pytest. Reuses `jupedsim_scenarios.direct_steering_runtime` helpers.

**Spec:** `docs/specs/2026-06-10-airplane-boarding-study-design.md`

> **DESIGN REVISION (2026-06-10, as-built):** During Task 5, integration proved that
> direct-steering *seat navigation* in a comb geometry wedges agents (straight-line steering
> drives shoved agents into walls) and produces same-row centreline collisions — 2-D artifacts,
> not boarding physics. The design pivoted to **logical seating**, validated by a 3-row spike and
> the full 30-row study (see `docs/specs/2026-06-10-airplane-boarding-results.md`). The
> **Architecture** paragraph above and **Tasks 2, 4, 5** below describe the original comb-geometry
> approach and are superseded. As built:
> - **Geometry (Task 2):** walkable is an **aisle-only** rectangle. `SeatGeom(aisle_waypoint, seat_coord)`;
>   `seat_coord` is off-aisle and used only for the post-hoc visual, never navigated.
> - **Choreography (Task 4):** **3 states** — `WALK_TO_ROW → HOLD → SEATED`. HOLD keeps targeting the
>   row aisle-point (self-corrects under shoving); no `GO_TO_SEAT`, no `seat_target`.
> - **Run loop (Task 5):** on hold expiry the agent is recorded seated and **`mark_agent_for_removal`** —
>   sitting is logical. Spawn is gated on door clearance + headway.
> - **New module `seat_placement.py`:** `seat_fill_table(result, seat_map)` → DataFrame
>   `[row, side, col, x, y, seat_time]` for the post-hoc "seats filling" animation.
> The canonical description of the as-built design is the spec's "Seating model — logical seating"
> section. Tasks 1, 3, 6, 7, 8, 9 are unaffected.

---

## File Structure

All new files under `src/jupedsim_scenarios/boarding/`:

| File | Responsibility |
|------|----------------|
| `__init__.py` | Public exports for the subpackage. |
| `config.py` | `Seat` dataclass + `BoardingConfig` dataclass (all parameters). |
| `geometry.py` | `build_fuselage(config)` → `(walkable_polygon, seat_map, door_point)`. |
| `methods.py` | One ordering function per boarding method + `METHODS` registry. |
| `choreography.py` | `seat_interference_penalty()`, `luggage_time()`, `AgentPlan` state machine. |
| `experiment.py` | `run_boarding(method, seed, config)` + `sweep(methods, seeds, config)`. |
| `analysis.py` | Ranking table + box plot + seat-time curves. |
| `cli.py` | `python -m jupedsim_scenarios.boarding ...` entry point. |

Tests under `tests/boarding/`: `test_config.py`, `test_geometry.py`, `test_methods.py`, `test_choreography.py`, `test_experiment_smoke.py`.

**Coordinate system:** Aisle runs along **x** from the door (x≈0, front, row 1) to the rear (x≈rows·pitch). Aisle is centered on **y=0** with width `aisle_width`. Left-side seats at y<0, right-side at y>0. Within a row-side, seat column index `col` runs **0=aisle, 1=middle, 2=window** (increasing |y|, i.e. outward from the aisle). "Inboard neighbors" of a seat = same row+side seats with **smaller** `col` (between it and the aisle).

---

### Task 1: Subpackage skeleton + config types

**Files:**
- Create: `src/jupedsim_scenarios/boarding/__init__.py`
- Create: `src/jupedsim_scenarios/boarding/config.py`
- Test: `tests/boarding/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_config.py
from jupedsim_scenarios.boarding.config import BoardingConfig, Seat


def test_default_config_is_180_passengers():
    cfg = BoardingConfig()
    assert cfg.rows == 30
    assert cfg.seats_per_side == 3
    assert cfg.total_passengers == 180


def test_seat_inboard_cols_window_has_two():
    # window (col=2) sits inboard of middle(1) and aisle(0)
    window = Seat(row=5, side="L", col=2)
    assert window.inboard_cols == (0, 1)
    aisle = Seat(row=5, side="L", col=0)
    assert aisle.inboard_cols == ()


def test_seat_is_hashable_and_value_equal():
    assert Seat(1, "R", 0) == Seat(1, "R", 0)
    assert len({Seat(1, "R", 0), Seat(1, "R", 0)}) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: jupedsim_scenarios.boarding`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/config.py
from dataclasses import dataclass


@dataclass(frozen=True)
class Seat:
    """A seat addressed by 1-based row, side ('L'/'R'), and column.

    col: 0 = aisle-adjacent, increasing outward; (seats_per_side-1) = window.
    """

    row: int
    side: str
    col: int

    @property
    def inboard_cols(self) -> tuple[int, ...]:
        """Columns between this seat and the aisle (smaller col, same row+side)."""
        return tuple(range(self.col))


@dataclass(frozen=True)
class BoardingConfig:
    # cabin
    rows: int = 30
    seats_per_side: int = 3
    seat_pitch: float = 0.8        # m, longitudinal row spacing (x)
    seat_width: float = 0.45       # m, lateral width per seat (y)
    seat_block_x: float = 0.45     # m, walkable lateral-slot depth per row (< pitch leaves gaps)
    aisle_width: float = 0.5       # m
    door_depth: float = 1.2        # m, entry corridor length ahead of row 1
    # penalties (Steffen)
    luggage_mean: float = 7.0      # s, gamma mean
    luggage_sd: float = 3.0        # s, gamma std-dev
    seat_penalty: float = 5.0      # s per displaced inboard neighbor
    # dynamics
    dt: float = 0.05               # s
    v0: float = 1.2                # m/s desired speed
    agent_radius: float = 0.18     # m
    arrival_threshold: float = 0.45  # m, "reached row" distance
    spawn_headway: float = 2.0     # s between consecutive boardings at the door
    max_sim_seconds: float = 3600.0

    @property
    def total_passengers(self) -> int:
        return self.rows * self.seats_per_side * 2
```

```python
# src/jupedsim_scenarios/boarding/__init__.py
from .config import BoardingConfig, Seat

__all__ = ["BoardingConfig", "Seat"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_config.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/jupedsim_scenarios/boarding/__init__.py src/jupedsim_scenarios/boarding/config.py tests/boarding/test_config.py
git commit -m "feat(boarding): config + Seat types"
```

---

### Task 2: Parametric fuselage geometry + seat map

**Files:**
- Create: `src/jupedsim_scenarios/boarding/geometry.py`
- Test: `tests/boarding/test_geometry.py`

Geometry is a "comb": a central aisle rectangle (full length) plus, per row and side, a lateral
slot rectangle connecting the aisle to the seat targets. Slots are narrower than the pitch
(`seat_block_x < seat_pitch`), leaving non-walkable gaps between rows so agents cannot walk
along the seats — they must use the aisle and turn off only at their row.

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_geometry.py
import jupedsim as jps
from shapely import Point

from jupedsim_scenarios.boarding.config import BoardingConfig, Seat
from jupedsim_scenarios.boarding.geometry import build_fuselage


def test_seat_map_has_every_seat():
    cfg = BoardingConfig(rows=4)  # smaller cabin, same 3-per-side
    _walkable, seat_map, _door = build_fuselage(cfg)
    assert len(seat_map) == 4 * 3 * 2
    assert Seat(1, "L", 2) in seat_map


def test_seat_targets_and_waypoints_inside_walkable():
    cfg = BoardingConfig(rows=4)
    walkable, seat_map, door = build_fuselage(cfg)
    assert walkable.contains(Point(*door))
    for geom in seat_map.values():
        assert walkable.contains(Point(*geom.seat_target))
        assert walkable.contains(Point(*geom.aisle_waypoint))


def test_every_seat_target_is_routable_from_door():
    cfg = BoardingConfig(rows=4)
    walkable, seat_map, door = build_fuselage(cfg)
    engine = jps.RoutingEngine(walkable)
    assert engine.is_routable(door)
    for geom in seat_map.values():
        assert engine.is_routable(geom.seat_target)


def test_window_target_is_farther_from_aisle_than_aisle_seat():
    cfg = BoardingConfig(rows=4)
    _walkable, seat_map, _door = build_fuselage(cfg)
    window_y = abs(seat_map[Seat(2, "L", 2)].seat_target[1])
    aisle_y = abs(seat_map[Seat(2, "L", 0)].seat_target[1])
    assert window_y > aisle_y
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_geometry.py -v`
Expected: FAIL — `ImportError: cannot import name 'build_fuselage'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/geometry.py
from dataclasses import dataclass

from shapely import Polygon, box, unary_union

from .config import BoardingConfig, Seat


@dataclass(frozen=True)
class SeatGeom:
    aisle_waypoint: tuple[float, float]  # point in the aisle at this row
    seat_target: tuple[float, float]     # point inside the seat


def _row_x(cfg: BoardingConfig, row: int) -> float:
    """Longitudinal centre of a row; row 1 is nearest the door."""
    return cfg.door_depth + (row - 0.5) * cfg.seat_pitch


def build_fuselage(cfg: BoardingConfig):
    """Build (walkable_polygon, seat_map, door_point) for the cabin.

    Aisle along +x; door at x=0. Left seats y<0, right seats y>0.
    """
    half_aisle = cfg.aisle_width / 2.0
    cabin_len = cfg.door_depth + cfg.rows * cfg.seat_pitch

    # Central aisle + door corridor, full length.
    aisle = box(0.0, -half_aisle, cabin_len, half_aisle)

    parts: list[Polygon] = [aisle]
    seat_map: dict[Seat, SeatGeom] = {}
    side_sign = {"L": -1.0, "R": 1.0}
    seat_span = cfg.seats_per_side * cfg.seat_width  # lateral reach of seats

    for row in range(1, cfg.rows + 1):
        cx = _row_x(cfg, row)
        x0 = cx - cfg.seat_block_x / 2.0
        x1 = cx + cfg.seat_block_x / 2.0
        for side, sign in side_sign.items():
            inner = half_aisle
            outer = half_aisle + seat_span
            ylo, yhi = sorted((sign * inner, sign * outer))
            parts.append(box(x0, ylo, x1, yhi))  # lateral slot for this row+side
            for col in range(cfg.seats_per_side):
                # col 0 nearest aisle, increasing outward to window
                seat_centre_y = sign * (half_aisle + (col + 0.5) * cfg.seat_width)
                seat_map[Seat(row, side, col)] = SeatGeom(
                    aisle_waypoint=(cx, 0.0),
                    seat_target=(cx, seat_centre_y),
                )

    walkable = unary_union(parts)
    door_point = (cfg.door_depth * 0.25, 0.0)
    return walkable, seat_map, door_point
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_geometry.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add src/jupedsim_scenarios/boarding/geometry.py tests/boarding/test_geometry.py
git commit -m "feat(boarding): parametric fuselage geometry + seat map"
```

---

### Task 3: Boarding-order generators

**Files:**
- Create: `src/jupedsim_scenarios/boarding/methods.py`
- Test: `tests/boarding/test_methods.py`

Each generator returns a list of `Seat` in **boarding order** (index 0 boards first). The seat
universe is all `(row, side, col)`. `rng` is a seeded `random.Random` for shuffles/tie-breaks.

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_methods.py
import random

from jupedsim_scenarios.boarding.config import BoardingConfig
from jupedsim_scenarios.boarding.methods import METHODS, all_seats


def _cfg():
    return BoardingConfig(rows=6)  # 6 rows -> back-to-front = 1 block of 6 wraps; use blocks of 3


def test_every_method_returns_a_permutation_of_all_seats():
    cfg = _cfg()
    universe = set(all_seats(cfg))
    for name, fn in METHODS.items():
        order = fn(cfg, random.Random(0))
        assert len(order) == len(universe), name
        assert set(order) == universe, name


def test_back_to_front_boards_rear_rows_before_front_rows():
    cfg = _cfg()
    order = METHODS["back_to_front"](cfg, random.Random(0))
    # first-boarded seat must be in a higher row than last-boarded seat
    assert order[0].row > order[-1].row


def test_wilma_boards_all_windows_before_any_aisle():
    cfg = _cfg()
    order = METHODS["wilma"](cfg, random.Random(0))
    last_window = max(i for i, s in enumerate(order) if s.col == 2)
    first_aisle = min(i for i, s in enumerate(order) if s.col == 0)
    assert last_window < first_aisle


def test_steffen_perfect_consecutive_boarders_skip_rows():
    cfg = _cfg()
    order = METHODS["steffen_perfect"](cfg, random.Random(0))
    # In Steffen-perfect no two adjacent boarders share a row (maximal spacing).
    assert all(order[i].row != order[i + 1].row for i in range(len(order) - 1))


def test_methods_are_deterministic_for_a_seed():
    cfg = _cfg()
    a = METHODS["random"](cfg, random.Random(42))
    b = METHODS["random"](cfg, random.Random(42))
    assert a == b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_methods.py -v`
Expected: FAIL — `ImportError: cannot import name 'METHODS'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/methods.py
import random
from collections.abc import Callable

from .config import BoardingConfig, Seat

WINDOW_FIRST = (2, 1, 0)  # col order: window, middle, aisle


def all_seats(cfg: BoardingConfig) -> list[Seat]:
    return [
        Seat(row, side, col)
        for row in range(1, cfg.rows + 1)
        for side in ("L", "R")
        for col in range(cfg.seats_per_side)
    ]


def _shuffled(seats: list[Seat], rng: random.Random) -> list[Seat]:
    out = list(seats)
    rng.shuffle(out)
    return out


def random_order(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    return _shuffled(all_seats(cfg), rng)


def _blocks(cfg: BoardingConfig, block_rows: int) -> list[list[int]]:
    rows = list(range(1, cfg.rows + 1))
    return [rows[i : i + block_rows] for i in range(0, len(rows), block_rows)]


def back_to_front(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    block_rows = max(1, cfg.rows // 6)
    order: list[Seat] = []
    for block in reversed(_blocks(cfg, block_rows)):  # rear block first
        in_block = [s for s in all_seats(cfg) if s.row in block]
        order.extend(_shuffled(in_block, rng))
    return order


def front_to_back(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    block_rows = max(1, cfg.rows // 6)
    order: list[Seat] = []
    for block in _blocks(cfg, block_rows):  # front block first
        in_block = [s for s in all_seats(cfg) if s.row in block]
        order.extend(_shuffled(in_block, rng))
    return order


def wilma(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    order: list[Seat] = []
    for col in WINDOW_FIRST:  # window, then middle, then aisle
        wave = [s for s in all_seats(cfg) if s.col == col]
        rng.shuffle(wave)
        order.extend(wave)
    return order


def steffen_perfect(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    # window->middle->aisle; within a wave, one side then the other,
    # rear->front in steps of 2 (even rows then odd rows) for maximal spacing.
    order: list[Seat] = []
    for col in WINDOW_FIRST:
        for side in ("L", "R"):
            for parity in (0, 1):  # even-indexed rows first, then odd
                rows = [
                    r
                    for r in range(cfg.rows, 0, -1)
                    if (cfg.rows - r) % 2 == parity
                ]
                order.extend(Seat(r, side, col) for r in rows)
    return order


def steffen_modified(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    # Practical 4-group variant: side x parity, each group rear->front, all cols together.
    order: list[Seat] = []
    for side in ("L", "R"):
        for parity in (0, 1):
            rows = [r for r in range(cfg.rows, 0, -1) if (cfg.rows - r) % 2 == parity]
            group = [Seat(r, side, col) for r in rows for col in WINDOW_FIRST]
            order.extend(group)
    return order


METHODS: dict[str, Callable[[BoardingConfig, random.Random], list[Seat]]] = {
    "random": random_order,
    "back_to_front": back_to_front,
    "front_to_back": front_to_back,
    "wilma": wilma,
    "steffen_perfect": steffen_perfect,
    "steffen_modified": steffen_modified,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_methods.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/jupedsim_scenarios/boarding/methods.py tests/boarding/test_methods.py
git commit -m "feat(boarding): per-method boarding-order generators"
```

---

### Task 4: Penalties + agent state machine

**Files:**
- Create: `src/jupedsim_scenarios/boarding/choreography.py`
- Test: `tests/boarding/test_choreography.py`

Pure logic only — no JuPedSim. `seat_interference_penalty` counts already-seated inboard
neighbors. `luggage_time` draws from a gamma matched to (mean, sd). `AgentPlan` is the per-agent
state machine the run loop will drive; here we unit-test its transitions with a fake agent.

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_choreography.py
import random

from jupedsim_scenarios.boarding.choreography import (
    AgentPlan,
    State,
    luggage_time,
    seat_interference_penalty,
)
from jupedsim_scenarios.boarding.config import BoardingConfig, Seat


def test_penalty_counts_seated_inboard_neighbors():
    cfg = BoardingConfig()
    window = Seat(5, "L", 2)
    occupied = {Seat(5, "L", 0), Seat(5, "L", 1)}  # aisle + middle already seated
    assert seat_interference_penalty(window, occupied, cfg) == 2 * cfg.seat_penalty
    # aisle seat never has inboard neighbors
    assert seat_interference_penalty(Seat(5, "L", 0), occupied, cfg) == 0.0
    # empty cabin: no penalty
    assert seat_interference_penalty(window, set(), cfg) == 0.0


def test_luggage_time_matches_mean_within_tolerance():
    cfg = BoardingConfig()
    rng = random.Random(0)
    draws = [luggage_time(cfg, rng) for _ in range(5000)]
    mean = sum(draws) / len(draws)
    assert 6.0 < mean < 8.0
    assert all(d > 0 for d in draws)


class _FakeAgent:
    def __init__(self, x):
        self.position = (x, 0.0)
        self.target = None


def test_plan_walks_then_holds_then_seats():
    cfg = BoardingConfig(dt=1.0, arrival_threshold=0.5)
    seat = Seat(1, "L", 0)
    waypoint = (10.0, 0.0)
    target = (10.0, -0.5)
    plan = AgentPlan(seat=seat, aisle_waypoint=waypoint, seat_target=target,
                     hold_seconds=3.0, dt=cfg.dt)
    far = _FakeAgent(x=0.0)
    plan.step(far, iteration=0, arrival_threshold=cfg.arrival_threshold)
    assert plan.state is State.WALK_TO_ROW
    assert far.target == waypoint

    at_row = _FakeAgent(x=10.0)
    plan.step(at_row, iteration=1, arrival_threshold=cfg.arrival_threshold)
    assert plan.state is State.HOLD  # arrived -> holding, target frozen at current pos

    # hold is 3 seconds at dt=1 -> released on iteration 1+3
    plan.step(at_row, iteration=4, arrival_threshold=cfg.arrival_threshold)
    assert plan.state is State.GO_TO_SEAT
    assert at_row.target == target

    near_seat = _FakeAgent(x=10.0)
    near_seat.position = target
    plan.step(near_seat, iteration=5, arrival_threshold=cfg.arrival_threshold)
    assert plan.state is State.SEATED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_choreography.py -v`
Expected: FAIL — `ImportError: cannot import name 'AgentPlan'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/choreography.py
import enum
import math
import random

from ..direct_steering_runtime import assign_agent_target, extract_agent_xy
from .config import BoardingConfig, Seat


class State(enum.Enum):
    WALK_TO_ROW = enum.auto()
    HOLD = enum.auto()
    GO_TO_SEAT = enum.auto()
    SEATED = enum.auto()


def seat_interference_penalty(
    seat: Seat, occupied: set[Seat], cfg: BoardingConfig
) -> float:
    """5 s per already-seated neighbor between this seat and the aisle."""
    blockers = sum(
        1 for col in seat.inboard_cols if Seat(seat.row, seat.side, col) in occupied
    )
    return blockers * cfg.seat_penalty


def luggage_time(cfg: BoardingConfig, rng: random.Random) -> float:
    """Gamma draw with the configured mean and std-dev (shape=k, scale=theta)."""
    if cfg.luggage_sd <= 0:
        return cfg.luggage_mean
    k = (cfg.luggage_mean / cfg.luggage_sd) ** 2
    theta = (cfg.luggage_sd ** 2) / cfg.luggage_mean
    return rng.gammavariate(k, theta)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class AgentPlan:
    """Per-agent boarding state machine driven once per simulation frame."""

    def __init__(
        self,
        seat: Seat,
        aisle_waypoint: tuple[float, float],
        seat_target: tuple[float, float],
        hold_seconds: float,
        dt: float,
    ) -> None:
        self.seat = seat
        self.aisle_waypoint = aisle_waypoint
        self.seat_target = seat_target
        self.hold_frames = max(1, round(hold_seconds / dt))
        self.state = State.WALK_TO_ROW
        self._release_iter: int | None = None

    def step(self, agent, iteration: int, arrival_threshold: float) -> None:
        pos = extract_agent_xy(agent)
        if self.state is State.WALK_TO_ROW:
            assign_agent_target(agent, self.aisle_waypoint)
            if _dist(pos, self.aisle_waypoint) <= arrival_threshold:
                self.state = State.HOLD
                self._release_iter = iteration + self.hold_frames
                assign_agent_target(agent, pos)  # freeze, block the aisle
        elif self.state is State.HOLD:
            assign_agent_target(agent, pos)  # keep blocking until released
            if iteration >= (self._release_iter or 0):
                self.state = State.GO_TO_SEAT
                assign_agent_target(agent, self.seat_target)
        elif self.state is State.GO_TO_SEAT:
            assign_agent_target(agent, self.seat_target)
            if _dist(pos, self.seat_target) <= arrival_threshold:
                self.state = State.SEATED
        # SEATED: no-op, agent parked off the aisle
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_choreography.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/jupedsim_scenarios/boarding/choreography.py tests/boarding/test_choreography.py
git commit -m "feat(boarding): penalties + per-agent boarding state machine"
```

---

### Task 5: Run loop (`run_boarding`) + smoke test

**Files:**
- Create: `src/jupedsim_scenarios/boarding/experiment.py`
- Test: `tests/boarding/test_experiment_smoke.py`

`run_boarding` builds the simulation, stages agents at the door in method order with a spawn
headway, drives every agent's `AgentPlan` each frame, and stops when all agents are SEATED.
Penalties are computed **at HOLD entry** from live occupancy, so a per-agent hold is set when the
agent reaches its row (see Step 3 — hold_seconds is computed lazily in the loop, not at spawn).

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_experiment_smoke.py
from jupedsim_scenarios.boarding.config import BoardingConfig
from jupedsim_scenarios.boarding.experiment import BoardingResult, run_boarding


def _tiny():
    # 3-row cabin = 18 passengers: fast enough for CI, still exercises the bottleneck.
    return BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=600.0)


def test_run_boarding_seats_everyone():
    cfg = _tiny()
    result = run_boarding("random", seed=0, config=cfg)
    assert isinstance(result, BoardingResult)
    assert result.seated_count == cfg.total_passengers
    assert result.total_time > 0
    assert len(result.seat_times) == cfg.total_passengers


def test_steffen_not_slower_than_front_to_back_on_one_seed():
    cfg = _tiny()
    steffen = run_boarding("steffen_perfect", seed=1, config=cfg).total_time
    f2b = run_boarding("front_to_back", seed=1, config=cfg).total_time
    assert steffen <= f2b
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_experiment_smoke.py -v`
Expected: FAIL — `ImportError: cannot import name 'run_boarding'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/experiment.py
import random
import tempfile
from dataclasses import dataclass
from pathlib import Path

import jupedsim as jps

from .choreography import AgentPlan, State, luggage_time, seat_interference_penalty
from .config import BoardingConfig, Seat
from .geometry import build_fuselage
from .methods import METHODS


@dataclass
class BoardingResult:
    method: str
    seed: int
    total_time: float
    seated_count: int
    seat_times: dict[Seat, float]
    sqlite_path: Path


def _build_simulation(cfg: BoardingConfig, walkable, out_path: Path):
    # Verified against jupedsim 1.4.2: keyword-only Simulation(model=, geometry=, dt=,
    # trajectory_writer=); SqliteTrajectoryWriter(output_file=, every_nth_frame=).
    model = jps.CollisionFreeSpeedModel()
    writer = jps.SqliteTrajectoryWriter(
        output_file=out_path, every_nth_frame=max(1, round(0.1 / cfg.dt))
    )
    sim = jps.Simulation(
        model=model, geometry=walkable, dt=cfg.dt, trajectory_writer=writer
    )
    return sim, writer


def run_boarding(method: str, seed: int, config: BoardingConfig | None = None) -> BoardingResult:
    cfg = config or BoardingConfig()
    rng = random.Random(seed)
    walkable, seat_map, door = build_fuselage(cfg)
    order = METHODS[method](cfg, rng)

    out_path = Path(tempfile.mkdtemp(prefix="boarding_")) / f"{method}_{seed}.sqlite"
    sim, writer = _build_simulation(cfg, walkable, out_path)
    direct = sim.add_direct_steering_stage()
    journey = sim.add_journey(jps.JourneyDescription([direct]))

    agent_params = jps.CollisionFreeSpeedModelAgentParameters(
        journey_id=journey, stage_id=direct, position=door,
        desired_speed=cfg.v0, radius=cfg.agent_radius,
    )

    plans: dict[int, AgentPlan] = {}
    queue = list(order)               # seats waiting to board, in order
    luggage = {s: luggage_time(cfg, rng) for s in order}
    occupied: set[Seat] = set()
    seat_times: dict[Seat, float] = {}

    headway_frames = max(1, round(cfg.spawn_headway / cfg.dt))
    max_iter = round(cfg.max_sim_seconds / cfg.dt)

    iteration = 0
    next_spawn = 0
    while len(seat_times) < cfg.total_passengers and iteration < max_iter:
        # spawn next passenger at the door on schedule, if the door is clear
        if queue and iteration >= next_spawn:
            seat = queue[0]
            agent_params.position = door
            agent_id = sim.add_agent(agent_params)
            geom = seat_map[seat]
            plans[agent_id] = AgentPlan(
                seat=seat, aisle_waypoint=geom.aisle_waypoint,
                seat_target=geom.seat_target, hold_seconds=0.0, dt=cfg.dt,
            )
            queue.pop(0)
            next_spawn = iteration + headway_frames

        for agent_id, plan in plans.items():
            if plan.state is State.SEATED:
                continue
            agent = sim.agent(agent_id)
            prev = plan.state
            plan.step(agent, iteration, cfg.arrival_threshold)
            # compute the real hold the moment the agent starts holding
            if prev is State.WALK_TO_ROW and plan.state is State.HOLD:
                penalty = seat_interference_penalty(plan.seat, occupied, cfg)
                hold_s = luggage[plan.seat] + penalty
                plan.hold_frames = max(1, round(hold_s / cfg.dt))
                plan._release_iter = iteration + plan.hold_frames
            if plan.state is State.SEATED and plan.seat not in seat_times:
                occupied.add(plan.seat)
                seat_times[plan.seat] = iteration * cfg.dt

        sim.iterate()
        iteration += 1

    writer.close()  # verified jupedsim 1.4.2: writer has close(), not end_writing()
    return BoardingResult(
        method=method, seed=seed, total_time=iteration * cfg.dt,
        seated_count=len(seat_times), seat_times=seat_times, sqlite_path=out_path,
    )
```

> **Implementer note (door deadlock — spec open question #1):** if the smoke test stalls (agents
> jam at the door), increase `spawn_headway`, or guard the spawn with a clearance check: only spawn
> when no existing agent is within `2·agent_radius` of `door`. Add the check inside the `if queue`
> block using `extract_agent_xy`. Do not over-engineer before observing an actual stall.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_experiment_smoke.py -v`
Expected: PASS (2 tests). If a test stalls, apply the door-clearance guard from the note above, then re-run.

- [ ] **Step 5: Verify the hold actually blocks followers (spec risk #2)**

Run a quick manual check that a held agent stalls the one behind it:

```bash
python -c "
from jupedsim_scenarios.boarding.config import BoardingConfig
from jupedsim_scenarios.boarding.experiment import run_boarding
r = run_boarding('front_to_back', seed=0, config=BoardingConfig(rows=3, spawn_headway=0.5))
print('seated', r.seated_count, 'time', round(r.total_time,1))
"
```
Expected: `seated 18` and a total time visibly larger than `18 * mean_luggage / parallelism` — i.e. front-to-back is slow because front holds block the rear. Record the number.

- [ ] **Step 6: Commit**

```bash
git add src/jupedsim_scenarios/boarding/experiment.py tests/boarding/test_experiment_smoke.py
git commit -m "feat(boarding): direct-steering run loop with per-agent row holds"
```

---

### Task 6: Sweep over methods × paired seeds

**Files:**
- Modify: `src/jupedsim_scenarios/boarding/experiment.py` (append `sweep`)
- Test: `tests/boarding/test_experiment_smoke.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/boarding/test_experiment_smoke.py
import pandas as pd

from jupedsim_scenarios.boarding.experiment import sweep


def test_sweep_returns_long_dataframe():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    df = sweep(["random", "steffen_perfect"], seeds=[0, 1], config=cfg)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"method", "seed", "total_time"}
    assert len(df) == 2 * 2  # methods x seeds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_experiment_smoke.py::test_sweep_returns_long_dataframe -v`
Expected: FAIL — `ImportError: cannot import name 'sweep'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/jupedsim_scenarios/boarding/experiment.py
from collections.abc import Sequence

import pandas as pd  # add to existing imports at top of file


def sweep(
    methods: Sequence[str],
    seeds: Sequence[int],
    config: BoardingConfig | None = None,
) -> pd.DataFrame:
    """Run every (method, seed) pair; seeds are paired across methods."""
    rows = []
    for seed in seeds:
        for method in methods:
            res = run_boarding(method, seed, config)
            rows.append(
                {
                    "method": method,
                    "seed": seed,
                    "total_time": res.total_time,
                    "seated_count": res.seated_count,
                    "sqlite_path": str(res.sqlite_path),
                }
            )
    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_experiment_smoke.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add src/jupedsim_scenarios/boarding/experiment.py tests/boarding/test_experiment_smoke.py
git commit -m "feat(boarding): sweep over methods x paired seeds"
```

---

### Task 7: Analysis (ranking + plot)

**Files:**
- Create: `src/jupedsim_scenarios/boarding/analysis.py`
- Test: `tests/boarding/test_analysis.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_analysis.py
import pandas as pd

from jupedsim_scenarios.boarding.analysis import ranking_table


def test_ranking_table_sorts_fastest_first():
    df = pd.DataFrame(
        [
            {"method": "slow", "seed": 0, "total_time": 100.0},
            {"method": "slow", "seed": 1, "total_time": 120.0},
            {"method": "fast", "seed": 0, "total_time": 40.0},
            {"method": "fast", "seed": 1, "total_time": 50.0},
        ]
    )
    table = ranking_table(df)
    assert list(table["method"]) == ["fast", "slow"]
    assert table.iloc[0]["mean_time"] == 45.0
    assert {"mean_time", "std_time", "n"} <= set(table.columns)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_analysis.py -v`
Expected: FAIL — `ImportError: cannot import name 'ranking_table'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/analysis.py
from pathlib import Path

import pandas as pd


def ranking_table(df: pd.DataFrame) -> pd.DataFrame:
    """Mean/std boarding time per method, fastest first."""
    grouped = (
        df.groupby("method")["total_time"]
        .agg(mean_time="mean", std_time="std", n="count")
        .reset_index()
        .sort_values("mean_time")
        .reset_index(drop=True)
    )
    grouped["std_time"] = grouped["std_time"].fillna(0.0)
    return grouped


def boxplot_by_method(df: pd.DataFrame, out_path: Path) -> Path:
    """Box plot of total boarding time per method; saves a PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = ranking_table(df)["method"].tolist()
    data = [df.loc[df["method"] == m, "total_time"].to_numpy() for m in order]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(data, labels=order, vert=True)
    ax.set_ylabel("Boarding time (s)")
    ax.set_title("Boarding time by method")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_analysis.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/jupedsim_scenarios/boarding/analysis.py tests/boarding/test_analysis.py
git commit -m "feat(boarding): ranking table + boxplot analysis"
```

---

### Task 8: CLI + public exports

**Files:**
- Create: `src/jupedsim_scenarios/boarding/cli.py`
- Modify: `src/jupedsim_scenarios/boarding/__init__.py`
- Test: `tests/boarding/test_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/boarding/test_cli.py
from jupedsim_scenarios.boarding.cli import build_parser


def test_cli_defaults_to_full_method_set():
    args = build_parser().parse_args([])
    assert "steffen_perfect" in args.methods
    assert "back_to_front" in args.methods
    assert args.seeds == 20  # default replication
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/boarding/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: ...boarding.cli`

- [ ] **Step 3: Write minimal implementation**

```python
# src/jupedsim_scenarios/boarding/cli.py
import argparse
from pathlib import Path

from .analysis import boxplot_by_method, ranking_table
from .config import BoardingConfig
from .experiment import sweep
from .methods import METHODS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Steffen airplane boarding-method study.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--seeds", type=int, default=20, help="number of paired seeds")
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("boarding_out"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df = sweep(args.methods, seeds=list(range(args.seeds)), config=cfg)
    df.to_csv(args.out / "results.csv", index=False)
    table = ranking_table(df)
    table.to_csv(args.out / "ranking.csv", index=False)
    boxplot_by_method(df, args.out / "boarding_times.png")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
```

```python
# src/jupedsim_scenarios/boarding/__init__.py  (replace)
from .config import BoardingConfig, Seat
from .experiment import BoardingResult, run_boarding, sweep

__all__ = ["BoardingConfig", "Seat", "BoardingResult", "run_boarding", "sweep"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/boarding/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Full suite + lint**

Run:
```bash
python -m pytest tests/boarding -v
ruff check src/jupedsim_scenarios/boarding tests/boarding
```
Expected: all pass, no lint errors.

- [ ] **Step 6: Commit**

```bash
git add src/jupedsim_scenarios/boarding/cli.py src/jupedsim_scenarios/boarding/__init__.py tests/boarding/test_cli.py
git commit -m "feat(boarding): CLI runner + public exports"
```

---

### Task 9: Full-cabin validation run (the actual study)

**Files:**
- Create: `docs/specs/2026-06-10-airplane-boarding-results.md` (results write-up)

This task produces the scientific deliverable: run the full 30-row study and confirm the ranking.

- [ ] **Step 1: Run the study**

Run (this is a longer run; expect minutes):
```bash
python -m jupedsim_scenarios.boarding --seeds 20 --out boarding_out
```

- [ ] **Step 2: Check the ranking**

Open `boarding_out/ranking.csv`. Confirm the expected ordering holds:
`steffen_perfect` fastest; `back_to_front` and `front_to_back` slowest; `random` in between;
`wilma` between steffen and random.

- [ ] **Step 3: Write up results**

Create `docs/specs/2026-06-10-airplane-boarding-results.md` with: the ranking table, the
boxplot, the speedup of `steffen_perfect` vs `back_to_front`, and a note on how the JuPedSim
ranking compares to Steffen's published ranking. If the ranking deviates, record which
parameter (`spawn_headway`, `arrival_threshold`, `aisle_width`) was tuned and why.

- [ ] **Step 4: Commit**

```bash
git add boarding_out/ranking.csv boarding_out/boarding_times.png docs/specs/2026-06-10-airplane-boarding-results.md
git commit -m "docs(boarding): full-cabin study results + ranking"
```

---

## Self-Review

**Spec coverage:**
- Scientific framing (factor/response/controlled/paired seeds) → Tasks 5, 6, 9. ✓
- 6 canonical methods → Task 3. ✓
- 30×6 / 180 pax, configurable → Task 1 (`BoardingConfig`). ✓
- `CollisionFreeSpeedModel` → Task 5. ✓
- Parametric geometry + seat map + routability assertions → Task 2. ✓
- Direct-steering choreography, per-agent live-computed holds, luggage Gamma(7,3), seat penalty 5s/neighbor → Tasks 4, 5. ✓
- Sweep + ranking + boxplot + replayable SQLite → Tasks 6, 7 (SQLite written per run in Task 5). ✓
- Tests: order generators, penalty, routability, smoke run → Tasks 1–5, 8. ✓
- Open risks (door deadlock, hold-blocks-followers, steffen-modified variant) → Task 5 notes, Task 3 (documented variant). ✓

**Placeholder scan:** No TBD/TODO; every code step has full code. Task 9 is intentionally a
run+observe task (the study itself), not a code stub.

**Type consistency:** `Seat`, `BoardingConfig`, `SeatGeom`, `AgentPlan`, `State`,
`BoardingResult`, `METHODS`, `seat_interference_penalty`, `luggage_time`, `run_boarding`,
`sweep`, `ranking_table`, `boxplot_by_method`, `build_fuselage`, `all_seats` — names used
consistently across tasks. `AgentPlan.hold_frames`/`_release_iter` are set in Task 4 and
re-set live in Task 5 (documented, intentional).

> **API caveat for the implementer:** exact `jupedsim>=1.4` constructor signatures
> (`SqliteTrajectoryWriter` arg names, `CollisionFreeSpeedModelAgentParameters` fields,
> `Simulation(dt=...)` vs per-iterate dt) may differ slightly by version. If a call raises a
> TypeError on a keyword, check the installed API: `python -c "import jupedsim, inspect;
> print(inspect.signature(jupedsim.Simulation.__init__))"` and adjust. The plan's control flow
> is correct; only keyword spellings may need alignment.
