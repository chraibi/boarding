from dataclasses import dataclass

from shapely import Polygon, box

from .config import BoardingConfig, Seat


@dataclass(frozen=True)
class SeatGeom:
    aisle_waypoint: tuple[float, float]  # on-aisle point at this row (walk-to / hold point)
    seat_coord: tuple[float, float]      # seat's physical coordinate, off the aisle (viz only)


def _row_x(cfg: BoardingConfig, row: int) -> float:
    """Longitudinal centre of a row; row 1 is nearest the door."""
    return cfg.door_depth + (row - 0.5) * cfg.seat_pitch


def build_fuselage(cfg: BoardingConfig) -> tuple[Polygon, dict[Seat, SeatGeom], tuple[float, float]]:
    """Build (walkable_aisle, seat_map, door_point).

    Logical seating: walkable is a single rectangular aisle from the door past the last
    row. Agents walk the aisle to their row point, hold, then are removed (sit logically).
    seat_coord is off-aisle and used only for the post-hoc seat-fill visual.
    """
    half_aisle = cfg.aisle_width / 2.0
    # extend one pitch past the last row so the rear row point sits inside the aisle
    cabin_len = cfg.door_depth + cfg.rows * cfg.seat_pitch + cfg.seat_pitch
    walkable = box(0.0, -half_aisle, cabin_len, half_aisle)

    seat_map: dict[Seat, SeatGeom] = {}
    side_sign = {"L": -1.0, "R": 1.0}
    for row in range(1, cfg.rows + 1):
        cx = _row_x(cfg, row)
        for side, sign in side_sign.items():
            for col in range(cfg.seats_per_side):
                seat_y = sign * (half_aisle + (col + 0.5) * cfg.seat_width)
                seat_map[Seat(row, side, col)] = SeatGeom(
                    aisle_waypoint=(cx, 0.0),
                    seat_coord=(cx, seat_y),
                )

    door_point = (cfg.door_depth * 0.25, 0.0)
    return walkable, seat_map, door_point
