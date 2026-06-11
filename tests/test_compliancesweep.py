import pandas as pd

from boarding.compliancesweep import compliance_plot, sweep_compliance
from boarding.config import BoardingConfig


def test_sweep_compliance_shape():
    cfg = BoardingConfig(rows=2, spawn_headway=1.0)
    df = sweep_compliance(
        ["random", "steffen_perfect"], rates=[1.0, 0.5], seeds=[0], config=cfg
    )
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"method", "compliance_rate", "seed", "total_time"}
    assert len(df) == 2 * 2 * 1


def test_compliance_plot_writes_png(tmp_path):
    df = pd.DataFrame(
        [
            {"method": "random", "compliance_rate": 1.0, "seed": 0, "total_time": 10.0},
            {"method": "random", "compliance_rate": 0.0, "seed": 0, "total_time": 11.0},
            {"method": "steffen_perfect", "compliance_rate": 1.0, "seed": 0, "total_time": 8.0},
            {"method": "steffen_perfect", "compliance_rate": 0.0, "seed": 0, "total_time": 11.0},
        ]
    )
    out = compliance_plot(df, tmp_path / "c.png")
    assert out.exists()
