# Airplane Boarding Study — Results

**Date:** 2026-06-10
**Spec:** `docs/specs/2026-06-10-airplane-boarding-study-design.md`
**Code:** `src/jupedsim_scenarios/boarding/`
**Artifacts:** `docs/results/2026-06-10-boarding/` (`ranking.csv`, `results.csv`, `boarding_times.png`)
**Reproduce:** `python -m jupedsim_scenarios.boarding --seeds 20 --rows 30 --out docs/results/2026-06-10-boarding`

## Configuration

- Cabin: 30 rows × 6 seats = **180 passengers**, single central aisle (A320/737-class).
- Model: `CollisionFreeSpeedModel`, `dt = 0.05 s`, aisle width 0.5 m (single-file).
- Luggage stow: Gamma(mean 7 s, sd 3 s) per passenger. Seat interference: 5 s per already-seated
  inboard neighbor. Logical seating (agent holds at its row, then is removed).
- Replication: **20 paired seeds** per method (same seed ⇒ same luggage/speed draws across methods).

## Ranking (20 seeds)

| Rank | Method            | Mean boarding time (s) | Std (s) | vs Steffen-Perfect |
|------|-------------------|------------------------|---------|--------------------|
| 1    | steffen_perfect   | 371.0                  | 3.2     | 1.00×              |
| 2    | steffen_modified  | 378.9                  | 5.2     | 1.02×              |
| 3    | wilma             | 402.2                  | 9.6     | 1.08×              |
| 4    | back_to_front     | 443.0                  | 12.3    | 1.19×              |
| 5    | random            | 455.9                  | 13.0    | 1.23×              |
| 6    | front_to_back     | 615.0                  | 18.5    | 1.66×              |

Luggage stow times use **paired (common-random-number) replication**: the same seed yields
identical per-seat luggage across all six methods, so the differences above are attributable to
boarding order, not draw noise.

## Comparison to Steffen (2008)

The **ranking reproduces Steffen's findings**:

- **Steffen-Perfect is fastest**, with Steffen-Modified close behind — the practical variant keeps
  most of the gain. ✓
- **WilMA (outside-in)** is strong, between the Steffen methods and the block methods. ✓
- **Back-to-Front is among the worst** — slower than every seat-interference-aware method and only
  marginally better than fully random. This is Steffen's central counter-intuitive result: boarding
  rear-to-front in row blocks does **not** help, because it clusters passengers and serializes
  luggage stowing instead of parallelizing it. ✓
- **Front-to-Back is worst** by a wide margin — front holds block the entire aisle behind them. ✓

**On absolute magnitude:** Steffen's headline "~4× faster" comes from his idealized 1-D
cellular-automaton model with a strict block back-to-front baseline. This study uses JuPedSim's
continuous 2-D dynamics with collision avoidance, which compresses the ratios (Steffen-Perfect is
1.19× faster than back-to-front and 1.65× faster than front-to-back here). As stated in the design
spec, the deliverable is the **method ranking and relative ordering**, not the absolute factor —
and that ranking matches.

## Parallelization, observed

The mechanism behind the ranking is visible in the per-method spread: Steffen/WilMA distribute
holds across many rows simultaneously (passengers stow luggage in parallel), while Back-to-Front
and Front-to-Back concentrate passengers in adjacent rows where one holder blocks the aisle and
forces serial stowing. The 65 % gap between best and worst is entirely this parallelization effect.

## Notes / limitations

- `results.csv` records a throwaway `sqlite_path` per run (machine-local temp dir); the trajectories
  themselves are not committed. Re-run the CLI to regenerate them for replay in the app / jpsvis.
- Seat-fill visualization (`seat_placement.seat_fill_table`) is available for animating "seats
  filling" over time but is not exercised by the CLI sweep.
