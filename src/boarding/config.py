from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .profiles import Profile


@dataclass(frozen=True)
class Seat:
    """A seat addressed by 1-based row, side ('L'/'R'), and column.

    col: 0 = aisle-adjacent, increasing outward; (seats_per_side-1) = window.
    """

    row: int
    side: str
    col: int

    @property
    def inboard_cols(self) -> tuple[int, ...]:
        """Columns between this seat and the aisle (smaller col, same row+side)."""
        return tuple(range(self.col))


@dataclass(frozen=True)
class BoardingConfig:
    # cabin
    rows: int = 30
    seats_per_side: int = 3
    seat_pitch: float = 0.8        # m, longitudinal row spacing (x)
    seat_width: float = 0.45       # m, lateral width per seat (y)
    seat_block_x: float = 0.45     # m, walkable lateral-slot depth per row (< pitch leaves gaps)
    aisle_width: float = 0.5       # m
    door_depth: float = 1.2        # m, entry corridor length ahead of row 1
    # penalties (Steffen)
    luggage_mean: float = 7.0      # s, gamma mean
    luggage_sd: float = 3.0        # s, gamma std-dev
    seat_penalty: float = 5.0      # s per displaced inboard neighbor
    # dynamics
    dt: float = 0.05               # s
    v0: float = 1.2                # m/s desired speed
    agent_radius: float = 0.18     # m
    arrival_threshold: float = 0.45  # m, "reached row" distance
    spawn_headway: float = 2.0     # s between consecutive boardings at the door
    max_sim_seconds: float = 3600.0
    # heterogeneity: None = homogeneous (baseline); a tuple of Profile enables a mix
    profile_mix: "tuple[Profile, ...] | None" = None
    # travel groups: 0.0 = no groups (baseline); fraction of passengers boarding cohesively
    group_fraction: float = 0.0

    @property
    def total_passengers(self) -> int:
        return self.rows * self.seats_per_side * 2
