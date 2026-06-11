import random

from .config import Seat


def _canonical(order: list[Seat]) -> list[Seat]:
    return sorted(order, key=lambda s: (s.row, s.side, s.col))


def noncompliant_seats(order: list[Seat], rate: float, seed: int) -> set[Seat]:
    """The set of non-compliant passengers for ``(rate, seed)``.

    Selected from a canonical seat ordering, so the set depends only on the seat set, the
    rate, and the seed — never on the boarding method. This is the paired-replication
    guarantee: at a given seed/rate the same passengers are non-compliant for every method.
    """
    n = round((1.0 - rate) * len(order))
    if n <= 0:
        return set()
    return set(random.Random(seed).sample(_canonical(order), n))


def apply_compliance(order: list[Seat], rate: float, seed: int) -> list[Seat]:
    """Perturb a boarding order by non-compliant passengers.

    ``n = round((1 - rate) * len(order))`` passengers are chosen non-compliant from a
    canonical seat ordering (so the same passengers are non-compliant for a given seed,
    independent of method — paired). They are removed from ``order`` (compliant passengers
    keep their relative order) and reinserted at uniformly random positions. Returns a
    permutation of ``order``. rate=1.0 -> unchanged; rate=0.0 -> a method-independent
    random permutation (depends only on the seat set + seed).
    """
    n = round((1.0 - rate) * len(order))
    if n <= 0:
        return list(order)
    rng = random.Random(seed)
    canonical = _canonical(order)
    noncompliant = set(rng.sample(canonical, n))
    compliant = [s for s in order if s not in noncompliant]
    displaced = [s for s in canonical if s in noncompliant]
    rng.shuffle(displaced)
    result = list(compliant)
    for seat in displaced:
        result.insert(rng.randint(0, len(result)), seat)
    return result
