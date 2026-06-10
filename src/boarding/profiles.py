import random
from dataclasses import dataclass

from .config import BoardingConfig, Seat
from .methods import all_seats


@dataclass(frozen=True)
class Profile:
    name: str
    weight: float            # relative mix fraction
    walk_speed_factor: float  # x cfg.v0
    stow_mean: float         # s, luggage-stow gamma mean
    stow_sd: float           # s
    mobility_factor: float   # x seat-interference penalty


@dataclass(frozen=True)
class PassengerParams:
    profile_name: str
    speed_factor: float
    stow_time: float
    mobility_factor: float


# Illustrative realistic mix (see docs/heterogeneous-profiles-design.md); weights sum to 1.
DEFAULT_MIX: tuple[Profile, ...] = (
    Profile("standard", 0.45, 1.00, 7.0, 3.0, 1.0),
    Profile("business_young", 0.15, 1.15, 2.0, 1.0, 0.9),
    Profile("heavy_luggage", 0.15, 0.95, 14.0, 5.0, 1.2),
    Profile("elderly", 0.15, 0.60, 10.0, 4.0, 1.8),
    Profile("family_with_kids", 0.10, 0.70, 16.0, 6.0, 2.0),
)


def _stow_draw(profile: Profile, rng: random.Random) -> float:
    if profile.stow_sd <= 0:
        return profile.stow_mean
    k = (profile.stow_mean / profile.stow_sd) ** 2
    theta = (profile.stow_sd ** 2) / profile.stow_mean
    return rng.gammavariate(k, theta)


def draw_passengers(
    cfg: BoardingConfig, seed: int, mix: tuple[Profile, ...]
) -> dict[Seat, PassengerParams]:
    """Assign a profile + stow time to each seat's occupant.

    Iterates seats in canonical all_seats order from a dedicated RNG, so a seed gives the
    same occupant at each seat regardless of boarding method (paired replication).
    """
    rng = random.Random(seed)
    weights = [p.weight for p in mix]
    out: dict[Seat, PassengerParams] = {}
    for seat in all_seats(cfg):
        profile = rng.choices(mix, weights=weights, k=1)[0]
        out[seat] = PassengerParams(
            profile_name=profile.name,
            speed_factor=profile.walk_speed_factor,
            stow_time=_stow_draw(profile, rng),
            mobility_factor=profile.mobility_factor,
        )
    return out
