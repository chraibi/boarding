# Passenger Time-to-Sitting Profiles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in per-passenger heterogeneity (walk speed, luggage-stow time, shuffle speed) to the boarding study and run a 6-method comparison under a realistic passenger mix, without changing the published homogeneous baseline.

**Architecture:** A new `profiles.py` defines `Profile` bundles and `draw_passengers(cfg, seed, mix)` (seeded, paired across methods, like `draw_luggage`). `BoardingConfig` gains an optional `profile_mix`; when set, `run_boarding` gives each agent a profile-derived `desired_speed` and `hold = stow_time + mobility_factor × interference`. When `None`, the existing code path is byte-identical.

**Tech Stack:** Python ≥3.11, `jupedsim>=1.4`, `jupedsim-scenarios`, pandas, matplotlib, pytest. Verify with the scenarios venv: `/Users/chraibi/workspace/PedestrianDynamics/jupedsim-scenarios/.venv/bin/python` and `…/.venv/bin/ruff`. Run from repo root `/Users/chraibi/workspace/playground/boarding`. Tests via `pytest` (pyproject sets `pythonpath = ["src"]`); module runs need `PYTHONPATH=src`.

**Spec:** `docs/heterogeneous-profiles-design.md`

---

## File Structure

| File | Change |
|------|--------|
| `src/boarding/profiles.py` | NEW — `Profile`, `PassengerParams`, `DEFAULT_MIX`, `draw_passengers`. |
| `src/boarding/config.py` | Add `profile_mix: tuple[Profile, ...] | None = None`. |
| `src/boarding/experiment.py` | Branch `run_boarding` on `cfg.profile_mix` for per-agent speed + hold. |
| `src/boarding/cli.py` | Add `--mix` flag (separate `*_mix` output filenames). |
| `tests/test_profiles.py` | NEW. |
| `tests/test_experiment_smoke.py` | Add heterogeneity tests. |
| `docs/results-heterogeneous.md` | NEW — results write-up (Task 5). |

**Existing facts the implementer needs:**
- `boarding/config.py`: `BoardingConfig` is a `@dataclass(frozen=True)` with fields incl. `rows`, `v0`, `luggage_mean`, `luggage_sd`, `seat_penalty`, `dt`, and `total_passengers` property; `Seat(row, side, col)` frozen dataclass.
- `boarding/methods.py`: `all_seats(cfg) -> list[Seat]` in canonical order.
- `boarding/experiment.py`: `draw_luggage(cfg, seed) -> dict[Seat, float]`; `seat_interference_penalty(seat, occupied, cfg)`; `run_boarding(method, seed, config=None, on_frame=None)`.

---

### Task 1: `profiles.py` — Profile, mix, draw_passengers

**Files:**
- Create: `src/boarding/profiles.py`
- Test: `tests/test_profiles.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_profiles.py
from boarding.config import BoardingConfig
from boarding.profiles import DEFAULT_MIX, Profile, draw_passengers


def test_default_mix_weights_sum_to_one():
    assert abs(sum(p.weight for p in DEFAULT_MIX) - 1.0) < 1e-9
    assert {p.name for p in DEFAULT_MIX} == {
        "standard", "business_young", "heavy_luggage", "elderly", "family_with_kids"
    }


def test_draw_passengers_covers_every_seat():
    cfg = BoardingConfig(rows=4)
    pax = draw_passengers(cfg, seed=0, mix=DEFAULT_MIX)
    assert len(pax) == cfg.total_passengers
    sample = next(iter(pax.values()))
    assert sample.speed_factor > 0
    assert sample.stow_time > 0
    assert sample.mobility_factor > 0


def test_draw_passengers_is_deterministic_and_paired():
    # same seed -> identical assignment (independent of method); different seed -> different
    cfg = BoardingConfig(rows=6)
    a = draw_passengers(cfg, seed=5, mix=DEFAULT_MIX)
    b = draw_passengers(cfg, seed=5, mix=DEFAULT_MIX)
    assert a == b
    c = draw_passengers(cfg, seed=6, mix=DEFAULT_MIX)
    assert a != c


def test_profile_frequencies_roughly_match_weights():
    cfg = BoardingConfig(rows=60)  # 360 seats -> stable frequencies
    pax = draw_passengers(cfg, seed=1, mix=DEFAULT_MIX)
    n = len(pax)
    standard = sum(1 for p in pax.values() if p.profile_name == "standard") / n
    assert 0.35 < standard < 0.55  # weight 0.45


def test_single_profile_mix_assigns_that_profile_to_all():
    cfg = BoardingConfig(rows=4)
    only_fast = (Profile("fast", 1.0, 1.5, 2.0, 1.0, 0.8),)
    pax = draw_passengers(cfg, seed=0, mix=only_fast)
    assert all(p.profile_name == "fast" for p in pax.values())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `…/.venv/bin/python -m pytest tests/test_profiles.py -v`
Expected: FAIL — `ModuleNotFoundError: boarding.profiles`

- [ ] **Step 3: Write minimal implementation**

```python
# src/boarding/profiles.py
import random
from dataclasses import dataclass

from .config import BoardingConfig, Seat
from .methods import all_seats


@dataclass(frozen=True)
class Profile:
    name: str
    weight: float            # relative mix fraction
    walk_speed_factor: float  # x cfg.v0
    stow_mean: float         # s, luggage-stow gamma mean
    stow_sd: float           # s
    mobility_factor: float   # x seat-interference penalty


@dataclass(frozen=True)
class PassengerParams:
    profile_name: str
    speed_factor: float
    stow_time: float
    mobility_factor: float


# Illustrative realistic mix (see docs/heterogeneous-profiles-design.md); weights sum to 1.
DEFAULT_MIX: tuple[Profile, ...] = (
    Profile("standard", 0.45, 1.00, 7.0, 3.0, 1.0),
    Profile("business_young", 0.15, 1.15, 2.0, 1.0, 0.9),
    Profile("heavy_luggage", 0.15, 0.95, 14.0, 5.0, 1.2),
    Profile("elderly", 0.15, 0.60, 10.0, 4.0, 1.8),
    Profile("family_with_kids", 0.10, 0.70, 16.0, 6.0, 2.0),
)


def _stow_draw(profile: Profile, rng: random.Random) -> float:
    if profile.stow_sd <= 0:
        return profile.stow_mean
    k = (profile.stow_mean / profile.stow_sd) ** 2
    theta = (profile.stow_sd ** 2) / profile.stow_mean
    return rng.gammavariate(k, theta)


def draw_passengers(
    cfg: BoardingConfig, seed: int, mix: tuple[Profile, ...]
) -> dict[Seat, PassengerParams]:
    """Assign a profile + stow time to each seat's occupant.

    Iterates seats in canonical all_seats order from a dedicated RNG, so a seed gives the
    same occupant at each seat regardless of boarding method (paired replication).
    """
    rng = random.Random(seed)
    weights = [p.weight for p in mix]
    out: dict[Seat, PassengerParams] = {}
    for seat in all_seats(cfg):
        profile = rng.choices(mix, weights=weights, k=1)[0]
        out[seat] = PassengerParams(
            profile_name=profile.name,
            speed_factor=profile.walk_speed_factor,
            stow_time=_stow_draw(profile, rng),
            mobility_factor=profile.mobility_factor,
        )
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `…/.venv/bin/python -m pytest tests/test_profiles.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/profiles.py tests/test_profiles.py
git commit -m "feat: passenger profiles + draw_passengers (paired heterogeneity)"
```

---

### Task 2: `config.py` — optional `profile_mix`

**Files:**
- Modify: `src/boarding/config.py`
- Test: `tests/test_config.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_config.py
def test_profile_mix_defaults_to_none():
    from boarding.config import BoardingConfig
    assert BoardingConfig().profile_mix is None


def test_profile_mix_can_be_set():
    from boarding.config import BoardingConfig
    from boarding.profiles import DEFAULT_MIX
    cfg = BoardingConfig(profile_mix=DEFAULT_MIX)
    assert cfg.profile_mix is DEFAULT_MIX
```

- [ ] **Step 2: Run test to verify it fails**

Run: `…/.venv/bin/python -m pytest tests/test_config.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'profile_mix'`

- [ ] **Step 3: Write minimal implementation**

In `src/boarding/config.py`, add the import at the top under `from dataclasses import dataclass`:

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .profiles import Profile
```

Then add this field to `BoardingConfig` (place it last, after `max_sim_seconds`):

```python
    # heterogeneity: None = homogeneous (baseline); a tuple of Profile enables a mix
    profile_mix: "tuple[Profile, ...] | None" = None
```

> Note: the `TYPE_CHECKING` guard avoids a circular import (`profiles` imports `config`). The
> annotation is a string so it is not evaluated at runtime.

- [ ] **Step 4: Run test to verify it passes**

Run: `…/.venv/bin/python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/config.py tests/test_config.py
git commit -m "feat: optional profile_mix on BoardingConfig (default None)"
```

---

### Task 3: `experiment.py` — per-passenger speed + hold

**Files:**
- Modify: `src/boarding/experiment.py`
- Test: `tests/test_experiment_smoke.py` (append)

The homogeneous path (mix `None`) must stay byte-identical: it keeps calling `draw_luggage`,
reuses the single `params` object, and uses `mobility_factor = 1.0` — so no extra RNG is consumed
and `hold` is unchanged.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_experiment_smoke.py
from boarding.profiles import DEFAULT_MIX, Profile


def test_homogeneous_default_is_unchanged_by_the_feature():
    # default config has no mix and must remain deterministic/identical run-to-run
    cfg = _tiny()
    assert cfg.profile_mix is None
    a = run_boarding("random", seed=0, config=cfg).total_time
    b = run_boarding("random", seed=0, config=cfg).total_time
    assert a == b


def test_all_slow_mix_boards_slower_than_all_fast_mix():
    fast = (Profile("fast", 1.0, 1.4, 2.0, 1.0, 0.5),)
    slow = (Profile("slow", 1.0, 0.5, 18.0, 1.0, 2.5),)
    base = BoardingConfig(rows=4, spawn_headway=1.0)
    t_fast = run_boarding("random", 0, replace(base, profile_mix=fast)).total_time
    t_slow = run_boarding("random", 0, replace(base, profile_mix=slow)).total_time
    assert t_slow > t_fast


def test_realistic_mix_run_completes():
    cfg = BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=1200.0,
                         profile_mix=DEFAULT_MIX)
    result = run_boarding("steffen_perfect", seed=1, config=cfg)
    assert result.seated_count == cfg.total_passengers
```

(`replace` and `BoardingConfig` are already imported at the top of this test file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `…/.venv/bin/python -m pytest tests/test_experiment_smoke.py -k "mix or homogeneous" -v`
Expected: FAIL — slow-vs-fast differ is not yet implemented (both use uniform speed/stow), or import error.

- [ ] **Step 3: Write minimal implementation**

In `src/boarding/experiment.py`, add the import near the other local imports:

```python
from .profiles import PassengerParams, draw_passengers
```

Replace the luggage line (currently around line 74):

```python
    luggage = draw_luggage(cfg, seed)  # paired across methods, independent of order
```

with:

```python
    mix = cfg.profile_mix
    luggage = draw_luggage(cfg, seed) if mix is None else None
    pax: dict[Seat, PassengerParams] | None = (
        None if mix is None else draw_passengers(cfg, seed, mix)
    )
```

Replace the spawn block (currently lines ~97-107) with one that builds per-passenger params when
heterogeneous:

```python
        if queue and iteration >= next_spawn and _door_is_clear(sim, plans, door, clearance):
            seat = queue[0]
            if pax is None:
                agent_params = params
            else:
                agent_params = jps.CollisionFreeSpeedModelAgentParameters(
                    position=door, desired_speed=cfg.v0 * pax[seat].speed_factor,
                    radius=cfg.agent_radius, journey_id=journey, stage_id=direct,
                )
            try:
                agent_id = sim.add_agent(agent_params)
            except Exception:
                agent_id = None
            if agent_id is not None:
                geom = seat_map[seat]
                plans[agent_id] = AgentPlan(seat, geom.aisle_waypoint)
                queue.pop(0)
                next_spawn = iteration + headway_frames
```

Replace the hold computation (currently lines ~114-116) with:

```python
                if pax is None:
                    stow, mob = luggage[plan.seat], 1.0
                else:
                    stow = pax[plan.seat].stow_time
                    mob = pax[plan.seat].mobility_factor
                hold_s = stow + mob * seat_interference_penalty(
                    plan.seat, occupied, cfg
                )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `…/.venv/bin/python -m pytest tests/test_experiment_smoke.py -v`
Expected: PASS (all — existing + 3 new)

- [ ] **Step 5: Full regression + lint**

Run:
```bash
…/.venv/bin/python -m pytest tests -q
…/.venv/bin/ruff check src/boarding tests
```
Expected: all pass (the homogeneous tests confirm the baseline is unchanged), lint clean.

- [ ] **Step 6: Commit**

```bash
git add src/boarding/experiment.py tests/test_experiment_smoke.py
git commit -m "feat: per-passenger speed + mobility-scaled hold when a profile mix is set"
```

---

### Task 4: `cli.py` — `--mix` flag

**Files:**
- Modify: `src/boarding/cli.py`
- Test: `tests/test_boarding_cli.py` (append)

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_boarding_cli.py
def test_cli_mix_flag_defaults_off():
    assert build_parser().parse_args([]).mix is False
    assert build_parser().parse_args(["--mix"]).mix is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `…/.venv/bin/python -m pytest tests/test_boarding_cli.py -v`
Expected: FAIL — `AttributeError: 'Namespace' object has no attribute 'mix'`

- [ ] **Step 3: Write minimal implementation**

In `src/boarding/cli.py`, add the import:

```python
from .profiles import DEFAULT_MIX
```

Add the argument in `build_parser` (after `--trajectories`):

```python
    p.add_argument(
        "--mix",
        action="store_true",
        help="run under the default realistic passenger mix (writes *_mix files)",
    )
```

In `main`, replace the `cfg = BoardingConfig(rows=args.rows)` line and the three output writes so the
mix run does not overwrite the homogeneous artifacts:

```python
    cfg = BoardingConfig(
        rows=args.rows, profile_mix=DEFAULT_MIX if args.mix else None
    )
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "_mix" if args.mix else ""
    df = sweep(args.methods, seeds=list(range(args.seeds)), config=cfg)
    df.to_csv(args.out / f"results{suffix}.csv", index=False)
    table = ranking_table(df)
    table.to_csv(args.out / f"ranking{suffix}.csv", index=False)
    boxplot_by_method(df, args.out / f"boarding_times{suffix}.png")
    print(table.to_string(index=False))
```

(Leave the existing `--trajectories` handling block after this unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `…/.venv/bin/python -m pytest tests/test_boarding_cli.py -v`
Expected: PASS

- [ ] **Step 5: CLI smoke (tiny)**

Run:
```bash
PYTHONPATH=src …/.venv/bin/python -m boarding --mix --methods random steffen_perfect --seeds 1 --rows 3 --out /tmp/boarding_mix_smoke
ls /tmp/boarding_mix_smoke
```
Expected: prints a ranking table; directory contains `results_mix.csv`, `ranking_mix.csv`, `boarding_times_mix.png`.

- [ ] **Step 6: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/cli.py tests/test_boarding_cli.py
git commit -m "feat: --mix CLI flag for the heterogeneous comparison"
```

---

### Task 5: Run the heterogeneous study + write-up

**Files:**
- Create: `docs/results-heterogeneous.md`
- Create (artifacts): `docs/study-output/ranking_mix.csv`, `results_mix.csv`, `boarding_times_mix.png`

- [ ] **Step 1: Run both baselines for comparison**

Run (writes the mix artifacts into the committed study-output dir):
```bash
PYTHONPATH=src …/.venv/bin/python -m boarding --mix --seeds 20 --rows 30 --out docs/study-output
```
This takes ~1-2 min. Note the printed ranking. Do NOT re-run the homogeneous sweep into that dir —
the homogeneous `ranking.csv` is already committed; just read it for the comparison.

- [ ] **Step 2: Write the comparison doc**

Create `docs/results-heterogeneous.md` with: the heterogeneous ranking table (from
`ranking_mix.csv`); for each method, the % inflation vs the committed homogeneous `ranking.csv`
mean; and the two headline findings — (a) does the method ordering still hold under the mix, and
(b) which methods inflate most/least (does heterogeneity compress or preserve Steffen's edge?).
Reference `docs/study-output/boarding_times_mix.png`. Keep it factual — report the numbers actually
produced, do not assume a direction.

- [ ] **Step 3: Commit**

```bash
git add docs/results-heterogeneous.md docs/study-output/ranking_mix.csv docs/study-output/results_mix.csv
git add -f docs/study-output/boarding_times_mix.png
git commit -m "docs: heterogeneous passenger-mix study results"
```

---

## Self-Review

**Spec coverage:**
- `Profile` bundle + `DEFAULT_MIX` + `draw_passengers` (paired) → Task 1. ✓
- `BoardingConfig.profile_mix`, default None = baseline → Task 2. ✓
- Per-agent `desired_speed` + `mobility × interference` hold; homogeneous path unchanged → Task 3. ✓
- `--mix` flag, separate `*_mix` outputs → Task 4. ✓
- Fixed-mix 6-method comparison + write-up → Task 5. ✓
- Tests: deterministic+paired assignment, weight frequencies, homogeneous regression, slow>fast,
  realistic-mix completes → Tasks 1, 3. ✓

**Placeholder scan:** No TBD/TODO; every code step is complete. Task 5 Step 2 is a write-up task
(report the numbers produced), not a stub.

**Type consistency:** `Profile(name, weight, walk_speed_factor, stow_mean, stow_sd, mobility_factor)`
and `PassengerParams(profile_name, speed_factor, stow_time, mobility_factor)` are used consistently
in Tasks 1, 3, 4. `draw_passengers(cfg, seed, mix)` signature matches all call sites.
`cfg.profile_mix` referenced consistently. `replace` (from `dataclasses`) is already imported in
`tests/test_experiment_smoke.py`.

> **Baseline-preservation note for the implementer:** the single most important invariant is that
> `BoardingConfig()` (mix `None`) produces the exact same numbers as before. Task 3's homogeneous
> branch must not call `draw_passengers` and must keep `draw_luggage` + the reused `params` object,
> so the RNG stream and hold values are untouched. The `test_homogeneous_default_is_unchanged…`
> test guards run-to-run determinism; if you have any doubt, also spot-check one method/seed
> `total_time` against a value from the committed `docs/study-output/results.csv`.
