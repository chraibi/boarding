# Travel Groups & Boarding-Order Cohesion — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design); pending implementation plan
**Repo:** `playground/boarding`
**Motivation:** Steffen's optimal method needs passengers in a flawless single-file window→middle→aisle
order. Real travel parties (families, couples) board **together** and cannot be split across that
sequence — a central reason airlines reject the method. This models groups that board cohesively and
measures, via a sweep over the group fraction, how much each method's advantage erodes.

## Scope

- **In:** groups of 2–3 in adjacent same-bench seats; cohesive boarding (a group's members board
  consecutively, window-first); a sensitivity **sweep** over `group_fraction` with an erosion plot.
- **Out (future):** groups of 4+ spanning the aisle / two rows; arbitrary within-group order;
  combining groups with Phase-1 passenger profiles. This axis is measured on the **homogeneous**
  baseline to isolate the lost-spacing effect.

## Concepts

- **`group_fraction` ∈ [0, 1]** — the share of the 180 passengers travelling in a group (the rest are
  solo). This is the swept independent variable.
- **Bench** — the `seats_per_side` (3) seats on one side of one row: window (col 2), middle (col 1),
  aisle (col 0). A group occupies adjacent seats within a single bench.
- **Group** — 2 or 3 passengers in one bench. Size drawn from `{2: 0.5, 3: 0.5}`. A 3-group fills the
  bench (window+middle+aisle); a 2-group takes window+middle (the aisle seat becomes solo). Cap at 3
  for this version; cross-aisle / multi-row 4+ groups are a noted future extension.
- **Window-first cohesion (charitable)** — when a group boards, its members enter outermost-seat-first
  (col descending), so they never make each other stand. The measured erosion is therefore purely the
  loss of the method's global spacing/parallelization — a clean lower bound on how much groups hurt.

## Architecture

### New module `groups.py`

- `assign_groups(cfg, seed, group_fraction) -> dict[Seat, int]`:
  - one `group_id` per seat; solo passengers each get a unique singleton id.
  - iterate benches `(row, side)` in a **seeded-shuffled** order; for each, if more grouped
    passengers are still needed to reach `round(group_fraction * total_passengers)`, form a group of
    size 2 or 3 (seeded weighted choice) from that bench's window-out seats and give them a shared id;
    otherwise leave the bench's seats as singletons. Stop once the target grouped count is reached.
  - **method-independent and seeded** → the same families/seats for a given `(seed, group_fraction)`
    regardless of boarding method (paired replication). `group_fraction = 0` → every seat a singleton.
- `cohesive_order(method_order, groups) -> list[Seat]`:
  - walk `method_order`; at each seat, look up its group; if the group has not yet been emitted, emit
    **all** its members consecutively sorted by `col` **descending** (window-first); mark emitted and
    skip those members when reached later. Solo seats emit in place.
  - returns a permutation of `method_order`; with all-singleton groups it returns it unchanged.

### `config.py`

- Add `group_fraction: float = 0.0`. **Default `0.0` = no groups = baseline byte-identical** (no
  reordering). Composes with `profile_mix=None`.

### `experiment.py`

- In `run_boarding`, after `order = METHODS[method](cfg, random.Random(seed))`:
  - if `cfg.group_fraction > 0`: `groups = assign_groups(cfg, seed, cfg.group_fraction)`;
    `order = cohesive_order(order, groups)`.
  - else: leave `order` unchanged (existing path; baseline preserved).
- Nothing else changes — `order` already drives the spawn queue.

### Sweep + analysis (`groupsweep.py`)

- `sweep_group_fraction(methods, fractions, seeds, cfg) -> pandas.DataFrame` with columns
  `method, group_fraction, seed, total_time` (runs `run_boarding` with `replace(cfg,
  group_fraction=f)` for each `f`; seeds paired across methods and fractions).
- `erosion_plot(df, out_path)` — x = `group_fraction`, y = mean boarding time, one line per method
  (markers + light CI band optional); saves a PNG.
- `main()` (`python -m boarding.groupsweep`): default `--fractions 0 0.2 0.4 0.6 0.8`, `--seeds 20`,
  `--rows 30`, `--out docs/study-output`; writes `group_sweep.csv` and `group_erosion.png`.

## Deliverable

- The **erosion curve** (`group_erosion.png`) + `group_sweep.csv`.
- `docs/results-groups.md`: the curve, and the two findings — (a) how each method's time rises with
  `group_fraction`, and (b) at what fraction Steffen-Perfect's line crosses the others (where its edge
  dies / converges toward random). Report numbers actually produced.
- A new README section (the basic and heterogeneity sections stay unchanged).

## Testing

- `assign_groups`: deterministic + paired for a `(seed, group_fraction)`; grouped-passenger fraction
  ≈ `group_fraction` (within tolerance on a large cabin); grouped seats are adjacent within one bench
  (same row+side, contiguous cols from the window); `group_fraction = 0` → all singleton ids.
- `cohesive_order`: returns a permutation of the input; members of a group are consecutive and ordered
  window-first; an all-singleton mapping returns the order unchanged.
- `experiment.py`: `group_fraction = 0` reproduces the pinned baseline values; a run with
  `group_fraction = 0.6` completes (all seated); `steffen_perfect` total time increases monotone-ish
  with `group_fraction` (slower as groups clump) on a fixed seed (sanity, not a strict claim).

## Engineering assessment

Additive and opt-in; reuses the run loop, the seeded-pairing pattern, and the analysis/plot
conventions; preserves the baseline (`group_fraction = 0`) exactly and isolates the axis from
Phase-1 profiles. The only new logic is group assignment + the cohesion reordering the feature
requires. Appropriately engineered — not over-built (no 4+/cross-aisle groups, no arbitrary
within-group order, no profile coupling), not under-built (pairing + baseline pin + adjacency tests
guard validity).

## Open questions / risks

1. **Group-size cap at 3** keeps clustering to a single bench (clean adjacency). 4+ families
   (cross-aisle or two rows) are deferred; note this in the write-up so the erosion is read as a
   conservative estimate (real groups can be larger and messier).
2. **Window-first within-group order** makes the curve a lower bound; arbitrary order would erode more.
   Stated explicitly in the results.
3. **Anchor = earliest member** clumps a group at its first-ordered seat. For Steffen-Perfect, whose
   members are spread far apart in the order, this is the maximal disruption — exactly the effect under
   study. No risk, but document the choice.
