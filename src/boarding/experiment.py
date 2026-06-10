import random
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import jupedsim as jps
import pandas as pd

from .choreography import AgentPlan, State, luggage_time, seat_interference_penalty
from .config import BoardingConfig, Seat
from .geometry import build_fuselage
from .methods import METHODS, all_seats


@dataclass
class BoardingResult:
    method: str
    seed: int
    total_time: float
    seated_count: int
    seat_times: dict[Seat, float]
    sqlite_path: Path


def draw_luggage(cfg: BoardingConfig, seed: int) -> dict[Seat, float]:
    """Luggage-stow time per seat, in canonical seat order from a dedicated RNG.

    Keyed by seat (not boarding order) and independent of the boarding method, so a
    given seed yields identical per-seat luggage across all methods — true paired
    (common-random-number) replication.
    """
    rng = random.Random(seed)
    return {seat: luggage_time(cfg, rng) for seat in all_seats(cfg)}


def _build_simulation(cfg: BoardingConfig, walkable, out_path: Path):
    model = jps.CollisionFreeSpeedModel()
    writer = jps.SqliteTrajectoryWriter(
        output_file=out_path, every_nth_frame=max(1, round(0.1 / cfg.dt))
    )
    sim = jps.Simulation(
        model=model, geometry=walkable, dt=cfg.dt, trajectory_writer=writer
    )
    return sim, writer


def _door_is_clear(sim, plans, door, clearance) -> bool:
    c2 = clearance * clearance
    for agent_id in plans:
        px, py = sim.agent(agent_id).position
        if (px - door[0]) ** 2 + (py - door[1]) ** 2 < c2:
            return False
    return True


def run_boarding(
    method: str, seed: int, config: BoardingConfig | None = None
) -> BoardingResult:
    cfg = config or BoardingConfig()
    walkable, seat_map, door = build_fuselage(cfg)
    order = METHODS[method](cfg, random.Random(seed))
    luggage = draw_luggage(cfg, seed)  # paired across methods, independent of order

    out_path = Path(tempfile.mkdtemp(prefix="boarding_")) / f"{method}_{seed}.sqlite"
    sim, writer = _build_simulation(cfg, walkable, out_path)
    direct = sim.add_direct_steering_stage()
    journey = sim.add_journey(jps.JourneyDescription([direct]))
    params = jps.CollisionFreeSpeedModelAgentParameters(
        position=door, desired_speed=cfg.v0, radius=cfg.agent_radius,
        journey_id=journey, stage_id=direct,
    )

    plans: dict[int, AgentPlan] = {}
    queue = list(order)
    occupied: set[Seat] = set()
    seat_times: dict[Seat, float] = {}

    headway_frames = max(1, round(cfg.spawn_headway / cfg.dt))
    max_iter = round(cfg.max_sim_seconds / cfg.dt)
    clearance = 2.0 * cfg.agent_radius

    iteration = 0
    next_spawn = 0
    while len(seat_times) < cfg.total_passengers and iteration < max_iter:
        if queue and iteration >= next_spawn and _door_is_clear(sim, plans, door, clearance):
            seat = queue[0]
            try:
                agent_id = sim.add_agent(params)
            except Exception:
                agent_id = None
            if agent_id is not None:
                geom = seat_map[seat]
                plans[agent_id] = AgentPlan(seat, geom.aisle_waypoint)
                queue.pop(0)
                next_spawn = iteration + headway_frames

        seated_now: list[int] = []
        for agent_id, plan in plans.items():
            agent = sim.agent(agent_id)
            if plan.step(agent, iteration, cfg.arrival_threshold):
                # arrived at the row: compute the hold from live occupancy and start it
                hold_s = luggage[plan.seat] + seat_interference_penalty(
                    plan.seat, occupied, cfg
                )
                plan.start_hold(iteration, round(hold_s / cfg.dt))
            elif plan.state is State.SEATED:
                occupied.add(plan.seat)
                seat_times[plan.seat] = iteration * cfg.dt
                seated_now.append(agent_id)

        for agent_id in seated_now:
            sim.mark_agent_for_removal(agent_id)
            del plans[agent_id]

        sim.iterate()
        iteration += 1

    writer.close()
    seated_count = len(seat_times)
    if seated_count < cfg.total_passengers:
        raise RuntimeError(
            f"boarding did not complete: {seated_count}/{cfg.total_passengers} seated "
            f"within {cfg.max_sim_seconds}s ({method}, seed {seed}). "
            "Increase max_sim_seconds — a partial run would corrupt the method mean."
        )
    return BoardingResult(
        method=method, seed=seed, total_time=iteration * cfg.dt,
        seated_count=seated_count, seat_times=seat_times, sqlite_path=out_path,
    )


def sweep(
    methods: Sequence[str],
    seeds: Sequence[int],
    config: BoardingConfig | None = None,
) -> pd.DataFrame:
    """Run every (method, seed) pair; seeds are paired across methods."""
    rows = []
    for seed in seeds:
        for method in methods:
            res = run_boarding(method, seed, config)
            rows.append(
                {
                    "method": method,
                    "seed": seed,
                    "total_time": res.total_time,
                    "seated_count": res.seated_count,
                    "sqlite_path": str(res.sqlite_path),
                }
            )
    return pd.DataFrame(rows)
