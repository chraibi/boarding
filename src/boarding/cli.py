import argparse
import shutil
from pathlib import Path

from .analysis import CANONICAL_ORDER, COMPARISON_YLIM, boxplot_by_method, ranking_table
from .config import BoardingConfig
from .experiment import run_boarding, sweep
from .methods import METHODS
from .profiles import DEFAULT_MIX


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Steffen airplane boarding-method study.")
    p.add_argument(
        "--methods", nargs="+", default=list(METHODS), choices=list(METHODS)
    )
    p.add_argument("--seeds", type=int, default=20, help="number of paired seeds")
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("boarding_out"))
    p.add_argument(
        "--trajectories",
        type=int,
        default=None,
        metavar="SEED",
        help="also save one SQLite trajectory per method at this seed "
        "(under <out>/trajectories/, for jpsvis / the web app)",
    )
    p.add_argument(
        "--mix",
        action="store_true",
        help="run under the default realistic passenger mix (writes *_mix files)",
    )
    return p


def _save_trajectories(methods, seed: int, cfg: BoardingConfig, out: Path) -> None:
    traj_dir = out / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    for method in methods:
        result = run_boarding(method, seed, config=cfg)
        shutil.copy(result.sqlite_path, traj_dir / f"{method}.sqlite")
    print(f"saved {len(methods)} trajectories to {traj_dir} (seed {seed})")


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(
        rows=args.rows, profile_mix=DEFAULT_MIX if args.mix else None
    )
    args.out.mkdir(parents=True, exist_ok=True)
    suffix = "_mix" if args.mix else ""
    df = sweep(args.methods, seeds=list(range(args.seeds)), config=cfg)
    df.to_csv(args.out / f"results{suffix}.csv", index=False)
    table = ranking_table(df)
    table.to_csv(args.out / f"ranking{suffix}.csv", index=False)
    boxplot_by_method(
        df, args.out / f"boarding_times{suffix}.png",
        order=CANONICAL_ORDER, ylim=COMPARISON_YLIM,
    )
    print(table.to_string(index=False))
    if args.trajectories is not None:
        _save_trajectories(args.methods, args.trajectories, cfg, args.out)


if __name__ == "__main__":
    main()
