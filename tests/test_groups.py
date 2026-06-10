from collections import Counter

from boarding.config import BoardingConfig, Seat
from boarding.groups import assign_groups, cohesive_order
from boarding.methods import all_seats


def test_zero_fraction_makes_every_seat_a_singleton():
    cfg = BoardingConfig(rows=4)
    g = assign_groups(cfg, seed=0, group_fraction=0.0)
    assert len(set(g.values())) == cfg.total_passengers


def test_assign_groups_is_deterministic_and_method_independent():
    cfg = BoardingConfig(rows=6)
    a = assign_groups(cfg, seed=3, group_fraction=0.5)
    b = assign_groups(cfg, seed=3, group_fraction=0.5)
    assert a == b
    assert a != assign_groups(cfg, seed=4, group_fraction=0.5)


def test_grouped_fraction_is_approximately_the_target():
    cfg = BoardingConfig(rows=60)
    g = assign_groups(cfg, seed=1, group_fraction=0.5)
    sizes = Counter(g.values())
    grouped = sum(c for c in sizes.values() if c >= 2)
    assert 0.40 < grouped / cfg.total_passengers < 0.60


def test_group_members_are_adjacent_in_one_bench():
    cfg = BoardingConfig(rows=20)
    g = assign_groups(cfg, seed=2, group_fraction=0.7)
    members: dict[int, list[Seat]] = {}
    for seat, gid in g.items():
        members.setdefault(gid, []).append(seat)
    for seats in members.values():
        if len(seats) < 2:
            continue
        rows = {s.row for s in seats}
        sides = {s.side for s in seats}
        assert rows == {next(iter(rows))} and sides == {next(iter(sides))}
        cols = sorted(s.col for s in seats)
        assert cols == list(range(max(cols) - len(cols) + 1, max(cols) + 1))
        assert max(cols) == cfg.seats_per_side - 1


def test_cohesive_order_groups_members_window_first_and_is_a_permutation():
    cfg = BoardingConfig(rows=3)
    order = all_seats(cfg)
    groups: dict[Seat, int] = {}
    gid = 0
    grp = {Seat(1, "L", 0), Seat(1, "L", 1), Seat(1, "L", 2)}
    for s in order:
        if s in grp:
            groups[s] = 999
        else:
            groups[s] = gid
            gid += 1
    out = cohesive_order(order, groups)
    assert set(out) == set(order) and len(out) == len(order)
    idx = [i for i, s in enumerate(out) if s in grp]
    assert idx == list(range(idx[0], idx[0] + 3))
    block = out[idx[0]: idx[0] + 3]
    assert [s.col for s in block] == [2, 1, 0]


def test_cohesive_order_unchanged_when_all_singletons():
    cfg = BoardingConfig(rows=3)
    order = all_seats(cfg)
    groups = {s: i for i, s in enumerate(order)}
    assert cohesive_order(order, groups) == order


def test_real_groups_are_contiguous_window_first_in_a_method_order():
    # end-to-end: a real assign_groups output, reordered against a real method order,
    # must place each multi-seat group's members consecutively and window-first
    import random

    from boarding.methods import METHODS

    cfg = BoardingConfig(rows=12)
    groups = assign_groups(cfg, seed=7, group_fraction=0.7)
    order = cohesive_order(METHODS["steffen_perfect"](cfg, random.Random(7)), groups)
    assert set(order) == set(all_seats(cfg)) and len(order) == cfg.total_passengers

    members: dict[int, list[Seat]] = {}
    for s in order:
        members.setdefault(groups[s], []).append(s)
    positions = {s: i for i, s in enumerate(order)}
    for seats in members.values():
        if len(seats) < 2:
            continue
        idx = sorted(positions[s] for s in seats)
        assert idx == list(range(idx[0], idx[0] + len(seats)))  # consecutive in final order
        block = order[idx[0]: idx[0] + len(seats)]
        assert block == sorted(block, key=lambda s: -s.col)  # window-first
