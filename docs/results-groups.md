# Travel Groups & Cohesion — Results

**Date:** 2026-06-10
**Spec:** `docs/groups-design.md`
**Reproduce:** `python -m boarding.groupsweep --seeds 20 --rows 30 --out docs/study-output`
**Artifacts:** `docs/study-output/group_sweep.csv`, `group_erosion.png`

## What the sweep does

A fraction of the 180 passengers travel in groups seated together in one bench (window/middle/aisle of
a row-side). Each group boards **cohesively** — its members enter consecutively, **window-first** (so
they never make each other stand). Everything not in the table below (geometry, luggage, homogeneous
passengers) is held fixed, so the only thing changing is how much the perfect single-file order is
clumped by parties boarding together.

| Parameter            | Value |
|----------------------|-------|
| `group_fraction` sweep | 0.0, 0.2, 0.4, 0.6, 0.8 |
| Group sizes (weights)  | 2 (0.5), 3 (0.5) |
| Group seating          | adjacent window-out seats of one bench (row + side); max size 3 |
| Within-group board order | window → middle → aisle (no within-group interference) |
| Cohesion anchor        | the group's earliest position in the method's order |
| Passengers             | homogeneous (groups studied in isolation from profiles) |
| Seeds                  | 20 paired (same group structure per seed across methods) |
| Cabin                  | 30 rows × 6 seats = 180 passengers |

(Values from `assign_groups` / `_GROUP_SIZES` in `src/boarding/groups.py` and the `groupsweep`
defaults.)

## Mean boarding time (s) vs group fraction

| group_fraction | steffen_perfect | steffen_modified | wilma | back_to_front | random | front_to_back |
|----------------|-----------------|------------------|-------|---------------|--------|---------------|
| 0.0 | **371.0** | 378.9 | 402.2 | 443.0 | 455.9 | 615.0 |
| 0.2 | 373.9 | 378.9 | 403.2 | 435.6 | 451.6 | 600.2 |
| 0.4 | 378.0 | 378.9 | 405.5 | 429.7 | 449.1 | 587.7 |
| 0.6 | 382.7 | 378.9 | 407.9 | 425.8 | 438.5 | 570.0 |
| 0.8 | **388.8** | 378.9 | 410.4 | 421.0 | 427.9 | 553.7 |

![Boarding time vs group fraction](study-output/group_erosion.png)

## Findings

**1. Steffen-Perfect is the only method that gets *worse* as groups grow** (371 → 389 s, +4.8%). Its
advantage is built on spreading a bench's three passengers far apart in time so many people stow
luggage in parallel. A travelling party forces those three to board back-to-back, collapsing exactly
that parallelization. Groups attack the one method whose edge depends on perfect spacing.

**2. Steffen-Modified is completely group-immune** (flat 378.9 s at every fraction). It already boards
each bench's seats consecutively window-first, so enforcing group cohesion changes nothing about its
order — cohesion is a literal no-op for it. The practical variant is robust precisely because it never
relied on splitting parties apart.

**3. The crown changes hands at ~50% groups.** Steffen-Perfect leads at 0% (371 vs 379), the two are
tied near `group_fraction ≈ 0.4`, and beyond that **Steffen-Modified wins** decisively (379 vs 389 at
0.8). The theoretical optimum is the first casualty of group travel; the practical method that gives
families their natural row-by-row order overtakes it once even half the cabin travels together.

**4. The disordered methods speed up** (random 456 → 428, front-to-back 615 → 554, back-to-front
443 → 421). This is a consequence of the **window-first** cohesion: grouping a bench's passengers and
boarding them outermost-first removes the within-bench seat-interference that random/block orderings
otherwise incur. So the benefit is real but specific to well-behaved (window-first) groups.

## Caveats

- This is a **lower bound** on group disruption. Window-first cohesion is charitable (no within-group
  shuffle), and groups are capped at 3 (single bench). Arbitrary within-group order, or larger
  cross-aisle/multi-row families, would erode Steffen-Perfect further and would remove the speed-up the
  disordered methods enjoy here.
- Passengers are homogeneous here (groups studied in isolation from the [Phase-1 profiles](results-heterogeneous.md))
  so the curve measures the pure lost-spacing effect. Combining groups with slow-passenger profiles is
  future work.

## Takeaway

Across both realism axes — heterogeneous passengers and travelling groups — **Steffen-Perfect's
theoretical edge is the fragile part**, and the practical **Steffen-Modified** is what survives contact
with real passengers. That is a concrete, simulated version of why airlines adopt block/practical
schemes rather than the mathematically optimal sequence.
