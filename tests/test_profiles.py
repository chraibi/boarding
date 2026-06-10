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
    cfg = BoardingConfig(rows=6)
    a = draw_passengers(cfg, seed=5, mix=DEFAULT_MIX)
    b = draw_passengers(cfg, seed=5, mix=DEFAULT_MIX)
    assert a == b
    c = draw_passengers(cfg, seed=6, mix=DEFAULT_MIX)
    assert a != c


def test_profile_frequencies_roughly_match_weights():
    cfg = BoardingConfig(rows=60)
    pax = draw_passengers(cfg, seed=1, mix=DEFAULT_MIX)
    n = len(pax)
    standard = sum(1 for p in pax.values() if p.profile_name == "standard") / n
    assert 0.35 < standard < 0.55


def test_single_profile_mix_assigns_that_profile_to_all():
    cfg = BoardingConfig(rows=4)
    only_fast = (Profile("fast", 1.0, 1.5, 2.0, 1.0, 0.8),)
    pax = draw_passengers(cfg, seed=0, mix=only_fast)
    assert all(p.profile_name == "fast" for p in pax.values())
