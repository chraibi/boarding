# Airplane Boarding Study — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design); pending implementation plan
**Target repo:** `jupedsim-scenarios`
**Reference:** Steffen, J.H. (2008), *Optimal boarding method for airline passengers*, J. Air Transport Management — [arXiv:0802.0733](https://arxiv.org/abs/0802.0733)

## Goal

Reproduce Steffen's comparison of airplane boarding methods in JuPedSim as a rigorous,
reproducible study living in `jupedsim-scenarios`. The deliverable is the **method ranking
and relative speedups** — Steffen-Perfect fastest, Back-to-Front and Front-to-Back
counter-intuitively near-worst, Random in the middle — not a match of absolute wall-clock
minutes.

### Why not absolute times

Steffen's original is a 1-D cellular-automaton toy model. JuPedSim provides continuous 2-D
movement with collision avoidance, which is more realistic but will not reproduce the exact
18–24 min figures. We therefore validate against the *ordering* of methods and their
*relative* differences.

## Scientific framing

- **Factor (independent variable):** boarding method → passenger release order.
- **Response (dependent variable):** total boarding time (last agent seated). Secondary:
  per-row seat-time curve.
- **Controlled:** geometry, luggage & seat-interference penalty parameters, microscopic
  model, `dt`, seeds, desired-speed distribution.
- **Replication:** N seeds per method (default **20**), **paired** across methods — the same
  seed produces the same luggage draws and speed draws for a given passenger, so differences
  are attributable to order, not noise.
- **Aircraft:** single-aisle, **30 rows × 6 seats = 180 passengers** (A320/737-class), per
  the paper. Fully configurable.
- **Model:** `CollisionFreeSpeedModel` (speed-based; appropriate for single-file aisle
  queuing).

### Methods compared (canonical Steffen set)

| Method           | Order rule                                                        |
|------------------|------------------------------------------------------------------|
| Random           | Uniform shuffle of all 180 passengers (per-seed).                |
| Back-to-Front    | 6 blocks of 5 rows, rear block first; random within block.       |
| Front-to-Back    | Same blocks, front block first (worst-case sanity check).        |
| WilMA            | Outside-in: all window seats, then all middle, then all aisle.   |
| Steffen-Perfect  | Alternating rows, one side, window→middle→aisle; maximal spacing.|
| Steffen-Modified | Practical variant: board in 4 groups by side + odd/even rows.    |

**Expected ranking:** Steffen-Perfect < WilMA < Random < {Back-to-Front, Front-to-Back}.

## Architecture (Approach A — standalone in jupedsim-scenarios)

A new subpackage `boarding/` under `src/jupedsim_scenarios/`. The web *editor* is intentionally
not in the critical path: it cannot express per-agent timed holds or auto-draw 180 seats. The
study emits standard SQLite trajectories that replay in the Web-Based-JuPedSim app / jpsvis for
the visual payoff.

### Module layout

| Module            | Responsibility                                                            |
|-------------------|---------------------------------------------------------------------------|
| `geometry.py`     | Aisle-only walkable polygon + row aisle-points + seat coordinates (viz).  |
| `methods.py`      | Boarding-order generators (one function per method, seeded).              |
| `choreography.py` | Per-agent boarding state machine + luggage/seat-interference penalties.   |
| `experiment.py`   | `run_boarding(method, seed)` + `sweep(methods, seeds)` → DataFrame.       |
| `analysis.py`     | Metrics, ranking table, box/violin plot, seat-time curves.                |
| `seat_placement.py` | Post-hoc seat-fill artifact (agent dropped at its seat at its seat-time). |
| `cli.py`          | Run a sweep / single method from the command line.                       |

### Seating model — logical seating (resolved after a validation spike)

Agents do **not** physically navigate into seats. Integration of an earlier "comb geometry +
direct-steering seat navigation" design failed: direct steering moves in straight lines and
ignores walls, so the aisle crush shoved holders/releasers off their row-x and drove them into
non-walkable gaps (wedging), plus same-row opposite-side agents collided at the aisle centreline.
These are 2-D continuous-navigation artifacts, not boarding physics.

**Resolution:** logical seating. The geometry is a **walled aisle only**; an agent walks to its
row point, HOLDs there (luggage + interference), then is **removed** (`mark_agent_for_removal`)
— "sitting" is logical. Seats remain labels for the interference penalty (the `occupied` set).
This is also closer to Steffen's own model (aisle + serial holds + penalty, no seat choreography).
A 3-row validation spike confirmed the ranking emerges (steffen_perfect 55.6 s < wilma 57.8 <
back_to_front 68.0 < front_to_back 91.1 s, all 18/18 seated, seed 1).

**Visual tradeoff (accepted):** logical seating means a raw trajectory replay shows the aisle
queue/holds but agents vanish at their row rather than filling seats. To keep the demo payoff,
`seat_placement.py` produces a **post-hoc** seat-fill artifact: each agent is dropped at its real
seat coordinate at its recorded seat-time, so an animation still shows seats filling.

## Section detail

### Geometry generator (`geometry.py`)

`build_fuselage(cfg)` → `(walkable_polygon, seat_map, door_point)`.

- The walkable area is a **single rectangular aisle** running from the door (x≈0) to just past
  the last row. Width = `aisle_width` (0.5 m), which already forbids passing (two agent diameters
  = 0.72 m > 0.5 m), so single-file aisle flow — the bottleneck — holds without any seat walls.
- `seat_map[Seat]` → `SeatGeom(aisle_waypoint, seat_coord)`: `aisle_waypoint = (row_x, 0)` is the
  on-aisle point the agent walks to and holds at; `seat_coord = (row_x, ±(half_aisle+(col+½)·seat_width))`
  is the seat's physical coordinate, used only for the post-hoc seat-fill visual (never navigated).
- `RoutingEngine.is_routable()` is asserted for the door and every row aisle-point (all on the
  aisle, so trivially routable — the check guards against a degenerate aisle).

### Boarding choreography (`choreography.py`) — core

Each agent runs a small state machine, advanced every frame by the run loop via a **direct
steering** stage (`add_direct_steering_stage`; one stage per journey; per-frame `agent.target`):

1. **WALK_TO_ROW** — `agent.target =` the row aisle-point `(row_x, 0)`.
2. **HOLD** — on arrival (within threshold), set a release iteration `hold_frames` ahead,
   `hold_frames = round((luggage_time + seat_interference_penalty) / dt)`, **computed at that
   moment** from current seat occupancy. During HOLD the agent **keeps targeting the row aisle-point**
   (so a shove from the queue behind self-corrects) — its body blocks the aisle, followers queue
   via collision avoidance, and agents at different rows hold concurrently (the parallelization
   effect that gives WilMA/Steffen their advantage).
   - `luggage_time` ~ **Gamma(mean 7 s, sd 3 s)**, drawn per agent from the seeded RNG.
   - `seat_interference_penalty` = **5 s × (number of already-seated neighbors inboard of this
     seat)**: window displaces middle+aisle (≤2), middle displaces aisle (≤1), aisle = 0.
     Order-dependent; computed live from occupancy at HOLD entry.
3. **SEATED** — when the hold expires, the agent is recorded as seated (occupancy += seat,
   seat-time = iteration × dt) and the run loop **removes it** (`mark_agent_for_removal`). The
   aisle clears for following agents.

Release schedule: agents enter at the door in method order on a spawn headway, gated so a new
agent spawns only when the door point is clear (no existing agent within `2·agent_radius`).

### Experiment harness (`experiment.py`)

- `run_boarding(method, seed) -> BoardingResult(total_time, seat_times, method, seed, sqlite_path)`
  — builds the sim, generates the order, runs the loop until every passenger is seated (all
  removed), closes the SQLite writer. `seat_times` maps each `Seat` → the time it was seated.
- `sweep(methods, seeds) -> pandas.DataFrame` — paired seeds across methods.

### Seat-fill artifact (`seat_placement.py`)

- `seat_fill_table(result, seat_map) -> pandas.DataFrame` with columns
  `[row, side, col, x, y, seat_time]` — each seat's physical coordinate and the time it filled.
  An animation/overlay drives "seats filling" from this; the rigorous numbers never depend on it.

### Analysis (`analysis.py`)

- Mean ± confidence interval boarding time per method; ranking table.
- Box/violin plot of boarding time by method; per-method seat-time curves.
- Reuses the repo's existing analysis / PedPy conventions.
- Outputs: results CSV, summary plot, and one SQLite trajectory per method (representative
  seed) for replay in the app / jpsvis.

## Testing

- **Order generators:** deterministic and correct per method for a small cabin (e.g. assert
  Steffen-Perfect alternates rows and sides; Back-to-Front rear block first).
- **Penalty function:** occupancy → seconds (window with both neighbors seated = +10 s, etc.).
- **Geometry routability:** the door and every row aisle-point are routable for default config.
- **Smoke run:** a tiny 3-row cabin runs to all-seated (all removed); assert Steffen-Perfect
  total ≤ Front-to-Back total on one fixed seed (sanity, not a strict statistical claim).
- **Seat-fill table:** one row per passenger, coordinates match `seat_map`, `seat_time` matches
  the run's `seat_times`.

## Engineering assessment

- **Appropriately engineered.** Each module has one purpose and a clear interface; the
  choreography (the only novel/risky part) is isolated in one file. No web-editor coupling, no
  speculative config surface beyond the documented fuselage/penalty parameters that the study
  actually varies.
- **Not overengineered:** no interactive demo, no app integration in this phase (deferred to a
  possible Phase 2 hybrid generator).
- **Not underengineered:** paired seeds + routability checks + a smoke run guard the
  scientific validity gates the `jupedsim` skill requires.

## Open questions / risks

1. **Door deadlock / spawn headway** — RESOLVED: spawn is gated on door clearance (no agent
   within `2·agent_radius` of the door) plus the headway timer; validated in the spike.
2. **HOLD blocks followers / wedging** — RESOLVED by the logical-seating pivot above. The held
   agent targets its row aisle-point and self-corrects under shoving; no seat navigation, so no
   wedging or same-row centreline collisions. Validated on the 3-row spike (all 18 seated).
3. **Steffen-Modified exact grouping** — pick one published practical variant and document it.
4. **Absolute-time fidelity** — JuPedSim is continuous 2-D; absolute minutes will not match
   Steffen's 1-D CA. The deliverable is the *ranking and relative speedups*, which the spike
   reproduced.
