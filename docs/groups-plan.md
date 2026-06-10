# Travel Groups & Cohesion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in travel groups that board cohesively (window-first), and sweep the group fraction to measure how each boarding method's advantage erodes — without changing the published homogeneous baseline.

**Architecture:** A new `groups.py` assigns groups of 2–3 to adjacent same-bench seats (`assign_groups`, seeded + method-independent) and reorders a method's boarding sequence so each group's members board consecutively window-first (`cohesive_order`). `BoardingConfig` gains `group_fraction`; when > 0, `run_boarding` applies the cohesion reorder. `groupsweep.py` sweeps the fraction and plots the erosion curve.

**Tech Stack:** Python ≥3.11, `jupedsim`, pandas, matplotlib, pytest. Verify with the scenarios venv: `/Users/chraibi/workspace/PedestrianDynamics/jupedsim-scenarios/.venv/bin/python` and `…/.venv/bin/ruff`. Run from repo root `/Users/chraibi/workspace/playground/boarding`. Tests via `pytest` (pyproject sets `pythonpath=["src"]`); module runs need `PYTHONPATH=src`.

**Spec:** `docs/groups-design.md`

---

## File Structure

| File | Change |
|------|--------|
| `src/boarding/groups.py` | NEW — `assign_groups`, `cohesive_order`. |
| `src/boarding/config.py` | Add `group_fraction: float = 0.0`. |
| `src/boarding/experiment.py` | Apply `cohesive_order` to `order` when `group_fraction > 0`. |
| `src/boarding/groupsweep.py` | NEW — `sweep_group_fraction`, `erosion_plot`, CLI `main`. |
| `tests/test_groups.py` | NEW. |
| `tests/test_experiment_smoke.py` | Add baseline-at-0 + erosion tests. |
| `tests/test_groupsweep.py` | NEW. |
| `docs/results-groups.md` | NEW — write-up (Task 5). |

**Existing facts the implementer needs:**
- `boarding/config.py`: `BoardingConfig` `@dataclass(frozen=True)` (fields incl. `rows`, `total_passengers`, `seats_per_side` default 3); `Seat(row, side, col)` frozen — `col` 0=aisle, 1=middle, 2=window.
- `boarding/methods.py`: `all_seats(cfg) -> list[Seat]` canonical order; `METHODS: dict[str, callable]`.
- `boarding/experiment.py`: in `run_boarding`, the boarding sequence is built by
  `order = METHODS[method](cfg, random.Random(seed))`; `Seat` is already imported there.
- `tests/test_experiment_smoke.py` already imports `replace`, `BoardingConfig`, `run_boarding`, `pytest`, and defines `_tiny()` → `BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=900.0)`.

---

### Task 1: `groups.py` — assign_groups + cohesive_order

**Files:** Create `src/boarding/groups.py`; Create `tests/test_groups.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_groups.py
from collections import Counter

from boarding.config import BoardingConfig, Seat
from boarding.groups import assign_groups, cohesive_order
from boarding.methods import all_seats


def test_zero_fraction_makes_every_seat_a_singleton():
    cfg = BoardingConfig(rows=4)
    g = assign_groups(cfg, seed=0, group_fraction=0.0)
    assert len(set(g.values())) == cfg.total_passengers  # all unique ids


def test_assign_groups_is_deterministic_and_method_independent():
    cfg = BoardingConfig(rows=6)
    a = assign_groups(cfg, seed=3, group_fraction=0.5)
    b = assign_groups(cfg, seed=3, group_fraction=0.5)
    assert a == b
    assert a != assign_groups(cfg, seed=4, group_fraction=0.5)


def test_grouped_fraction_is_approximately_the_target():
    cfg = BoardingConfig(rows=60)  # 360 seats
    g = assign_groups(cfg, seed=1, group_fraction=0.5)
    sizes = Counter(g.values())
    grouped = sum(c for c in sizes.values() if c >= 2)
    assert 0.40 < grouped / cfg.total_passengers < 0.60


def test_group_members_are_adjacent_in_one_bench():
    cfg = BoardingConfig(rows=20)
    g = assign_groups(cfg, seed=2, group_fraction=0.7)
    members: dict[int, list[Seat]] = {}
    for seat, gid in g.items():
        members.setdefault(gid, []).append(seat)
    for seats in members.values():
        if len(seats) < 2:
            continue
        rows = {s.row for s in seats}
        sides = {s.side for s in seats}
        assert rows == {next(iter(rows))} and sides == {next(iter(sides))}  # one bench
        cols = sorted(s.col for s in seats)
        # contiguous cols ending at the window (highest col == seats_per_side-1)
        assert cols == list(range(max(cols) - len(cols) + 1, max(cols) + 1))
        assert max(cols) == cfg.seats_per_side - 1


def test_cohesive_order_groups_members_window_first_and_is_a_permutation():
    cfg = BoardingConfig(rows=3)
    order = all_seats(cfg)
    # a single group of 3 in row 1 left bench (cols 0,1,2), everything else solo
    groups: dict[Seat, int] = {}
    gid = 0
    grp = {Seat(1, "L", 0), Seat(1, "L", 1), Seat(1, "L", 2)}
    for s in order:
        if s in grp:
            groups[s] = 999
        else:
            groups[s] = gid
            gid += 1
    out = cohesive_order(order, groups)
    assert set(out) == set(order) and len(out) == len(order)  # permutation
    idx = [i for i, s in enumerate(out) if s in grp]
    assert idx == list(range(idx[0], idx[0] + 3))  # consecutive
    block = out[idx[0]: idx[0] + 3]
    assert [s.col for s in block] == [2, 1, 0]  # window-first


def test_cohesive_order_unchanged_when_all_singletons():
    cfg = BoardingConfig(rows=3)
    order = all_seats(cfg)
    groups = {s: i for i, s in enumerate(order)}
    assert cohesive_order(order, groups) == order
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_groups.py -v`; expect ModuleNotFoundError.

- [ ] **Step 3: Implementation** (`src/boarding/groups.py`):

```python
import random

from .config import BoardingConfig, Seat
from .methods import all_seats

_GROUP_SIZES = (2, 3)
_GROUP_SIZE_WEIGHTS = (0.5, 0.5)


def assign_groups(
    cfg: BoardingConfig, seed: int, group_fraction: float
) -> dict[Seat, int]:
    """Assign a group id to every seat. Members of a real group (size >= 2) share an id
    and sit in adjacent window-out seats of one bench (row+side). Solo passengers get a
    unique id. Seeded and method-independent (paired across methods)."""
    rng = random.Random(seed)
    benches: dict[tuple[int, str], list[Seat]] = {}
    for seat in all_seats(cfg):
        benches.setdefault((seat.row, seat.side), []).append(seat)
    for bench in benches.values():
        bench.sort(key=lambda s: -s.col)  # window (highest col) first

    bench_keys = list(benches.keys())
    rng.shuffle(bench_keys)
    target = round(group_fraction * cfg.total_passengers)

    group_id: dict[Seat, int] = {}
    next_id = 0
    grouped = 0
    for key in bench_keys:
        bench = benches[key]
        if grouped < target:
            size = min(rng.choices(_GROUP_SIZES, weights=_GROUP_SIZE_WEIGHTS, k=1)[0], len(bench))
            for seat in bench[:size]:
                group_id[seat] = next_id
            next_id += 1
            grouped += size
            for seat in bench[size:]:  # leftover seats are singletons
                group_id[seat] = next_id
                next_id += 1
        else:
            for seat in bench:
                group_id[seat] = next_id
                next_id += 1
    return group_id


def cohesive_order(method_order: list[Seat], groups: dict[Seat, int]) -> list[Seat]:
    """Reorder so each group's members board consecutively, window-first, anchored at the
    group's earliest position in method_order. Solo seats stay in place. Returns a
    permutation of method_order; an all-singleton mapping returns it unchanged."""
    members: dict[int, list[Seat]] = {}
    for seat in method_order:
        members.setdefault(groups[seat], []).append(seat)
    for seats in members.values():
        seats.sort(key=lambda s: -s.col)  # window-first within the group

    out: list[Seat] = []
    emitted: set[int] = set()
    for seat in method_order:
        gid = groups[seat]
        if gid in emitted:
            continue
        out.extend(members[gid])
        emitted.add(gid)
    return out
```

- [ ] **Step 4: Run** the test; expect 6 passing.
- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/groups.py tests/test_groups.py
git commit -m "feat: travel-group assignment + window-first cohesive ordering"
```

---

### Task 2: `config.py` — `group_fraction`

**Files:** Modify `src/boarding/config.py`; Test `tests/test_config.py` (append).

- [ ] **Step 1: Failing test** (append to `tests/test_config.py`):

```python
def test_group_fraction_defaults_to_zero():
    from boarding.config import BoardingConfig
    assert BoardingConfig().group_fraction == 0.0


def test_group_fraction_can_be_set():
    from boarding.config import BoardingConfig
    assert BoardingConfig(group_fraction=0.5).group_fraction == 0.5
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_config.py -v`; expect FAIL (`unexpected keyword argument 'group_fraction'`).

- [ ] **Step 3: Implementation** — add this field to `BoardingConfig`, immediately after the
existing `profile_mix` field (keep everything else untouched):

```python
    # travel groups: 0.0 = no groups (baseline); fraction of passengers boarding cohesively
    group_fraction: float = 0.0
```

- [ ] **Step 4: Run** the test; expect PASS. Then full suite: `…/.venv/bin/python -m pytest tests -q` (report count).
- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/config.py tests/test_config.py
git commit -m "feat: optional group_fraction on BoardingConfig (default 0.0)"
```

---

### Task 3: `experiment.py` — apply cohesion when `group_fraction > 0`

**Files:** Modify `src/boarding/experiment.py`; Test `tests/test_experiment_smoke.py` (append).

The baseline (`group_fraction == 0`) must be byte-identical: no reorder happens.

- [ ] **Step 1: Failing test** (append to `tests/test_experiment_smoke.py`):

```python
def test_groups_do_not_change_the_baseline_at_zero_fraction():
    cfg = _tiny()
    assert cfg.group_fraction == 0.0
    # pinned baseline values (must match the homogeneous study)
    assert run_boarding("random", seed=0, config=cfg).total_time == pytest.approx(82.5)
    assert run_boarding("front_to_back", seed=0, config=cfg).total_time == pytest.approx(99.3)


def test_groups_complete_and_slow_steffen_perfect():
    base = BoardingConfig(rows=4, spawn_headway=1.0)
    grouped = replace(base, group_fraction=0.8)
    r = run_boarding("steffen_perfect", seed=0, config=grouped)
    assert r.seated_count == grouped.total_passengers
    # clumping families destroys steffen's spacing -> not faster than the ungrouped run
    assert r.total_time >= run_boarding("steffen_perfect", seed=0, config=base).total_time
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_experiment_smoke.py -k groups -v`; expect FAIL (cohesion not wired → the slow assertion may equal, or import).

- [ ] **Step 3: Implementation** — in `src/boarding/experiment.py`:
1. Add import with the other `from .` imports:
```python
from .groups import assign_groups, cohesive_order
```
2. Right after the line `order = METHODS[method](cfg, random.Random(seed))`, add:
```python
    if cfg.group_fraction > 0:
        order = cohesive_order(order, assign_groups(cfg, seed, cfg.group_fraction))
```
Leave everything else unchanged.

- [ ] **Step 4: Run** `…/.venv/bin/python -m pytest tests/test_experiment_smoke.py -v`; expect all pass.
- [ ] **Step 5: Full regression + lint**

```bash
…/.venv/bin/python -m pytest tests -q
…/.venv/bin/ruff check src/boarding tests
```
Expect all pass (the at-zero pin confirms the baseline is intact), lint clean.

- [ ] **Step 6: Commit**

```bash
git add src/boarding/experiment.py tests/test_experiment_smoke.py
git commit -m "feat: cohesive group ordering applied when group_fraction > 0"
```

---

### Task 4: `groupsweep.py` — sweep + erosion plot + CLI

**Files:** Create `src/boarding/groupsweep.py`; Create `tests/test_groupsweep.py`.

- [ ] **Step 1: Failing test** (`tests/test_groupsweep.py`):

```python
import pandas as pd

from boarding.config import BoardingConfig
from boarding.groupsweep import erosion_plot, sweep_group_fraction


def test_sweep_group_fraction_shape():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    df = sweep_group_fraction(
        ["random", "steffen_perfect"], fractions=[0.0, 0.5], seeds=[0], config=cfg
    )
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"method", "group_fraction", "seed", "total_time"}
    assert len(df) == 2 * 2 * 1  # methods x fractions x seeds


def test_erosion_plot_writes_png(tmp_path):
    df = pd.DataFrame(
        [
            {"method": "a", "group_fraction": 0.0, "seed": 0, "total_time": 10.0},
            {"method": "a", "group_fraction": 0.5, "seed": 0, "total_time": 14.0},
            {"method": "b", "group_fraction": 0.0, "seed": 0, "total_time": 12.0},
            {"method": "b", "group_fraction": 0.5, "seed": 0, "total_time": 13.0},
        ]
    )
    out = erosion_plot(df, tmp_path / "e.png")
    assert out.exists()
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_groupsweep.py -v`; expect ModuleNotFoundError.

- [ ] **Step 3: Implementation** (`src/boarding/groupsweep.py`):

```python
import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .config import BoardingConfig
from .experiment import run_boarding
from .methods import METHODS


def sweep_group_fraction(
    methods: Sequence[str],
    fractions: Sequence[float],
    seeds: Sequence[int],
    config: BoardingConfig | None = None,
) -> pd.DataFrame:
    """Run every (method, fraction, seed); seeds paired across methods and fractions."""
    base = config or BoardingConfig()
    rows = []
    for fraction in fractions:
        cfg = replace(base, group_fraction=fraction)
        for seed in seeds:
            for method in methods:
                res = run_boarding(method, seed, cfg)
                rows.append(
                    {
                        "method": method,
                        "group_fraction": fraction,
                        "seed": seed,
                        "total_time": res.total_time,
                    }
                )
    return pd.DataFrame(rows)


def erosion_plot(df: pd.DataFrame, out_path: Path) -> Path:
    """Mean boarding time vs group fraction, one line per method."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    methods = [m for m in METHODS if m in set(df["method"])]
    fig, ax = plt.subplots(figsize=(9, 6))
    for method in methods:
        sub = df[df["method"] == method].groupby("group_fraction")["total_time"].mean()
        ax.plot(sub.index, sub.to_numpy(), marker="o", label=method)
    ax.set_xlabel("group fraction")
    ax.set_ylabel("mean boarding time (s)")
    ax.set_title("Boarding time vs group fraction (window-first cohesion)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Group-fraction sensitivity sweep.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--fractions", nargs="+", type=float, default=[0.0, 0.2, 0.4, 0.6, 0.8])
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("study-output"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df = sweep_group_fraction(
        args.methods, args.fractions, list(range(args.seeds)), config=cfg
    )
    df.to_csv(args.out / "group_sweep.csv", index=False)
    erosion_plot(df, args.out / "group_erosion.png")
    pivot = df.groupby(["group_fraction", "method"])["total_time"].mean().unstack()
    print(pivot.to_string())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run** `…/.venv/bin/python -m pytest tests/test_groupsweep.py -v`; expect 2 passing.
- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/groupsweep.py tests/test_groupsweep.py
git commit -m "feat: group-fraction sweep + erosion plot + CLI"
```

---

### Task 5: Run the sweep + write-up + README section

**Files:** Create `docs/results-groups.md`; artifacts `docs/study-output/group_sweep.csv`, `group_erosion.png`; Modify `README.md`.

- [ ] **Step 1: Run the sweep**

```bash
PYTHONPATH=src …/.venv/bin/python -m boarding.groupsweep --seeds 20 --rows 30 --out docs/study-output
```
~5–8 min (6 methods × 5 fractions × 20 seeds = 600 runs). Note the printed pivot (mean time per fraction × method).

- [ ] **Step 2: Write `docs/results-groups.md`** — include the pivot table (group_fraction × method
mean), the erosion plot, and the findings: (a) how each method's time rises with `group_fraction`;
(b) whether/where Steffen-Perfect's line converges toward or crosses the block/random methods (its
edge eroding); (c) which methods are most vs least group-sensitive. State that this is a **lower
bound** (window-first cohesion, groups capped at 3). Report numbers actually produced; do not assume
the direction.

- [ ] **Step 3: Add a README section** "## Travel groups (boarding-order cohesion)" AFTER the existing
"## Passenger heterogeneity" section and BEFORE "## Visualize". Do NOT modify the basic-study or
heterogeneity sections. Include: a one-paragraph explanation, the run command
`python -m boarding.groupsweep --seeds 20 --rows 30 --out study-output`, the headline finding, the
embedded plot `![group erosion](docs/study-output/group_erosion.png)`, and links to
`docs/results-groups.md` and `docs/groups-design.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/results-groups.md docs/study-output/group_sweep.csv README.md
git add -f docs/study-output/group_erosion.png
git commit -m "docs: travel-group erosion study results + README section"
```

---

## Self-Review

**Spec coverage:**
- `group_fraction` swept variable; groups 2–3 in one bench, sizes {2:.5,3:.5} → Task 1. ✓
- `assign_groups` seeded/method-independent/paired, fraction≈target, `0`→singletons → Task 1. ✓
- Window-first cohesion, anchor = earliest member, permutation, all-singleton→unchanged → Task 1. ✓
- `config.group_fraction` default 0 = baseline → Task 2. ✓
- `experiment.py` applies cohesion only when `>0`; baseline byte-identical → Task 3 (pinned test). ✓
- Sweep + erosion plot + CLI defaults `[0,.2,.4,.6,.8]`/20 seeds → Task 4. ✓
- Erosion-curve deliverable + write-up + README section (others unchanged) → Task 5. ✓
- Tests: assignment determinism/pairing/fraction/adjacency, cohesion permutation/window-first/identity,
  baseline-at-0 pin, completes+slows steffen, sweep shape, plot writes → Tasks 1, 3, 4. ✓

**Placeholder scan:** No TBD/TODO; every code step complete. Task 5 is a run+write task (report produced numbers), not a stub.

**Type consistency:** `assign_groups(cfg, seed, group_fraction) -> dict[Seat, int]` and
`cohesive_order(method_order, groups) -> list[Seat]` used consistently in Tasks 1, 3.
`sweep_group_fraction(methods, fractions, seeds, config)` and `erosion_plot(df, out_path)` match
their test call sites in Task 4. `cfg.group_fraction` referenced consistently. `Seat.col` semantics
(2=window) consistent with the window-first sort `key=lambda s: -s.col`.

> **Baseline-preservation note:** the at-zero pin (`test_groups_do_not_change_the_baseline_at_zero_fraction`)
> reuses the exact homogeneous values (82.5 / 99.3 for `_tiny()`). If they drift, the `group_fraction > 0`
> guard in Task 3 leaked into the default path — fix before proceeding.
