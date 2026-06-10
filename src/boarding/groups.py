import random

from .config import BoardingConfig, Seat
from .methods import all_seats

_GROUP_SIZES = (2, 3)
_GROUP_SIZE_WEIGHTS = (0.5, 0.5)


def assign_groups(
    cfg: BoardingConfig, seed: int, group_fraction: float
) -> dict[Seat, int]:
    """Assign a group id to every seat. Members of a real group (size >= 2) share an id
    and sit in adjacent window-out seats of one bench (row+side). Solo passengers get a
    unique id. Seeded and method-independent (paired across methods)."""
    rng = random.Random(seed)
    benches: dict[tuple[int, str], list[Seat]] = {}
    for seat in all_seats(cfg):
        benches.setdefault((seat.row, seat.side), []).append(seat)
    for bench in benches.values():
        bench.sort(key=lambda s: -s.col)  # window (highest col) first

    bench_keys = list(benches.keys())
    rng.shuffle(bench_keys)
    target = round(group_fraction * cfg.total_passengers)

    group_id: dict[Seat, int] = {}
    next_id = 0
    grouped = 0
    for key in bench_keys:
        bench = benches[key]
        if grouped < target:
            size = min(rng.choices(_GROUP_SIZES, weights=_GROUP_SIZE_WEIGHTS, k=1)[0], len(bench))
            for seat in bench[:size]:
                group_id[seat] = next_id
            next_id += 1
            grouped += size
            for seat in bench[size:]:
                group_id[seat] = next_id
                next_id += 1
        else:
            for seat in bench:
                group_id[seat] = next_id
                next_id += 1
    return group_id


def cohesive_order(method_order: list[Seat], groups: dict[Seat, int]) -> list[Seat]:
    """Reorder so each group's members board consecutively, window-first, anchored at the
    group's earliest position in method_order. Solo seats stay in place. Returns a
    permutation of method_order; an all-singleton mapping returns it unchanged."""
    members: dict[int, list[Seat]] = {}
    for seat in method_order:
        members.setdefault(groups[seat], []).append(seat)
    for seats in members.values():
        seats.sort(key=lambda s: -s.col)

    out: list[Seat] = []
    emitted: set[int] = set()
    for seat in method_order:
        gid = groups[seat]
        if gid in emitted:
            continue
        out.extend(members[gid])
        emitted.add(gid)
    return out
