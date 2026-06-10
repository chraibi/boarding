from boarding.config import BoardingConfig, Seat


def test_default_config_is_180_passengers():
    cfg = BoardingConfig()
    assert cfg.rows == 30
    assert cfg.seats_per_side == 3
    assert cfg.total_passengers == 180


def test_seat_inboard_cols_window_has_two():
    window = Seat(row=5, side="L", col=2)
    assert window.inboard_cols == (0, 1)
    aisle = Seat(row=5, side="L", col=0)
    assert aisle.inboard_cols == ()


def test_seat_is_hashable_and_value_equal():
    assert Seat(1, "R", 0) == Seat(1, "R", 0)
    assert len({Seat(1, "R", 0), Seat(1, "R", 0)}) == 1


def test_profile_mix_defaults_to_none():
    from boarding.config import BoardingConfig
    assert BoardingConfig().profile_mix is None


def test_profile_mix_can_be_set():
    from boarding.config import BoardingConfig
    from boarding.profiles import DEFAULT_MIX
    cfg = BoardingConfig(profile_mix=DEFAULT_MIX)
    assert cfg.profile_mix is DEFAULT_MIX


def test_group_fraction_defaults_to_zero():
    from boarding.config import BoardingConfig
    assert BoardingConfig().group_fraction == 0.0


def test_group_fraction_can_be_set():
    from boarding.config import BoardingConfig
    assert BoardingConfig(group_fraction=0.5).group_fraction == 0.5
