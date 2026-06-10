from pathlib import Path

import pandas as pd


def ranking_table(df: pd.DataFrame) -> pd.DataFrame:
    """Mean/std boarding time per method, fastest first."""
    grouped = (
        df.groupby("method")["total_time"]
        .agg(mean_time="mean", std_time="std", n="count")
        .reset_index()
        .sort_values("mean_time")
        .reset_index(drop=True)
    )
    grouped["std_time"] = grouped["std_time"].fillna(0.0)
    return grouped


def boxplot_by_method(df: pd.DataFrame, out_path: Path) -> Path:
    """Box plot of total boarding time per method; saves a PNG."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    order = ranking_table(df)["method"].tolist()
    data = [df.loc[df["method"] == m, "total_time"].to_numpy() for m in order]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(data, tick_labels=order, orientation="vertical")
    ax.set_ylabel("Boarding time (s)")
    ax.set_title("Boarding time by method")
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
