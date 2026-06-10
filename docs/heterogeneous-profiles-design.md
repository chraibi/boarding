# Passenger Time-to-Sitting Profiles — Design Spec

**Date:** 2026-06-10
**Status:** Approved (design); pending implementation plan
**Repo:** `playground/boarding`
**Motivation:** Steffen's optimal method assumes homogeneous passengers in a perfect single-file
order — a key reason no airline adopts it. This adds **per-passenger heterogeneity in time-to-sitting**
(age/mobility, luggage, kids) while keeping perfect method ordering, to quantify how much each
method's boarding time shifts under a realistic passenger mix.

## Scope

- **In:** per-passenger profiles modulating walk speed, luggage-stow time, and seat-shuffle
  (interference) speed; one fixed realistic mix; a 6-method comparison under that mix.
- **Out (future):** group/family cohesion, latecomers, imperfect order compliance (axis 2 — the
  social structure that breaks perfect ordering). Sensitivity sweeps over the mix.

## The passenger profile

A `Profile` is a named bundle of multipliers on the existing model levers:

```
Profile(name, weight, walk_speed_factor, stow_mean, stow_sd, mobility_factor)
```

- `walk_speed_factor` × `cfg.v0` → the passenger's `desired_speed` (aisle walking speed).
- `stow_mean`, `stow_sd` → the Gamma the passenger's luggage-stow time is drawn from.
- `mobility_factor` × `seat_interference_penalty` → how slowly they shuffle past seated neighbors.

A passenger's **time to sitting** = walk time (now speed-dependent) + hold, where
`hold = stow_time + mobility_factor × seat_interference_penalty(seat, occupied, cfg)`.

## Default realistic mix (`DEFAULT_MIX`)

Weights sum to 1; illustrative starting values, tunable.

| profile           | weight | walk× | stow mean (s) | stow sd (s) | mobility× | who |
|-------------------|--------|-------|---------------|-------------|-----------|-----|
| standard          | 0.45   | 1.00  | 7             | 3           | 1.0       | typical adult, one bag |
| business_young    | 0.15   | 1.15  | 2             | 1           | 0.9       | fast, little/no bag |
| heavy_luggage     | 0.15   | 0.95  | 14            | 5           | 1.2       | two bags, slow stow |
| elderly           | 0.15   | 0.60  | 10            | 4           | 1.8       | slow walk, slow shuffle |
| family_with_kids  | 0.10   | 0.70  | 16            | 6           | 2.0       | kids + multiple bags, slowest |

## Architecture

### New module `profiles.py`

- `Profile` frozen dataclass (fields above).
- `DEFAULT_MIX: tuple[Profile, ...]` — the table above.
- `PassengerParams` (per occupant): `speed_factor`, `stow_time`, `mobility_factor`, `profile_name`.
- `draw_passengers(cfg, seed, mix) -> dict[Seat, PassengerParams]`:
  - iterate seats in **canonical `all_seats(cfg)` order** from a dedicated `random.Random(seed)`;
  - for each seat pick a profile by weighted choice, then draw its stow time from the profile Gamma;
  - returns one `PassengerParams` per seat. **Paired across methods** (same seed ⇒ same occupant at
    each seat, independent of boarding method), exactly like `draw_luggage` today.

### `config.py`

- Add `profile_mix: tuple[Profile, ...] | None = None`.
- **Default `None` = current homogeneous behavior, byte-identical.** The committed 20-seed study and
  all existing tests are unaffected because the homogeneous code path and its RNG usage are unchanged.

### `experiment.py`

- When `cfg.profile_mix is None`: the existing path runs unchanged — `draw_luggage`, uniform
  `cfg.v0`, `hold = luggage[seat] + interference`.
- When a mix is set: `pax = draw_passengers(cfg, seed, cfg.profile_mix)`; build a **fresh** agent
  params per spawn with `desired_speed = cfg.v0 × pax[seat].speed_factor`; and
  `hold = pax[seat].stow_time + pax[seat].mobility_factor × seat_interference_penalty(...)`.
- The state machine, spawn gating, removal, and completeness guard are untouched.

### `cli.py`

- `--mix` flag: run the sweep under `DEFAULT_MIX` (writes `ranking_mix.csv`, `results_mix.csv`,
  `boarding_times_mix.png` so the homogeneous artifacts are not overwritten).

## Deliverable

- Run all six methods under `DEFAULT_MIX`, 20 paired seeds.
- `docs/results-heterogeneous.md`: the heterogeneous ranking table, the box plot, and the two
  headline answers — **does the method ranking hold** under a realistic mix, and **how much do
  absolute times inflate** versus the uniform baseline (per method).

## Testing

- `draw_passengers` is deterministic for a seed and **paired** (same seed ⇒ identical assignment,
  independent of any method); over many seats the profile frequencies roughly match the weights.
- **Homogeneous regression:** `run_boarding` with default config (mix `None`) returns the same
  `total_time` as before for a fixed seed (baseline preserved).
- A heterogeneous run completes (all seated) and its mean time is **greater** than the homogeneous
  run for the same method/seed (slower passengers ⇒ longer boarding).
- Per-profile params flow end-to-end: a mix of all-fast profiles boards faster than all-slow.

## Engineering assessment

Additive and opt-in; reuses the existing penalty function, run loop, and pairing pattern; preserves
the published baseline exactly. The only new abstraction is the `Profile` bundle the feature
genuinely needs. Appropriately engineered — not over-built (no group logic, no sweep yet), not
under-built (pairing + baseline-preservation + regression test guard scientific validity).

## Open questions / risks

1. **Profile numbers** are illustrative; calibrate against boarding-time literature if a quantitative
   claim is needed. For the ranking-robustness question, relative ordering of the multipliers is what
   matters.
2. **Interference attribution** is charged to the *boarding* passenger's `mobility_factor` only (not
   the seated neighbors'). A reasonable simplification; revisit only if it distorts the ranking.
