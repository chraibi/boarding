import pandas as pd

from boarding.analysis import ranking_table


def test_ranking_table_sorts_fastest_first():
    df = pd.DataFrame(
        [
            {"method": "slow", "seed": 0, "total_time": 100.0},
            {"method": "slow", "seed": 1, "total_time": 120.0},
            {"method": "fast", "seed": 0, "total_time": 40.0},
            {"method": "fast", "seed": 1, "total_time": 50.0},
        ]
    )
    table = ranking_table(df)
    assert list(table["method"]) == ["fast", "slow"]
    assert table.iloc[0]["mean_time"] == 45.0
    assert {"mean_time", "std_time", "n"} <= set(table.columns)


def test_boxplot_writes_png(tmp_path):
    from boarding.analysis import boxplot_by_method

    df = pd.DataFrame(
        [
            {"method": "a", "seed": 0, "total_time": 10.0},
            {"method": "a", "seed": 1, "total_time": 12.0},
            {"method": "b", "seed": 0, "total_time": 20.0},
        ]
    )
    out = boxplot_by_method(df, tmp_path / "p.png")
    assert out.exists()
