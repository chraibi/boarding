# Passenger Compliance Rate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in `compliance_rate` that perturbs any method's boarding order (displace `(1−Rc)·N` passengers, reinsert randomly), and sweep it 1.0 → 0.0 to reproduce the convergence trend of Dong et al. (2025) Fig 16 — without changing the published baseline.

**Architecture:** A new `compliance.py` reorders a method's sequence by removing a seeded, method-independent set of non-compliant passengers and reinserting them at random positions. `BoardingConfig` gains `compliance_rate` (1.0 = full compliance = baseline); `run_boarding` applies it when < 1.0. `compliancesweep.py` sweeps the rate and plots the per-method curve.

**Tech Stack:** Python ≥3.11, `jupedsim`, pandas, matplotlib, pytest. Verify with the scenarios venv: `/Users/chraibi/workspace/PedestrianDynamics/jupedsim-scenarios/.venv/bin/python` and `…/.venv/bin/ruff`. Run from repo root `/Users/chraibi/workspace/playground/boarding`. Tests via `pytest` (pyproject sets `pythonpath=["src"]`); module runs need `PYTHONPATH=src`.

**Spec:** `docs/compliance-design.md`

---

## File Structure

| File | Change |
|------|--------|
| `src/boarding/compliance.py` | NEW — `apply_compliance`. |
| `src/boarding/config.py` | Add `compliance_rate: float = 1.0`. |
| `src/boarding/experiment.py` | Apply `apply_compliance` to `order` when `compliance_rate < 1.0`. |
| `src/boarding/compliancesweep.py` | NEW — `sweep_compliance`, `compliance_plot`, CLI `main`. |
| `tests/test_compliance.py` | NEW. |
| `tests/test_experiment_smoke.py` | Add baseline-at-1.0 + slows-steffen tests. |
| `tests/test_compliancesweep.py` | NEW. |
| `docs/results-compliance.md` | NEW — write-up (Task 5). |

**Existing facts the implementer needs:**
- `boarding/config.py`: `BoardingConfig` `@dataclass(frozen=True)`; its current last two fields are `profile_mix` then `group_fraction`. `Seat(row, side, col)` frozen — `col` 0=aisle, 1=middle, 2=window.
- `boarding/methods.py`: `all_seats(cfg) -> list[Seat]`; `METHODS: dict[str, callable]` (a method maps `(cfg, random.Random)` → `list[Seat]`).
- `boarding/experiment.py`: in `run_boarding`, the order is built by `order = METHODS[method](cfg, random.Random(seed))`, followed by an existing `if cfg.group_fraction > 0:` block that reassigns `order`. `Seat` is already imported there.
- `boarding/analysis.py`: `CANONICAL_ORDER` (tuple of method names) and `COMPARISON_YLIM` (tuple) for shared plot order + y-limits.
- `tests/test_experiment_smoke.py` already imports `from dataclasses import replace`, `BoardingConfig`, `run_boarding`, `pytest`, and defines `_tiny()` → `BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=900.0)`. Pinned tiny baselines: `random`/seed 0 = 82.5 s, `front_to_back`/seed 0 = 99.3 s.

---

### Task 1: `compliance.py` — apply_compliance

**Files:** Create `src/boarding/compliance.py`; Create `tests/test_compliance.py`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_compliance.py
import random

from boarding.compliance import apply_compliance
from boarding.config import BoardingConfig
from boarding.methods import METHODS, all_seats


def _order(method, cfg, seed=0):
    return METHODS[method](cfg, random.Random(seed))


def test_full_compliance_returns_order_unchanged():
    cfg = BoardingConfig(rows=5)
    order = _order("steffen_perfect", cfg)
    assert apply_compliance(order, 1.0, seed=0) == order


def test_output_is_always_a_permutation():
    cfg = BoardingConfig(rows=5)
    order = _order("random", cfg)
    for rate in (0.75, 0.5, 0.25, 0.0):
        out = apply_compliance(order, rate, seed=3)
        assert len(out) == len(order)
        assert set(out) == set(order)


def test_is_deterministic_for_a_seed():
    cfg = BoardingConfig(rows=6)
    order = _order("wilma", cfg)
    assert apply_compliance(order, 0.5, seed=7) == apply_compliance(order, 0.5, seed=7)
    assert apply_compliance(order, 0.5, seed=7) != apply_compliance(order, 0.5, seed=8)


def test_zero_compliance_is_method_independent():
    # at Rc=0 every passenger is displaced, so the result depends only on the seat set
    # and seed, not on the input method's order (the paper's convergence to Random)
    cfg = BoardingConfig(rows=5)
    a = apply_compliance(_order("steffen_perfect", cfg), 0.0, seed=5)
    b = apply_compliance(_order("random", cfg), 0.0, seed=5)
    assert a == b
    assert set(a) == set(all_seats(cfg))


def test_partial_compliance_changes_the_order():
    cfg = BoardingConfig(rows=8)
    order = _order("steffen_perfect", cfg)
    assert apply_compliance(order, 0.5, seed=1) != order
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_compliance.py -v`; expect ModuleNotFoundError.

- [ ] **Step 3: Implementation** (`src/boarding/compliance.py`):

```python
import random

from .config import Seat


def apply_compliance(order: list[Seat], rate: float, seed: int) -> list[Seat]:
    """Perturb a boarding order by non-compliant passengers.

    ``n = round((1 - rate) * len(order))`` passengers are chosen non-compliant from a
    canonical seat ordering (so the same passengers are non-compliant for a given seed,
    independent of method — paired). They are removed from ``order`` (compliant passengers
    keep their relative order) and reinserted at uniformly random positions. Returns a
    permutation of ``order``. rate=1.0 -> unchanged; rate=0.0 -> a method-independent
    random permutation (depends only on the seat set + seed).
    """
    n = round((1.0 - rate) * len(order))
    if n <= 0:
        return list(order)
    rng = random.Random(seed)
    canonical = sorted(order, key=lambda s: (s.row, s.side, s.col))
    noncompliant = set(rng.sample(canonical, n))
    compliant = [s for s in order if s not in noncompliant]
    displaced = [s for s in canonical if s in noncompliant]
    rng.shuffle(displaced)
    result = list(compliant)
    for seat in displaced:
        result.insert(rng.randint(0, len(result)), seat)
    return result
```

- [ ] **Step 4: Run** the test; expect 5 passing.
- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/compliance.py tests/test_compliance.py
git commit -m "feat: compliance-rate order perturbation (displace + reinsert)"
```

---

### Task 2: `config.py` — `compliance_rate`

**Files:** Modify `src/boarding/config.py`; Test `tests/test_config.py` (append).

- [ ] **Step 1: Failing test** (append to `tests/test_config.py`):

```python
def test_compliance_rate_defaults_to_one():
    from boarding.config import BoardingConfig
    assert BoardingConfig().compliance_rate == 1.0


def test_compliance_rate_can_be_set():
    from boarding.config import BoardingConfig
    assert BoardingConfig(compliance_rate=0.5).compliance_rate == 0.5
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_config.py -v`; expect FAIL (`unexpected keyword argument 'compliance_rate'`).

- [ ] **Step 3: Implementation** — add this field to `BoardingConfig`, immediately AFTER the existing
`group_fraction` field (keep all other fields untouched, do not reformat):

```python
    # passenger compliance: 1.0 = everyone boards in their assigned slot (baseline);
    # below 1.0, that fraction of passengers is displaced to random positions
    compliance_rate: float = 1.0
```

- [ ] **Step 4: Run** the test; expect PASS. Then full suite `…/.venv/bin/python -m pytest tests -q` (report count).
- [ ] **Step 5: Lint + commit**

```bash
…/.venv/bin/ruff check src/boarding tests
git add src/boarding/config.py tests/test_config.py
git commit -m "feat: optional compliance_rate on BoardingConfig (default 1.0)"
```

---

### Task 3: `experiment.py` — apply compliance when `< 1.0`

**Files:** Modify `src/boarding/experiment.py`; Test `tests/test_experiment_smoke.py` (append).

The baseline (`compliance_rate == 1.0`) must be byte-identical: no reorder happens.

- [ ] **Step 1: Failing test** (append to `tests/test_experiment_smoke.py`):

```python
def test_compliance_does_not_change_the_baseline_at_full_compliance():
    cfg = _tiny()
    assert cfg.compliance_rate == 1.0
    assert run_boarding("random", seed=0, config=cfg).total_time == pytest.approx(82.5)
    assert run_boarding("front_to_back", seed=0, config=cfg).total_time == pytest.approx(99.3)


def test_low_compliance_completes_and_slows_steffen_perfect():
    base = BoardingConfig(rows=4, spawn_headway=1.0)
    noncompliant = replace(base, compliance_rate=0.3)
    r = run_boarding("steffen_perfect", seed=0, config=noncompliant)
    assert r.seated_count == noncompliant.total_passengers
    # displacing passengers degrades steffen's perfect order -> not faster than full compliance
    assert r.total_time >= run_boarding("steffen_perfect", seed=0, config=base).total_time
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_experiment_smoke.py -k compliance -v`; expect FAIL (compliance unwired → the >= assertion equal, or import).

- [ ] **Step 3: Implementation** — in `src/boarding/experiment.py`:
1. Add import with the other `from .` imports:
```python
from .compliance import apply_compliance
```
2. Find the existing block that applies group cohesion:
```python
    if cfg.group_fraction > 0:
        order = cohesive_order(order, assign_groups(cfg, seed, cfg.group_fraction))
```
and add, immediately AFTER it:
```python
    if cfg.compliance_rate < 1.0:
        order = apply_compliance(order, cfg.compliance_rate, seed)
```
Leave everything else unchanged.

- [ ] **Step 4: Run** `…/.venv/bin/python -m pytest tests/test_experiment_smoke.py -v`; expect all pass.
- [ ] **Step 5: Full regression + lint**

```bash
…/.venv/bin/python -m pytest tests -q
…/.venv/bin/ruff check src/boarding tests
```
Expect all pass (the at-full pin confirms the baseline is intact), lint clean. ALSO confirm the baseline
is unchanged and report the number:
```bash
PYTHONPATH=src …/.venv/bin/python -c "from boarding.config import BoardingConfig; from boarding.experiment import run_boarding; print(round(run_boarding('steffen_perfect',1,BoardingConfig(rows=30)).total_time,3))"
```
Expect ~369.7 (the committed baseline).

- [ ] **Step 6: Commit**

```bash
git add src/boarding/experiment.py tests/test_experiment_smoke.py
git commit -m "feat: apply compliance-rate perturbation when compliance_rate < 1.0"
```

---

### Task 4: `compliancesweep.py` — sweep + curve + CLI

**Files:** Create `src/boarding/compliancesweep.py`; Create `tests/test_compliancesweep.py`.

- [ ] **Step 1: Failing test** (`tests/test_compliancesweep.py`):

```python
import pandas as pd

from boarding.compliancesweep import compliance_plot, sweep_compliance
from boarding.config import BoardingConfig


def test_sweep_compliance_shape():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    df = sweep_compliance(
        ["random", "steffen_perfect"], rates=[1.0, 0.5], seeds=[0], config=cfg
    )
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"method", "compliance_rate", "seed", "total_time"}
    assert len(df) == 2 * 2 * 1  # methods x rates x seeds


def test_compliance_plot_writes_png(tmp_path):
    df = pd.DataFrame(
        [
            {"method": "random", "compliance_rate": 1.0, "seed": 0, "total_time": 10.0},
            {"method": "random", "compliance_rate": 0.0, "seed": 0, "total_time": 11.0},
            {"method": "steffen_perfect", "compliance_rate": 1.0, "seed": 0, "total_time": 8.0},
            {"method": "steffen_perfect", "compliance_rate": 0.0, "seed": 0, "total_time": 11.0},
        ]
    )
    out = compliance_plot(df, tmp_path / "c.png")
    assert out.exists()
```

- [ ] **Step 2: Run** `…/.venv/bin/python -m pytest tests/test_compliancesweep.py -v`; expect ModuleNotFoundError.

- [ ] **Step 3: Implementation** (`src/boarding/compliancesweep.py`):

```python
import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .analysis import CANONICAL_ORDER, COMPARISON_YLIM
from .config import BoardingConfig
from .experiment import run_boarding
from .methods import METHODS


def sweep_compliance(
    methods: Sequence[str],
    rates: Sequence[float],
    seeds: Sequence[int],
    config: BoardingConfig | None = None,
) -> pd.DataFrame:
    """Run every (method, rate, seed); seeds paired across methods and rates."""
    base = config or BoardingConfig()
    rows = []
    for rate in rates:
        cfg = replace(base, compliance_rate=rate)
        for seed in seeds:
            for method in methods:
                res = run_boarding(method, seed, cfg)
                rows.append(
                    {
                        "method": method,
                        "compliance_rate": rate,
                        "seed": seed,
                        "total_time": res.total_time,
                    }
                )
    return pd.DataFrame(rows)


def compliance_plot(df: pd.DataFrame, out_path: Path) -> Path:
    """Mean boarding time vs compliance rate, one line per method (x inverted: 100% -> 0%)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    present = set(df["method"])
    methods = [m for m in CANONICAL_ORDER if m in present]
    fig, ax = plt.subplots(figsize=(9, 6))
    for method in methods:
        sub = df[df["method"] == method].groupby("compliance_rate")["total_time"].mean()
        ax.plot(sub.index, sub.to_numpy(), marker="o", label=method)
    ax.set_xlabel("compliance rate")
    ax.set_ylabel("mean boarding time (s)")
    ax.set_ylim(*COMPARISON_YLIM)
    ax.invert_xaxis()  # 100% -> 0% left to right, matching the paper
    ax.set_title("Boarding time vs compliance rate")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compliance-rate sensitivity sweep.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--rates", nargs="+", type=float, default=[1.0, 0.75, 0.5, 0.25, 0.0])
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("study-output"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df = sweep_compliance(
        args.methods, args.rates, list(range(args.seeds)), config=cfg
    )
    df.to_csv(args.out / "compliance_sweep.csv", index=False)
    compliance_plot(df, args.out / "compliance_erosion.png")
    pivot = df.groupby(["compliance_rate", "method"])["total_time"].mean().unstack()
    print(pivot.to_string())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run** `…/.venv/bin/python -m pytest tests/test_compliancesweep.py -v`; expect 2 passing.
- [ ] **Step 5: Full suite + lint**

```bash
…/.venv/bin/python -m pytest tests -q
…/.venv/bin/ruff check src/boarding tests
```
- [ ] **Step 6: CLI smoke (tiny)**

```bash
PYTHONPATH=src …/.venv/bin/python -m boarding.compliancesweep --methods random steffen_perfect --rates 1.0 0.0 --seeds 1 --rows 3 --out /tmp/compliance_smoke
ls /tmp/compliance_smoke
```
Expect a printed pivot and files `compliance_sweep.csv`, `compliance_erosion.png`. Report what printed.
- [ ] **Step 7: Commit**

```bash
git add src/boarding/compliancesweep.py tests/test_compliancesweep.py
git commit -m "feat: compliance-rate sweep + curve + CLI"
```

---

### Task 5: Run the sweep + write-up + README section

**Files:** Create `docs/results-compliance.md`; artifacts `docs/study-output/compliance_sweep.csv`, `compliance_erosion.png`; Modify `README.md`.

- [ ] **Step 1: Run the sweep**

```bash
PYTHONPATH=src …/.venv/bin/python -m boarding.compliancesweep --seeds 20 --rows 30 --out docs/study-output
```
~5–8 min (6 methods × 5 rates × 20 seeds = 600 runs). Note the printed pivot (mean time per rate × method).

- [ ] **Step 2: Write `docs/results-compliance.md`** — include a `compliance_rate × method` mean table,
the curve, and the findings: (a) do the methods **converge** as the compliance rate drops; (b) do they
**collapse to Random at `Rc = 0`** (the optimized methods should lose their advantage); (c) which methods
are most compliance-sensitive. Add an explicit comparison to Dong et al. (2025) Fig 16 (their
Outside-in / Steffen / Double-Outside-in are the most affected; Random is flat). State that absolute
times differ (their multi-aisle BWB CA vs our single-aisle continuous model) — the **trend** is the
deliverable. Report numbers actually produced; do not assume the direction.

- [ ] **Step 3: Add a README section** "## Passenger compliance (order discipline)" AFTER the existing
"## Travel groups" section and BEFORE "## Visualize". Do NOT modify other sections. Include: a
one-paragraph explanation, the run command
`python -m boarding.compliancesweep --seeds 20 --rows 30 --out study-output`, the headline finding, the
embedded plot `![compliance erosion](docs/study-output/compliance_erosion.png)`, a one-line note that
this reproduces the trend of Dong et al. (2025), and links to `docs/results-compliance.md` and
`docs/compliance-design.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/results-compliance.md docs/study-output/compliance_sweep.csv README.md
git add -f docs/study-output/compliance_erosion.png
git commit -m "docs: compliance-rate study results + README section"
```

---

## Self-Review

**Spec coverage:**
- `apply_compliance` displace+reinsert, canonical method-independent selection, rate=1 unchanged,
  rate=0 method-independent random → Task 1. ✓
- `config.compliance_rate` default 1.0 = baseline → Task 2. ✓
- `experiment.py` applies only when `< 1.0`; baseline byte-identical → Task 3 (pinned test). ✓
- Sweep + inverted-x curve + CLI defaults `[1.0,0.75,0.5,0.25,0.0]`/20 seeds → Task 4. ✓
- Fig-16 reproduction write-up + README section (others unchanged) → Task 5. ✓
- Tests: unchanged@1, permutation, determinism, method-independent@0, partial-changes; baseline pin,
  completes+slows steffen; sweep shape, plot writes → Tasks 1, 3, 4. ✓

**Placeholder scan:** No TBD/TODO; every code step complete. Task 5 is a run+write task (report produced numbers), not a stub.

**Type consistency:** `apply_compliance(order, rate, seed) -> list[Seat]` used consistently in Tasks 1, 3.
`sweep_compliance(methods, rates, seeds, config)` and `compliance_plot(df, out_path)` match their test
call sites in Task 4. `cfg.compliance_rate` referenced consistently. `CANONICAL_ORDER`/`COMPARISON_YLIM`
imported from `analysis` as in `groupsweep.py`.

> **Baseline-preservation note:** the at-full-compliance pin
> (`test_compliance_does_not_change_the_baseline_at_full_compliance`) reuses the exact homogeneous values
> (82.5 / 99.3). If they drift, the `compliance_rate < 1.0` guard in Task 3 leaked into the default path —
> fix before proceeding.
