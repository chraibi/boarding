import jupedsim as jps
from shapely import Point

from boarding.config import BoardingConfig, Seat
from boarding.geometry import build_fuselage


def test_seat_map_has_every_seat():
    cfg = BoardingConfig(rows=4)
    _walkable, seat_map, _door = build_fuselage(cfg)
    assert len(seat_map) == 4 * 3 * 2
    assert Seat(1, "L", 2) in seat_map


def test_door_and_aisle_waypoints_inside_walkable():
    cfg = BoardingConfig(rows=4)
    walkable, seat_map, door = build_fuselage(cfg)
    assert walkable.contains(Point(*door))
    for geom in seat_map.values():
        assert walkable.contains(Point(*geom.aisle_waypoint))


def test_seat_coords_are_off_the_aisle():
    cfg = BoardingConfig(rows=4)
    walkable, seat_map, _door = build_fuselage(cfg)
    # seats are outside the walkable aisle (they are visual labels, not navigated)
    for geom in seat_map.values():
        assert not walkable.contains(Point(*geom.seat_coord))


def test_door_and_row_points_are_routable():
    cfg = BoardingConfig(rows=4)
    walkable, seat_map, door = build_fuselage(cfg)
    engine = jps.RoutingEngine(walkable)
    assert engine.is_routable(door)
    for geom in seat_map.values():
        assert engine.is_routable(geom.aisle_waypoint)


def test_window_coord_is_farther_from_aisle_than_aisle_seat():
    cfg = BoardingConfig(rows=4)
    _walkable, seat_map, _door = build_fuselage(cfg)
    window_y = abs(seat_map[Seat(2, "L", 2)].seat_coord[1])
    aisle_y = abs(seat_map[Seat(2, "L", 0)].seat_coord[1])
    assert window_y > aisle_y
