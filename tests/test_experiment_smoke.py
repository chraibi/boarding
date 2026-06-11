from dataclasses import replace

import pandas as pd
import pytest

from boarding.config import BoardingConfig
from boarding.experiment import (
    BoardingResult,
    draw_luggage,
    run_boarding,
    sweep,
)
from boarding.profiles import DEFAULT_MIX, Profile


def _tiny():
    return BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=900.0)


def test_run_boarding_seats_everyone():
    cfg = _tiny()
    result = run_boarding("random", seed=0, config=cfg)
    assert isinstance(result, BoardingResult)
    assert result.seated_count == cfg.total_passengers
    assert result.total_time > 0
    assert len(result.seat_times) == cfg.total_passengers


def test_steffen_not_slower_than_front_to_back_on_one_seed():
    cfg = _tiny()
    steffen = run_boarding("steffen_perfect", seed=1, config=cfg).total_time
    f2b = run_boarding("front_to_back", seed=1, config=cfg).total_time
    assert steffen <= f2b


def test_sweep_returns_long_dataframe():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    df = sweep(["random", "steffen_perfect"], seeds=[0, 1], config=cfg)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"method", "seed", "total_time"}
    assert len(df) == 2 * 2  # methods x seeds


def test_luggage_is_paired_across_methods_and_seed_dependent():
    # the same seed gives identical per-seat luggage regardless of boarding method,
    # and a different seed gives different draws (common-random-number replication)
    cfg = BoardingConfig(rows=4)
    assert draw_luggage(cfg, 7) == draw_luggage(cfg, 7)
    assert draw_luggage(cfg, 7) != draw_luggage(cfg, 8)


def test_run_boarding_is_deterministic_for_a_seed():
    cfg = _tiny()
    a = run_boarding("random", seed=3, config=cfg).total_time
    b = run_boarding("random", seed=3, config=cfg).total_time
    assert a == b


def test_incomplete_run_raises_instead_of_corrupting_the_mean():
    # a too-small time budget must fail loudly, not return a partial result
    cfg = BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=2.0)
    with pytest.raises(RuntimeError, match="did not complete"):
        run_boarding("random", seed=0, config=cfg)


def test_seat_interference_penalty_lengthens_boarding_end_to_end():
    # exercises the live penalty path: quadrupling the per-neighbor penalty must
    # increase total boarding time for an order that creates seat interference
    base = BoardingConfig(rows=4, spawn_headway=1.0)
    high = replace(base, seat_penalty=base.seat_penalty * 4)
    assert (
        run_boarding("random", seed=2, config=high).total_time
        > run_boarding("random", seed=2, config=base).total_time
    )


def test_homogeneous_default_is_unchanged_by_the_feature():
    cfg = _tiny()
    assert cfg.profile_mix is None
    a = run_boarding("random", seed=0, config=cfg).total_time
    b = run_boarding("random", seed=0, config=cfg).total_time
    assert a == b


def test_homogeneous_baseline_is_pinned():
    # Guards the critical invariant: the heterogeneity feature must NOT shift the
    # homogeneous baseline. These deterministic values predate the profile_mix work;
    # if a future change moves them, the baseline (and the published study) drifted.
    cfg = _tiny()
    assert run_boarding("random", seed=0, config=cfg).total_time == pytest.approx(82.5)
    assert run_boarding("front_to_back", seed=0, config=cfg).total_time == pytest.approx(99.3)


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


def test_groups_do_not_change_the_baseline_at_zero_fraction():
    cfg = _tiny()
    assert cfg.group_fraction == 0.0
    assert run_boarding("random", seed=0, config=cfg).total_time == pytest.approx(82.5)
    assert run_boarding("front_to_back", seed=0, config=cfg).total_time == pytest.approx(99.3)


def test_groups_complete_and_slow_steffen_perfect():
    base = BoardingConfig(rows=4, spawn_headway=1.0)
    grouped = replace(base, group_fraction=0.8)
    r = run_boarding("steffen_perfect", seed=0, config=grouped)
    assert r.seated_count == grouped.total_passengers
    assert r.total_time >= run_boarding("steffen_perfect", seed=0, config=base).total_time


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
    assert r.total_time >= run_boarding("steffen_perfect", seed=0, config=base).total_time
