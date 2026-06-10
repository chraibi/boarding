import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .analysis import CANONICAL_ORDER, COMPARISON_YLIM
from .config import BoardingConfig
from .experiment import run_boarding
from .methods import METHODS


def sweep_group_fraction(
    methods: Sequence[str],
    fractions: Sequence[float],
    seeds: Sequence[int],
    config: BoardingConfig | None = None,
) -> pd.DataFrame:
    """Run every (method, fraction, seed); seeds paired across methods and fractions."""
    base = config or BoardingConfig()
    rows = []
    for fraction in fractions:
        cfg = replace(base, group_fraction=fraction)
        for seed in seeds:
            for method in methods:
                res = run_boarding(method, seed, cfg)
                rows.append(
                    {
                        "method": method,
                        "group_fraction": fraction,
                        "seed": seed,
                        "total_time": res.total_time,
                    }
                )
    return pd.DataFrame(rows)


def erosion_plot(df: pd.DataFrame, out_path: Path) -> Path:
    """Mean boarding time vs group fraction, one line per method."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    present = set(df["method"])
    methods = [m for m in CANONICAL_ORDER if m in present]
    fig, ax = plt.subplots(figsize=(9, 6))
    for method in methods:
        sub = df[df["method"] == method].groupby("group_fraction")["total_time"].mean()
        ax.plot(sub.index, sub.to_numpy(), marker="o", label=method)
    ax.set_xlabel("group fraction")
    ax.set_ylabel("mean boarding time (s)")
    ax.set_ylim(*COMPARISON_YLIM)
    ax.set_title("Window-first group cohesion")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Group-fraction sensitivity sweep.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--fractions", nargs="+", type=float, default=[0.0, 0.2, 0.4, 0.6, 0.8])
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("study-output"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df = sweep_group_fraction(
        args.methods, args.fractions, list(range(args.seeds)), config=cfg
    )
    df.to_csv(args.out / "group_sweep.csv", index=False)
    erosion_plot(df, args.out / "group_erosion.png")
    pivot = df.groupby(["group_fraction", "method"])["total_time"].mean().unstack()
    print(pivot.to_string())


if __name__ == "__main__":
    main()
