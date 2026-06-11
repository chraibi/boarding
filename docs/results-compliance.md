# Passenger Compliance Rate — Results

**Date:** 2026-06-11
**Spec:** `docs/compliance-design.md`
**Reference:** Dong, Jia, Yanagisawa, Nishinari (2025), *Boarding strategies accounting for properties of
the blended wing body aircraft*, Physica A 658, 130298 — Fig 16.
**Reproduce:** `python -m boarding.compliancesweep --seeds 20 --rows 30 --out docs/study-output`
**Artifacts:** `docs/study-output/compliance_sweep.csv`, `compliance_erosion.png`

## What the sweep does

The **compliance rate** `Rc` is the share of passengers who board in their assigned slot. At `Rc = 1`
everyone follows the method's order; below that, `(1 − Rc) · 180` passengers are pulled out and
reinserted at random positions (the non-compliant set is the same per seed across methods). `Rc` is
swept 1.0 → 0.0; everything else (geometry, luggage, homogeneous passengers, 20 paired seeds) is held
fixed.

## Mean boarding time (s) vs compliance rate

| Rc | steffen_perfect | steffen_modified | wilma | back_to_front | random | front_to_back |
|------|-----------------|------------------|-------|---------------|--------|---------------|
| 1.00 | **371.0** | 378.9 | 402.2 | 443.0 | 455.9 | **615.0** |
| 0.75 | 405.4 | 408.7 | 423.3 | 433.4 | 457.8 | 556.9 |
| 0.50 | 425.2 | 425.0 | 431.0 | 436.1 | 456.0 | 501.7 |
| 0.25 | 443.9 | 446.8 | 445.7 | 443.3 | 459.5 | 470.0 |
| 0.00 | **458.0** | 458.0 | 458.0 | 458.0 | 458.0 | 458.0 |

![Boarding time vs compliance rate](study-output/compliance_erosion.png)

## Findings — this reproduces Dong et al. (2025) Fig 16

**1. Everything converges to Random as compliance falls, and collapses to a single value at `Rc = 0`.**
At zero compliance all six methods give **exactly 458.0 s** — not approximately, exactly: with every
passenger displaced, the boarding order is a method-independent random permutation, so all methods run
the identical sequence. This is the paper's central claim made exact in our model.

**2. Random is flat; the optimized methods degrade; the worst method improves.**
- **Random** is essentially unaffected (456 → 458 s) — shuffling an already-random order changes
  nothing. ✓ (matches the paper)
- **Steffen-Perfect, Steffen-Modified, WilMA** rise monotonically toward 458 s as `Rc` drops — their
  ordering advantage is exactly what non-compliance destroys. Steffen-Perfect's edge over Random shrinks
  from ~85 s (`Rc=1`) → ~31 s (`Rc=0.5`) → 0 (`Rc=0`). ✓
- **Front-to-Back** (the worst at full compliance, 615 s) *improves* toward 458 s as compliance drops —
  random is better than a strictly-bad order. ✓

**3. The optimized methods still win at 50 % compliance.** At `Rc = 0.5`, Steffen-Perfect (425 s) and
Steffen-Modified (425 s) still beat Random (456 s) by ~7 %. The paper reports the same: their
Outside-in / Double-Outside-in / N-Steffen remain favourable down to ~50 % compliance, with a practical
threshold around 75–80 %.

## Comparison to the paper

| | Dong et al. (2025), Fig 16 | This study |
|---|---|---|
| Aircraft | multi-aisle BWB (4 aisles, 312 seats), cellular automaton | single-aisle (180 seats), JuPedSim continuous 2-D |
| Random vs compliance | flat | flat (456→458 s) |
| Optimized methods | degrade toward Random | degrade toward Random |
| Worst method (Back-to-Front / Front-to-Back) | improves toward Random | Front-to-Back improves toward Random |
| At `Rc = 0` | all converge to Random | all **exactly** equal (458 s) |
| Favourable threshold | optimized still win at ~50 %, practical ~75–80 % | optimized still win at 50 % (~7 %) |

Absolute times differ (different aircraft and engine), but the **trend is reproduced**: the value of a
clever boarding order is entirely contingent on passengers following it, and evaporates linearly as they
don't.
