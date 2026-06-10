import pandas as pd

from boarding.config import BoardingConfig
from boarding.groupsweep import erosion_plot, sweep_group_fraction


def test_sweep_group_fraction_shape():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    df = sweep_group_fraction(
        ["random", "steffen_perfect"], fractions=[0.0, 0.5], seeds=[0], config=cfg
    )
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"method", "group_fraction", "seed", "total_time"}
    assert len(df) == 2 * 2 * 1


def test_erosion_plot_writes_png(tmp_path):
    df = pd.DataFrame(
        [
            {"method": "a", "group_fraction": 0.0, "seed": 0, "total_time": 10.0},
            {"method": "a", "group_fraction": 0.5, "seed": 0, "total_time": 14.0},
            {"method": "b", "group_fraction": 0.0, "seed": 0, "total_time": 12.0},
            {"method": "b", "group_fraction": 0.5, "seed": 0, "total_time": 13.0},
        ]
    )
    out = erosion_plot(df, tmp_path / "e.png")
    assert out.exists()
