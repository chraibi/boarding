import pandas as pd

from .config import Seat
from .experiment import BoardingResult
from .geometry import SeatGeom


def seat_fill_table(
    result: BoardingResult, seat_map: dict[Seat, SeatGeom]
) -> pd.DataFrame:
    """One row per seated passenger: physical seat coordinate + fill time.

    Drives the post-hoc 'seats filling' animation; the study's numbers never
    depend on this. Sorted ascending by seat_time (boarding order in time).
    """
    rows = []
    for seat, t in result.seat_times.items():
        x, y = seat_map[seat].seat_coord
        rows.append(
            {
                "row": seat.row,
                "side": seat.side,
                "col": seat.col,
                "x": x,
                "y": y,
                "seat_time": t,
            }
        )
    table = pd.DataFrame(rows)
    return table.sort_values("seat_time").reset_index(drop=True)
