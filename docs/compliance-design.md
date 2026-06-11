# Passenger Compliance Rate — Design Spec

**Date:** 2026-06-11
**Status:** Approved (design); pending implementation plan
**Repo:** `playground/boarding`
**Motivation & reference:** Dong, Jia, Yanagisawa, Nishinari (2025), *Boarding strategies accounting for
properties of the blended wing body aircraft*, Physica A 658, 130298 — their robustness study (Fig 16)
sweeps a **compliance rate** `Rc`: the share of passengers who board in their assigned slot. This adds
that axis to our model and checks whether we reproduce their trend — methods converge as compliance
drops, collapsing to Random at `Rc = 0`. It is a cleaner, more general "imperfect ordering" than our
window-first groups study.

## Scope

- **In:** a `compliance_rate` that perturbs any method's boarding order by displacing
  `(1 − Rc) · N` passengers and reinserting them at random positions; a sweep `Rc = 1.0 → 0.0` with a
  per-method curve; comparison to the paper's Fig 16.
- **Out (future):** combining compliance with profiles or groups (this axis is measured on the
  homogeneous, ungrouped baseline to isolate it). Calibrating `Rc` to real boarding data.

## The compliance model

`apply_compliance(order, rate, seed) -> list[Seat]`:

1. `n = round((1 − rate) · len(order))` passengers are **non-compliant**.
2. The non-compliant set is sampled from a **canonical** seat ordering (`sorted` by `(row, side, col)`),
   not from the method's order, so for a given `seed` the *same passengers* are non-compliant regardless
   of method — **paired replication**.
3. Compliant passengers keep their relative order from `order`; the non-compliant ones are reinserted at
   uniformly random positions (seeded).
4. Returns a permutation of `order`.

Edge behaviour:
- `rate = 1.0` → `n = 0` → the input order is returned unchanged (baseline).
- `rate = 0.0` → every passenger is displaced → the compliant list is empty and the output is a random
  permutation that depends only on `(canonical seats, seed)`, **independent of the input method**. This
  is the convergence the paper reports and a clean test hook.

All randomness uses a dedicated `random.Random(seed)`, decoupled from the method-order and luggage RNGs.

## Architecture

### New module `compliance.py`

`apply_compliance(order, rate, seed)` as above. No other public surface.

### `config.py`

- Add `compliance_rate: float = 1.0`.
- **Default `1.0` = full compliance = baseline byte-identical** (no reorder; no extra RNG consumed).
  Composes with `profile_mix` / `group_fraction`; the study sets those to their neutral defaults.

### `experiment.py`

In `run_boarding`, after `order = METHODS[method](cfg, random.Random(seed))` and after the optional
groups reorder:

```python
    if cfg.compliance_rate < 1.0:
        order = apply_compliance(order, cfg.compliance_rate, seed)
```

Nothing else changes — `order` already drives the spawn queue.

### Sweep + analysis (`compliancesweep.py`)

- `sweep_compliance(methods, rates, seeds, config) -> pandas.DataFrame` with columns
  `method, compliance_rate, seed, total_time` (runs `run_boarding` with `replace(cfg,
  compliance_rate=r)`; seeds paired across methods and rates).
- `compliance_plot(df, out_path)` — x = `compliance_rate` with the axis **inverted** (100% → 0%
  left-to-right, matching the paper), one line per method in `CANONICAL_ORDER`, y-limits
  `COMPARISON_YLIM`; saves a PNG.
- `main()` (`python -m boarding.compliancesweep`): default `--rates 1.0 0.75 0.5 0.25 0.0`,
  `--seeds 20`, `--rows 30`, `--out study-output`; writes `compliance_sweep.csv` and
  `compliance_erosion.png`.

## Deliverable

- The compliance curve (`compliance_erosion.png`) + `compliance_sweep.csv`.
- `docs/results-compliance.md`: the per-method curve and the headline checks — (a) do the methods
  **converge** as `Rc` falls, and (b) do they **collapse to Random at `Rc = 0`**? — with an explicit
  comparison to the paper's Fig 16 (their Outside-in / Steffen / Double-Outside-in are the most
  compliance-sensitive; Random is unaffected). Report numbers actually produced.
- A new README section (the basic / heterogeneity / groups sections stay unchanged).

## Testing

- `apply_compliance`: `rate = 1.0` returns the input unchanged; `rate = 0.0` returns a permutation that
  is **method-independent** (same output for two different input orders at the same seed) and not equal
  to the input; deterministic + paired for a `(seed, rate)`; the non-compliant *set* is the same across
  two different input orders at a given seed.
- `experiment.py`: `compliance_rate = 1.0` reproduces the pinned baseline values (82.5 / 99.3 for the
  tiny config); a `compliance_rate = 0.5` run completes (all seated); `steffen_perfect` total time
  increases as the rate drops (its order advantage is degraded).

## Engineering assessment

Additive and opt-in; reuses the run loop, the seeded-pairing pattern, and the sweep/plot conventions
(`CANONICAL_ORDER`, `COMPARISON_YLIM`); preserves the baseline (`compliance_rate = 1.0`) exactly and
isolates the axis. The only new logic is the displace-and-reinsert. Appropriately engineered.

## Open questions / risks

1. **Reinsertion model** — "reinsert at uniformly random positions, one at a time" is one reasonable
   reading of the paper's "added back to the boarding queue randomly." It yields a random permutation at
   `Rc = 0`, which matches their stated convergence; documented so the choice is explicit.
2. **Absolute times will not match the paper** (their multi-aisle BWB CA vs our single-aisle continuous
   model). As elsewhere, the deliverable is the *trend* — convergence and the relative ordering — not the
   absolute seconds.
