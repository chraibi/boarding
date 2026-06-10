"""Comparison animation: all boarding methods side by side, seats filling over time.

Each panel shows one method's cabin — aisle passengers as dots, seats as squares that
fill (colour in) at each passenger's seat-time. Panels share a clock so you can watch
which method seats everyone first. Renders to mp4.
"""

from pathlib import Path

from .config import BoardingConfig
from .experiment import run_boarding
from .geometry import _row_x, build_fuselage
from .methods import METHODS

_EMPTY_XY = [[0, -999]]  # off-screen placeholder for an empty scatter (set_offsets needs Nx2)

_EMPTY = "#3a3f57"   # unoccupied seat outline
_FILLED = "#4fd1c5"  # seated passenger
_AISLE = "#f6c453"   # passenger in the aisle


def capture(method: str, seed: int, cfg: BoardingConfig, sample_every_s: float):
    """Run one method, sampling (time, aisle_xy, filled_seat_xy) every sample_every_s."""
    stride = max(1, round(sample_every_s / cfg.dt))
    filled: list[tuple[float, float]] = []
    samples: list[tuple[float, list, list]] = []

    def on_frame(iteration, aisle_positions, newly_seated_coords):
        filled.extend(newly_seated_coords)
        if iteration % stride == 0:
            samples.append((iteration * cfg.dt, list(aisle_positions), list(filled)))

    result = run_boarding(method, seed, config=cfg, on_frame=on_frame)
    samples.append((result.total_time, [], list(filled)))  # final all-seated frame
    return samples, result.total_time


def _cabin_extent(cfg: BoardingConfig):
    seat_map = build_fuselage(cfg)[1]
    seat_xy = [g.seat_coord for g in seat_map.values()]
    ys = [y for _, y in seat_xy]
    x0 = cfg.door_depth * 0.1
    x1 = _row_x(cfg, cfg.rows) + cfg.seat_pitch
    pad = cfg.seat_width
    return seat_xy, (x0, x1), (min(ys) - pad, max(ys) + pad)


def build_comparison_video(
    methods,
    seed: int,
    cfg: BoardingConfig,
    out_path: Path,
    fps: int = 20,
    sample_every_s: float = 1.5,
) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import animation

    captures = {m: capture(m, seed, cfg, sample_every_s) for m in methods}
    n_frames = max(len(s) for s, _ in captures.values())
    total = cfg.total_passengers
    seat_xy, xlim, ylim = _cabin_extent(cfg)
    seat_x = [p[0] for p in seat_xy]
    seat_y = [p[1] for p in seat_xy]

    fig, axes = plt.subplots(
        len(methods), 1, figsize=(15, 1.9 * len(methods) + 1), facecolor="#0b0d17"
    )
    if len(methods) == 1:
        axes = [axes]

    artists = {}
    for ax, method in zip(axes, methods, strict=True):
        ax.set_facecolor("#0b0d17")
        ax.scatter(seat_x, seat_y, s=14, marker="s",
                   facecolors="none", edgecolors=_EMPTY, linewidths=0.6)
        filled = ax.scatter([], [], s=14, marker="s", c=_FILLED, zorder=3)
        aisle = ax.scatter([], [], s=26, marker="o", c=_AISLE,
                           edgecolors="#1a1d2e", linewidths=0.4, zorder=4)
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_xticks([])
        ax.set_yticks([])
        title = ax.set_title(
            "", color="white", fontsize=12, fontweight="bold", loc="left", pad=5
        )
        for spine in ax.spines.values():
            spine.set_color("#2a2f45")
        artists[method] = (filled, aisle, title)

    fig.suptitle("Airplane boarding — method comparison (seats fill as passengers sit)",
                 color="white", fontsize=14, fontweight="bold")
    fig.tight_layout(rect=(0, 0, 1, 0.96))

    # horizontal divider line between each pair of method panels
    from matplotlib.lines import Line2D

    for top_ax, bot_ax in zip(axes[:-1], axes[1:], strict=True):
        y = (top_ax.get_position().y0 + bot_ax.get_position().y1) / 2.0
        fig.add_artist(
            Line2D([0.02, 0.98], [y, y], transform=fig.transFigure,
                   color="#6b7394", linewidth=1.0)
        )

    def frame(i):
        updated = []
        for method in methods:
            samples, t_total = captures[method]
            s = samples[min(i, len(samples) - 1)]  # finished panels hold last frame
            t, aisle_xy, filled_xy = s
            filled_a, aisle_a, title = artists[method]
            filled_a.set_offsets(filled_xy if filled_xy else _EMPTY_XY)
            aisle_a.set_offsets(aisle_xy if aisle_xy else _EMPTY_XY)
            title.set_text(
                f"{method}   t={t:5.0f}s   seated {len(filled_xy):>3}/{total}"
                f"   (finishes {t_total:.0f}s)"
            )
            updated += [filled_a, aisle_a, title]
        return updated

    anim = animation.FuncAnimation(fig, frame, frames=n_frames, interval=1000 / fps)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(out_path, writer=animation.FFMpegWriter(fps=fps, bitrate=2400))
    plt.close(fig)
    return out_path


def main(argv=None):
    import argparse

    p = argparse.ArgumentParser(description="Boarding method-comparison video.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("study-output/comparison.mp4"))
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--sample-every-s", type=float, default=1.5)
    args = p.parse_args(argv)
    cfg = BoardingConfig(rows=args.rows)
    out = build_comparison_video(
        args.methods, args.seed, cfg, args.out, args.fps, args.sample_every_s
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
