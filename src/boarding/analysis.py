from pathlib import Path

import pandas as pd

# Fixed method order (homogeneous fastest-first) and shared y-limits so every study's
# plot uses the same x-axis order and the same y-scale — directly comparable by eye.
CANONICAL_ORDER = (
    "steffen_perfect",
    "steffen_modified",
    "wilma",
    "back_to_front",
    "random",
    "front_to_back",
)
COMPARISON_YLIM = (340.0, 730.0)


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


def boxplot_by_method(
    df: pd.DataFrame,
    out_path: Path,
    order: tuple[str, ...] | list[str] | None = None,
    ylim: tuple[float, float] | None = None,
    title: str | None = None,
) -> Path:
    """Box plot of total boarding time per method; saves a PNG.

    order: fixed method order for the x-axis (defaults to fastest-first for this df).
    ylim: fixed y-limits. Pass CANONICAL_ORDER + COMPARISON_YLIM for cross-study plots.
    title: figure title — pass the scenario name (e.g. "Realistic passenger mix").
        The compared quantity and methods already live in the y-label and x-ticks.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    present = set(df["method"])
    if order is None:
        seq = ranking_table(df)["method"].tolist()
    else:
        seq = [m for m in order if m in present]
    data = [df.loc[df["method"] == m, "total_time"].to_numpy() for m in seq]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.boxplot(data, tick_labels=seq, orientation="vertical")
    ax.set_ylabel("Boarding time (s)")
    ax.set_title(title if title is not None else "Boarding time by method")
    ax.tick_params(axis="x", rotation=30)
    if ylim is not None:
        ax.set_ylim(*ylim)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path
