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


def test_noncompliant_set_is_method_independent():
    # the load-bearing paired-replication guarantee: same passengers non-compliant for a
    # given (seed, rate), regardless of boarding method
    from boarding.compliance import noncompliant_seats

    cfg = BoardingConfig(rows=8)
    a = noncompliant_seats(_order("steffen_perfect", cfg), 0.5, seed=4)
    b = noncompliant_seats(_order("random", cfg), 0.5, seed=4)
    assert a == b
    assert len(a) == round(0.5 * cfg.total_passengers)


def test_compliant_passengers_keep_their_relative_order():
    from boarding.compliance import noncompliant_seats

    cfg = BoardingConfig(rows=8)
    order = _order("steffen_perfect", cfg)
    out = apply_compliance(order, 0.5, seed=2)
    nc = noncompliant_seats(order, 0.5, seed=2)
    in_compliant = [s for s in order if s not in nc]
    out_compliant = [s for s in out if s not in nc]
    assert out_compliant == in_compliant  # compliant subsequence order preserved


def test_zero_compliance_differs_from_input():
    cfg = BoardingConfig(rows=5)
    order = _order("steffen_perfect", cfg)
    assert apply_compliance(order, 0.0, seed=5) != order
