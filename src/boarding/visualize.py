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
_FILLED = "#4fd1c5"  # seated passenger (uniform case)
_AISLE = "#f6c453"   # passenger in the aisle (uniform case)

_SOLO = "#9aa0b5"    # background colour: solo passengers / the common "standard" profile
_NONCOMPLIANT = "#e15759"  # passenger boarding out of their assigned slot (compliance video)
_GROUP_PALETTE = ["#e15759", "#4e79a7", "#59a14f", "#f28e2b", "#b07aa1"]  # rotated per group
_PROFILE_COLORS = {
    "standard": _SOLO,
    "business_young": "#4e79a7",
    "heavy_luggage": "#f28e2b",
    "elderly": "#e15759",
    "family_with_kids": "#59a14f",
}


def _color_map(cfg: BoardingConfig, seed: int):
    """Return (color_of, legend_items, caption) for the scenario, or (None, None, None)
    for the uniform case. color_of maps a Seat to a hex colour; legend_items is a list of
    (label, colour) for a profile legend; caption is a one-line note for the group case."""
    if cfg.group_fraction > 0:
        from collections import Counter

        from .groups import assign_groups

        groups = assign_groups(cfg, seed, cfg.group_fraction)
        sizes = Counter(groups.values())
        real = sorted(gid for gid, c in sizes.items() if c >= 2)
        gid_color = {
            gid: _GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i, gid in enumerate(real)
        }

        def color_of(seat):
            return gid_color.get(groups[seat], _SOLO)

        return color_of, None, "each colour = one travelling party  ·  grey = solo"

    if cfg.profile_mix:
        from .profiles import draw_passengers

        pax = draw_passengers(cfg, seed, cfg.profile_mix)

        def color_of(seat):
            return _PROFILE_COLORS.get(pax[seat].profile_name, _SOLO)

        legend = [(p.name, _PROFILE_COLORS.get(p.name, _SOLO)) for p in cfg.profile_mix]
        return color_of, legend, None

    return None, None, None


def capture(method, seed, cfg, sample_every_s, color_of=None):
    """Run one method, sampling (time, aisle, filled) every sample_every_s. Each aisle /
    filled entry is (x, y, colour); colour comes from color_of(seat) or the uniform default."""
    stride = max(1, round(sample_every_s / cfg.dt))
    filled: list[tuple[float, float, str]] = []
    samples: list[tuple[float, list, list]] = []

    def aisle_color(seat):
        return color_of(seat) if color_of else _AISLE

    def seat_color(seat):
        return color_of(seat) if color_of else _FILLED

    def on_frame(iteration, aisle, newly):
        filled.extend((x, y, seat_color(seat)) for x, y, seat in newly)
        if iteration % stride == 0:
            pts = [(x, y, aisle_color(seat)) for x, y, seat in aisle]
            samples.append((iteration * cfg.dt, pts, list(filled)))

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


def _render_panels(panel_caps, cfg, out_path, fps, suptitle, caption, legend_items):
    """Render one stacked animated panel per (label, samples, t_total) entry to mp4.

    All panels share the cabin geometry from ``cfg``. Each title shows the panel label,
    elapsed time, seated count, and finish time."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import animation
    from matplotlib.lines import Line2D

    total = cfg.total_passengers
    n_frames = max(len(samples) for _, samples, _ in panel_caps)
    seat_xy, xlim, ylim = _cabin_extent(cfg)
    seat_x = [p[0] for p in seat_xy]
    seat_y = [p[1] for p in seat_xy]
    n = len(panel_caps)

    fig, axes = plt.subplots(n, 1, figsize=(15, 1.9 * n + 1), facecolor="#0b0d17")
    if n == 1:
        axes = [axes]

    artists = []
    for ax in axes:
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
        artists.append((filled, aisle, title))

    fig.suptitle(suptitle, color="white", fontsize=14, fontweight="bold")
    bottom = 0.05 if (legend_items or caption) else 0.0
    fig.tight_layout(rect=(0, bottom, 1, 0.96))

    for top_ax, bot_ax in zip(axes[:-1], axes[1:], strict=True):
        y = (top_ax.get_position().y0 + bot_ax.get_position().y1) / 2.0
        fig.add_artist(
            Line2D([0.02, 0.98], [y, y], transform=fig.transFigure,
                   color="#6b7394", linewidth=1.0)
        )

    if legend_items:
        handles = [
            Line2D([0], [0], marker="o", linestyle="", markersize=7,
                   markerfacecolor=c, markeredgecolor="none", label=name)
            for name, c in legend_items
        ]
        fig.legend(handles=handles, loc="lower center", ncol=len(handles),
                   frameon=False, labelcolor="white", fontsize=9)
    if caption:
        fig.text(0.5, 0.012, caption, ha="center", color="#c7ccdb", fontsize=10)

    def _split(pts):
        if not pts:
            return _EMPTY_XY, None
        return [(x, y) for x, y, _ in pts], [c for _, _, c in pts]

    def frame(i):
        updated = []
        for (label, samples, t_total), (filled_a, aisle_a, title) in zip(
            panel_caps, artists, strict=True
        ):
            t, aisle_pts, filled_pts = samples[min(i, len(samples) - 1)]
            fxy, fc = _split(filled_pts)
            axy, ac = _split(aisle_pts)
            filled_a.set_offsets(fxy)
            if fc:
                filled_a.set_facecolor(fc)
            aisle_a.set_offsets(axy)
            if ac:
                aisle_a.set_facecolor(ac)
            title.set_text(
                f"{label}   t={t:5.0f}s   seated {len(filled_pts):>3}/{total}"
                f"   (finishes {t_total:.0f}s)"
            )
            updated += [filled_a, aisle_a, title]
        return updated

    anim = animation.FuncAnimation(fig, frame, frames=n_frames, interval=1000 / fps)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    anim.save(out_path, writer=animation.FFMpegWriter(fps=fps, bitrate=2400))
    plt.close(fig)
    return out_path


def build_comparison_video(
    methods,
    seed: int,
    cfg: BoardingConfig,
    out_path: Path,
    fps: int = 20,
    sample_every_s: float = 1.5,
    scenario: str = "",
) -> Path:
    """One panel per method, all under the same cfg (homogeneous / mix / groups)."""
    color_of, legend_items, caption = _color_map(cfg, seed)
    panel_caps = [
        (m, *capture(m, seed, cfg, sample_every_s, color_of)) for m in methods
    ]
    suptitle = "Airplane boarding — method comparison"
    if scenario:
        suptitle += f"  ·  {scenario}"
    return _render_panels(panel_caps, cfg, out_path, fps, suptitle, caption, legend_items)


def build_compliance_video(
    method: str,
    seed: int,
    rates,
    cfg: BoardingConfig,
    out_path: Path,
    fps: int = 20,
    sample_every_s: float = 1.5,
) -> Path:
    """One panel per compliance rate, all for the same method. Non-compliant passengers
    (those boarding out of their assigned slot) are highlighted red; compliant ones grey."""
    from dataclasses import replace

    from .compliance import noncompliant_seats
    from .methods import all_seats

    seats = all_seats(cfg)

    def _color_for(noncompliant):
        return lambda seat: _NONCOMPLIANT if seat in noncompliant else _SOLO

    panel_caps = []
    for rate in rates:
        cfg_r = replace(cfg, compliance_rate=rate)
        color_of = _color_for(noncompliant_seats(seats, rate, seed))
        samples, t_total = capture(method, seed, cfg_r, sample_every_s, color_of)
        panel_caps.append((f"{method} · {round(rate * 100)}% compliance", samples, t_total))

    suptitle = "Airplane boarding — compliance comparison"
    caption = "red = boarding out of assigned slot (non-compliant)"
    return _render_panels(panel_caps, cfg, out_path, fps, suptitle, caption, None)


def main(argv=None):
    import argparse

    from .profiles import DEFAULT_MIX

    p = argparse.ArgumentParser(description="Boarding method-comparison video.")
    p.add_argument("--methods", nargs="+", default=list(METHODS), choices=list(METHODS))
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--rows", type=int, default=30)
    p.add_argument("--out", type=Path, default=Path("study-output/comparison.mp4"))
    p.add_argument("--fps", type=int, default=20)
    p.add_argument("--sample-every-s", type=float, default=1.5)
    p.add_argument("--mix", action="store_true", help="use the realistic passenger mix")
    p.add_argument(
        "--group-fraction", type=float, default=0.0,
        help="fraction of passengers travelling in cohesive groups",
    )
    p.add_argument(
        "--compliance", action="store_true",
        help="build a compliance video: one method, one panel per --compliance-rates value",
    )
    p.add_argument("--method", default="steffen_perfect", choices=list(METHODS),
                   help="method held fixed in --compliance mode")
    p.add_argument("--compliance-rates", nargs="+", type=float, default=[1.0, 0.5],
                   help="compliance rates to panel in --compliance mode")
    args = p.parse_args(argv)

    if args.compliance:
        cfg = BoardingConfig(rows=args.rows)
        out = build_compliance_video(
            args.method, args.seed, args.compliance_rates, cfg,
            args.out, args.fps, args.sample_every_s,
        )
        print(f"wrote {out}")
        return

    cfg = BoardingConfig(
        rows=args.rows,
        profile_mix=DEFAULT_MIX if args.mix else None,
        group_fraction=args.group_fraction,
    )
    if args.mix:
        scenario = "realistic passenger mix"
    elif args.group_fraction > 0:
        scenario = f"{round(args.group_fraction * 100)}% travel groups"
    else:
        scenario = "uniform passengers"
    out = build_comparison_video(
        args.methods, args.seed, cfg, args.out, args.fps, args.sample_every_s, scenario
    )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
