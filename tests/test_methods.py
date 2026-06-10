import random

from boarding.config import BoardingConfig
from boarding.methods import METHODS, all_seats


def _cfg():
    return BoardingConfig(rows=6)


def test_every_method_returns_a_permutation_of_all_seats():
    cfg = _cfg()
    universe = set(all_seats(cfg))
    for name, fn in METHODS.items():
        order = fn(cfg, random.Random(0))
        assert len(order) == len(universe), name
        assert set(order) == universe, name


def test_back_to_front_boards_rear_rows_before_front_rows():
    cfg = _cfg()
    order = METHODS["back_to_front"](cfg, random.Random(0))
    assert order[0].row > order[-1].row


def test_wilma_boards_all_windows_before_any_aisle():
    cfg = _cfg()
    order = METHODS["wilma"](cfg, random.Random(0))
    last_window = max(i for i, s in enumerate(order) if s.col == 2)
    first_aisle = min(i for i, s in enumerate(order) if s.col == 0)
    assert last_window < first_aisle


def test_steffen_perfect_consecutive_boarders_skip_rows():
    cfg = _cfg()
    order = METHODS["steffen_perfect"](cfg, random.Random(0))
    assert all(order[i].row != order[i + 1].row for i in range(len(order) - 1))


def test_methods_are_deterministic_for_a_seed():
    cfg = _cfg()
    a = METHODS["random"](cfg, random.Random(42))
    b = METHODS["random"](cfg, random.Random(42))
    assert a == b
