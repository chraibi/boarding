from boarding.config import BoardingConfig
from boarding.visualize import capture


def test_capture_samples_until_everyone_is_seated():
    cfg = BoardingConfig(rows=3, spawn_headway=1.0, max_sim_seconds=900.0)
    samples, total = capture("random", seed=0, cfg=cfg, sample_every_s=1.0)
    assert total > 0
    assert len(samples) >= 2
    # each sample is (time, aisle_positions, filled_seat_coords)
    t, aisle, filled = samples[-1]
    assert t == total
    assert len(filled) == cfg.total_passengers  # final frame: all seated
    assert aisle == []  # no one left in the aisle at the end
