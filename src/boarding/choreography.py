import enum
import math
import random

from jupedsim_scenarios.direct_steering_runtime import (
    assign_agent_target,
    extract_agent_xy,
)

from .config import BoardingConfig, Seat


class State(enum.Enum):
    WALK_TO_ROW = enum.auto()
    HOLD = enum.auto()
    SEATED = enum.auto()


def seat_interference_penalty(
    seat: Seat, occupied: set[Seat], cfg: BoardingConfig
) -> float:
    """5 s per already-seated neighbor between this seat and the aisle."""
    blockers = sum(
        1 for col in seat.inboard_cols if Seat(seat.row, seat.side, col) in occupied
    )
    return blockers * cfg.seat_penalty


def luggage_time(cfg: BoardingConfig, rng: random.Random) -> float:
    """Gamma draw with the configured mean and std-dev (shape=k, scale=theta)."""
    if cfg.luggage_sd <= 0:
        return cfg.luggage_mean
    k = (cfg.luggage_mean / cfg.luggage_sd) ** 2
    theta = (cfg.luggage_sd ** 2) / cfg.luggage_mean
    return rng.gammavariate(k, theta)


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class AgentPlan:
    """Per-agent boarding state machine driven once per simulation frame.

    Logical seating: the agent walks to its row's on-aisle point and holds there.
    The hold duration (luggage + interference) depends on live seat occupancy, so the
    run loop owns it: ``step`` reports arrival, the loop computes the duration and calls
    ``start_hold``. When the hold expires the agent becomes SEATED and the loop removes
    it (sitting is logical, not navigated).
    """

    def __init__(self, seat: Seat, aisle_waypoint: tuple[float, float]) -> None:
        self.seat = seat
        self.aisle_waypoint = aisle_waypoint
        self.state = State.WALK_TO_ROW
        self.release_iter: int | None = None

    def step(self, agent, iteration: int, arrival_threshold: float) -> bool:
        """Drive one frame. Returns True only on the frame the agent reaches its row;
        the run loop must then call ``start_hold`` with the computed duration."""
        if self.state is State.SEATED:
            return False
        # always steer toward the row point; in HOLD this lets a shoved agent self-correct
        assign_agent_target(agent, self.aisle_waypoint)
        if self.state is State.WALK_TO_ROW:
            pos = extract_agent_xy(agent)
            if _dist(pos, self.aisle_waypoint) <= arrival_threshold:
                self.state = State.HOLD  # awaiting start_hold from the run loop
                return True
            return False
        if self.state is State.HOLD and self.release_iter is not None:
            if iteration >= self.release_iter:
                self.state = State.SEATED
        return False

    def start_hold(self, iteration: int, hold_frames: int) -> None:
        """Begin the row hold; the agent seats ``hold_frames`` (≥1) iterations later."""
        self.release_iter = iteration + max(1, hold_frames)
