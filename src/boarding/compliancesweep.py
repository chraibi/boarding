import argparse
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pandas as pd

from .analysis import CANONICAL_ORDER, COMPARISON_YLIM
from .config import BoardingConfig
from .experiment import run_boarding
from .methods import METHODS


def sweep_compliance(
    methods: Sequence[str],
    rates: Sequence[float],
    seeds: Sequence[int],
    config: BoardingConfig | None = None,
) -> pd.DataFrame:
    """Run every (method, rate, seed); seeds paired across methods and rates."""
    base = config or BoardingConfig()
    rows = []
    for rate in rates:
        cfg = replace(base, compliance_rate=rate)
        for seed in seeds:
            for method in methods:
                res = run_boarding(method, seed, cfg)
                rows.append(
                    {
                        "method": method,
                        "compliance_rate": rate,
                        "seed": seed,
                        "total_time": res.total_time,
                    }
                )
    return pd.DataFrame(rows)


def compliance_plot(df: pd.DataFrame, out_path: Path) -> Path:
    """Mean boarding time vs compliance rate, one line per method (x inverted: 100% -> 0%)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    present = set(df["method"])
    methods = [m for m in CANONICAL_ORDER if m in present]
    fig, ax = plt.subplots(figsize=(9, 6))
    for method in methods:
        sub = df[df["method"] == method].groupby("compliance_rate")["total_time"].mean()
        ax.plot(sub.index, sub.to_numpy(), marker="o", label=method)
    ax.set_xlabel("compliance rate")
    ax.set_ylabel("mean boarding time (s)")
    ax.set_ylim(*COMPARISON_YLIM)
    ax.invert_xaxis()  # 100% -> 0% left to right, matching the paper
    ax.set_title("Boarding time vs compliance rate")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compliance-rate sensitivity sweep.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--rates", nargs="+", type=float, default=[1.0, 0.75, 0.5, 0.25, 0.0])
    p.add_argument("--seeds", type=int, default=20)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("study-output"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df = sweep_compliance(
        args.methods, args.rates, list(range(args.seeds)), config=cfg
    )
    df.to_csv(args.out / "compliance_sweep.csv", index=False)
    compliance_plot(df, args.out / "compliance_erosion.png")
    pivot = df.groupby(["compliance_rate", "method"])["total_time"].mean().unstack()
    print(pivot.to_string())


if __name__ == "__main__":
    main()
