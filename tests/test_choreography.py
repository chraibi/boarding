import random

from boarding.choreography import (
    AgentPlan,
    State,
    luggage_time,
    seat_interference_penalty,
)
from boarding.config import BoardingConfig, Seat


def test_penalty_counts_seated_inboard_neighbors():
    cfg = BoardingConfig()
    window = Seat(5, "L", 2)
    occupied = {Seat(5, "L", 0), Seat(5, "L", 1)}
    assert seat_interference_penalty(window, occupied, cfg) == 2 * cfg.seat_penalty
    assert seat_interference_penalty(Seat(5, "L", 0), occupied, cfg) == 0.0
    assert seat_interference_penalty(window, set(), cfg) == 0.0


def test_luggage_time_matches_mean_within_tolerance():
    cfg = BoardingConfig()
    rng = random.Random(0)
    draws = [luggage_time(cfg, rng) for _ in range(5000)]
    mean = sum(draws) / len(draws)
    assert 6.0 < mean < 8.0
    assert all(d > 0 for d in draws)


class _FakeAgent:
    def __init__(self, x):
        self.position = (x, 0.0)
        self.target = None


def test_plan_walks_arrives_holds_then_seats():
    cfg = BoardingConfig(dt=1.0, arrival_threshold=0.5)
    waypoint = (10.0, 0.0)
    plan = AgentPlan(seat=Seat(1, "L", 0), aisle_waypoint=waypoint)

    far = _FakeAgent(x=0.0)
    assert plan.step(far, iteration=0, arrival_threshold=cfg.arrival_threshold) is False
    assert plan.state is State.WALK_TO_ROW
    assert far.target == waypoint

    # reaching the row signals arrival exactly once; loop owns the hold duration
    at_row = _FakeAgent(x=10.0)
    assert plan.step(at_row, iteration=1, arrival_threshold=cfg.arrival_threshold) is True
    assert plan.state is State.HOLD
    assert at_row.target == waypoint  # keeps targeting the row point while holding

    # before start_hold, a HOLD agent never seats (release is unset)
    assert plan.step(at_row, iteration=999, arrival_threshold=cfg.arrival_threshold) is False
    assert plan.state is State.HOLD

    # run loop starts a 3-iteration hold; released on iteration 1+3 = 4
    plan.start_hold(iteration=1, hold_frames=3)
    plan.step(at_row, iteration=3, arrival_threshold=cfg.arrival_threshold)
    assert plan.state is State.HOLD
    plan.step(at_row, iteration=4, arrival_threshold=cfg.arrival_threshold)
    assert plan.state is State.SEATED


def test_seated_step_is_noop():
    plan = AgentPlan(seat=Seat(1, "L", 0), aisle_waypoint=(10.0, 0.0))
    plan.state = State.SEATED
    a = _FakeAgent(x=5.0)
    assert plan.step(a, iteration=99, arrival_threshold=0.5) is False
    assert plan.state is State.SEATED
    assert a.target is None  # no steering once seated
