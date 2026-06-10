
from boarding.config import BoardingConfig
from boarding.experiment import run_boarding
from boarding.geometry import build_fuselage
from boarding.seat_placement import seat_fill_table


def test_seat_fill_table_one_row_per_passenger_sorted_by_time():
    cfg = BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=900.0)
    _walkable, seat_map, _door = build_fuselage(cfg)
    result = run_boarding("random", seed=0, config=cfg)

    table = seat_fill_table(result, seat_map)

    assert set(table.columns) >= {"row", "side", "col", "x", "y", "seat_time"}
    assert len(table) == cfg.total_passengers
    # sorted ascending by seat_time
    times = list(table["seat_time"])
    assert times == sorted(times)
    # coordinates match the seat_map for the first row
    first = table.iloc[0]
    from boarding.config import Seat
    seat = Seat(int(first["row"]), str(first["side"]), int(first["col"]))
    assert (first["x"], first["y"]) == seat_map[seat].seat_coord


def test_seat_fill_table_matches_seat_times_exactly():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    _walkable, seat_map, _door = build_fuselage(cfg)
    result = run_boarding("steffen_perfect", seed=1, config=cfg)
    table = seat_fill_table(result, seat_map)
    # every seat_time in the table appears in result.seat_times
    assert sorted(table["seat_time"]) == sorted(result.seat_times.values())
