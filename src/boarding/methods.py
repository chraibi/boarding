import random
from collections.abc import Callable

from .config import BoardingConfig, Seat

WINDOW_FIRST = (2, 1, 0)  # col order: window, middle, aisle


def all_seats(cfg: BoardingConfig) -> list[Seat]:
    return [
        Seat(row, side, col)
        for row in range(1, cfg.rows + 1)
        for side in ("L", "R")
        for col in range(cfg.seats_per_side)
    ]


def _shuffled(seats: list[Seat], rng: random.Random) -> list[Seat]:
    out = list(seats)
    rng.shuffle(out)
    return out


def random_order(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    return _shuffled(all_seats(cfg), rng)


def _blocks(cfg: BoardingConfig, block_rows: int) -> list[list[int]]:
    rows = list(range(1, cfg.rows + 1))
    return [rows[i : i + block_rows] for i in range(0, len(rows), block_rows)]


def back_to_front(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    block_rows = max(1, cfg.rows // 6)
    order: list[Seat] = []
    for block in reversed(_blocks(cfg, block_rows)):
        in_block = [s for s in all_seats(cfg) if s.row in block]
        order.extend(_shuffled(in_block, rng))
    return order


def front_to_back(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    block_rows = max(1, cfg.rows // 6)
    order: list[Seat] = []
    for block in _blocks(cfg, block_rows):
        in_block = [s for s in all_seats(cfg) if s.row in block]
        order.extend(_shuffled(in_block, rng))
    return order


def wilma(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    order: list[Seat] = []
    for col in WINDOW_FIRST:
        wave = [s for s in all_seats(cfg) if s.col == col]
        rng.shuffle(wave)
        order.extend(wave)
    return order


def steffen_perfect(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    order: list[Seat] = []
    for col in WINDOW_FIRST:
        for side in ("L", "R"):
            for parity in (0, 1):
                rows = [
                    r
                    for r in range(cfg.rows, 0, -1)
                    if (cfg.rows - r) % 2 == parity
                ]
                order.extend(Seat(r, side, col) for r in rows)
    return order


def steffen_modified(cfg: BoardingConfig, rng: random.Random) -> list[Seat]:
    order: list[Seat] = []
    for side in ("L", "R"):
        for parity in (0, 1):
            rows = [r for r in range(cfg.rows, 0, -1) if (cfg.rows - r) % 2 == parity]
            group = [Seat(r, side, col) for r in rows for col in WINDOW_FIRST]
            order.extend(group)
    return order


METHODS: dict[str, Callable[[BoardingConfig, random.Random], list[Seat]]] = {
    "random": random_order,
    "back_to_front": back_to_front,
    "front_to_back": front_to_back,
    "wilma": wilma,
    "steffen_perfect": steffen_perfect,
    "steffen_modified": steffen_modified,
}
