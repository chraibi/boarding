import random

from .config import Seat


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
    canonical = sorted(order, key=lambda s: (s.row, s.side, s.col))
    noncompliant = set(rng.sample(canonical, n))
    compliant = [s for s in order if s not in noncompliant]
    displaced = [s for s in canonical if s in noncompliant]
    rng.shuffle(displaced)
    result = list(compliant)
    for seat in displaced:
        result.insert(rng.randint(0, len(result)), seat)
    return result
