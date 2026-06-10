import argparse
from pathlib import Path

from .analysis import boxplot_by_method, ranking_table
from .config import BoardingConfig
from .experiment import sweep
from .methods import METHODS


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Steffen airplane boarding-method study.")
    p.add_argument(
        "--methods", nargs="+", default=list(METHODS), choices=list(METHODS)
    )
    p.add_argument("--seeds", type=int, default=20, help="number of paired seeds")
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("boarding_out"))
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    args.out.mkdir(parents=True, exist_ok=True)
    df = sweep(args.methods, seeds=list(range(args.seeds)), config=cfg)
    df.to_csv(args.out / "results.csv", index=False)
    table = ranking_table(df)
    table.to_csv(args.out / "ranking.csv", index=False)
    boxplot_by_method(df, args.out / "boarding_times.png")
    print(table.to_string(index=False))


if __name__ == "__main__":
    main()
