"""Paper figures A-E from the BEFORE/AFTER backend campaigns; never invents data.

Each figure is written as PNG/SVG/PDF together with the CSV of the plotted values.
Inputs are the machine-readable reports produced by the audit and study scripts.
Matplotlib is optional and only needed here.
"""

import argparse
import csv
import gzip
import json
import statistics
from pathlib import Path

# Validated categorical slots (dataviz reference palette, light mode, 3 slots).
AFTER, BEFORE, CONTROL = "#2a78d6", "#eb6834", "#1baf7a"
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e5e4e0"


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def style(plt):
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.edgecolor": MUTED,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.6,
            "legend.frameon": False,
            "savefig.facecolor": "white",
        }
    )


def save(fig, out_dir, name, rows, header):
    out_dir.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "svg", "pdf"):
        fig.savefig(out_dir / f"{name}.{suffix}", dpi=200, bbox_inches="tight")
    with (out_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def current_records(report):
    return [
        r
        for r in report["records"]
        if r["case"].startswith("current_x_") and r["case"] != "current_x_negative"
    ]


def figure_a(plt, before, after, out_dir):
    fig, ax = plt.subplots(figsize=(5.2, 3.8))
    rows = []
    for label, report, color, marker in (
        ("Before (stock 2.3.0)", before, BEFORE, "o"),
        ("After (patched 2.3.0)", after, AFTER, "s"),
    ):
        recs = current_records(report)
        x = [abs(r["expected_drag_N"][0]) for r in recs]
        y = [abs(r["observed_drag_N"][0]) for r in recs]
        ax.loglog(x, y, marker, color=color, ms=6, mfc="white", mew=1.6, label=label)
        rows += [
            [label, r["ticks_per_sec"], r["trial"], r["current_m_s"][0], e, o]
            for r, e, o in zip(recs, x, y, strict=True)
        ]
    span = [1, 200]
    ax.loglog(span, span, "-", color=MUTED, lw=1.2, zorder=0)
    ax.loglog(span, [s / 100 for s in span], "--", color=MUTED, lw=1.2, zorder=0)
    ax.text(60, 75, "applied = SI equation", color=MUTED, ha="right", fontsize=8)
    ax.text(60, 0.75, "applied = SI / 100", color=MUTED, ha="right", va="top", fontsize=8)
    ax.set_xlabel("Expected SI drag from the source equation [N]")
    ax.set_ylabel("Applied drag inferred from runtime [N]")
    ax.set_title("A. Native drag magnitude, first step from rest", loc="left", color=INK)
    ax.legend(loc="lower right")
    save(
        fig,
        out_dir,
        "fig_a_drag_expected_vs_measured",
        rows,
        ["build", "ticks_per_sec", "trial", "current_m_s", "expected_N", "inferred_applied_N"],
    )
    plt.close(fig)


def scale_groups(report):
    groups = {
        "current magnitude (+X)": lambda c: (
            c.startswith("current_x_") and c != "current_x_negative"
        ),
        "signed axes": lambda c: (
            c == "current_x_negative" or c.startswith(("current_1_", "current_2_"))
        ),
        "yaw 90 deg": lambda c: c == "yaw90_world_current",
        "moving, still water": lambda c: c == "moving_zero_current" or c.startswith("autodrag_"),
    }
    result = {}
    for name, predicate in groups.items():
        values = [
            r["observed_expected_scale"]
            for r in report["records"]
            if predicate(r["case"]) and r["observed_expected_scale"] is not None
        ]
        if values:
            result[name] = values
    return result


def figure_b(plt, reports, out_dir):
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    rows = []
    names = list(scale_groups(reports[0][1]))
    for offset, (label, report, color, marker) in zip((-0.12, 0.12), reports, strict=False):
        groups = scale_groups(report)
        for i, name in enumerate(names):
            values = groups.get(name, [])
            ax.semilogy(
                [i + offset] * len(values),
                values,
                marker,
                color=color,
                ms=6,
                mfc="white",
                mew=1.4,
                label=label if i == 0 else None,
            )
            rows += [[label, name, v] for v in values]
            if values:
                ax.text(
                    i + offset,
                    statistics.mean(values) * 1.6,
                    f"{statistics.mean(values):.6f}",
                    ha="center",
                    fontsize=7,
                    color=INK,
                )
    ax.axhline(1, color=MUTED, lw=1.0, zorder=0)
    ax.axhline(0.01, color=MUTED, lw=1.0, ls="--", zorder=0)
    ax.set_xticks(range(len(names)), names)
    ax.set_ylim(0.004, 3)
    ax.set_ylabel("Inferred applied / expected SI drag")
    ax.set_title("B. Observed/expected drag ratio by case family", loc="left", color=INK)
    ax.legend(loc="center right")
    save(fig, out_dir, "fig_b_drag_ratio", rows, ["build", "case_family", "ratio"])
    plt.close(fig)


def station_rows(study):
    return sorted(
        (r["current_m_s"][0], r)
        for name, r in study["records"].items()
        if name.startswith("station_")
    )


def figure_c(plt, before, after, out_dir):
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    rows = []
    for label, study, color, marker in (
        ("Before (stock 2.3.0)", before, BEFORE, "o"),
        ("After (patched 2.3.0)", after, AFTER, "s"),
    ):
        data = station_rows(study)
        x = [u for u, _ in data]
        y = [r["mean_tail_propulsion_W"] for _, r in data]
        ax.plot(
            x, y, "-", color=color, lw=2, marker=marker, ms=7, mfc="white", mew=1.6, label=label
        )
        for u, r in data:
            rows.append(
                [
                    label,
                    u,
                    r["mean_tail_propulsion_W"],
                    r["mean_tail_applied_effort_norm_N"],
                    r["tail_saturated_tick_fraction"],
                    r["mean_tail_speed_m_s"],
                ]
            )
            if r["tail_saturated_tick_fraction"] > 0:
                ax.annotate(
                    "thrust-limited",
                    (u, r["mean_tail_propulsion_W"]),
                    textcoords="offset points",
                    xytext=(-8, 8),
                    ha="right",
                    fontsize=8,
                    color=MUTED,
                )
    ax.set_xlabel("Constant current speed [m/s]")
    ax.set_ylabel("Mean propulsion power, last 10 s [W]")
    ax.set_title("C. Station keeping: current vs propulsion power", loc="left", color=INK)
    ax.legend(loc="upper left")
    save(
        fig,
        out_dir,
        "fig_c_current_vs_propulsion_power",
        rows,
        [
            "build",
            "current_m_s",
            "propulsion_W",
            "effort_norm_N",
            "saturated_fraction",
            "speed_m_s",
        ],
    )
    plt.close(fig)


def figure_d(plt, before, after, out_dir):
    fig, ax = plt.subplots(figsize=(5.2, 3.6))
    rows = []
    for label, study, color, marker in (
        ("Before (stock 2.3.0)", before, BEFORE, "o"),
        ("After (patched 2.3.0)", after, AFTER, "s"),
    ):
        data = sorted(
            (r["current_m_s"][0], r)
            for name, r in study["records"].items()
            if name.startswith("mission_")
        )
        x = [u for u, _ in data]
        y = [r["terminal_Wh"] for _, r in data]
        ax.plot(
            x, y, "-", color=color, lw=2, marker=marker, ms=7, mfc="white", mew=1.6, label=label
        )
        rows += [
            [label, u, r["terminal_Wh"], r["propulsion_Wh"], r["duration_s"], r["final_soc"]]
            for u, r in data
        ]
    ax.set_xlabel("Constant current speed [m/s]")
    ax.set_ylabel("Mission terminal energy [Wh]")
    ax.set_title("D. Transit-yaw-return mission: current vs energy", loc="left", color=INK)
    ax.legend(loc="upper left")
    save(
        fig,
        out_dir,
        "fig_d_current_vs_mission_energy",
        rows,
        ["build", "current_m_s", "terminal_Wh", "propulsion_Wh", "duration_s", "final_soc"],
    )
    plt.close(fig)


def figure_e(plt, trace_path, out_dir, title):
    with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
        trace = [json.loads(line) for line in handle]
    panels = [
        ("power_propulsion_W", "Propulsion [W]"),
        ("current_A", "Pack current [A]"),
        ("voltage_V", "Terminal voltage [V]"),
        ("soc", "SOC [-]"),
        ("battery_temperature_C", "Battery T [°C]"),
    ]
    fig, axes = plt.subplots(len(panels), 1, figsize=(6.4, 7.2), sharex=True)
    t = [r["t_s"] for r in trace]
    changes = [i for i in range(1, len(trace)) if trace[i]["phase"] != trace[i - 1]["phase"]]
    for ax, (key, label) in zip(axes, panels, strict=True):
        ax.plot(t, [r[key] for r in trace], color=AFTER, lw=1.5)
        ax.set_ylabel(label, fontsize=8)
        for i in changes:
            ax.axvline(t[i], color=GRID, lw=0.8, zorder=0)
    for i in [0, *changes]:
        axes[0].text(
            t[i],
            axes[0].get_ylim()[1],
            trace[i]["phase"].replace("_", " "),
            rotation=90,
            va="top",
            ha="left",
            fontsize=6,
            color=MUTED,
        )
    axes[-1].set_xlabel("Simulated time [s]")
    axes[0].set_title(f"E. {title}", loc="left", color=INK)
    rows = [[r["t_s"], r["phase"]] + [r[k] for k, _ in panels] for r in trace]
    save(fig, out_dir, "fig_e_battery_trace", rows, ["t_s", "phase"] + [k for k, _ in panels])
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--drag-before", type=Path, required=True)
    parser.add_argument("--drag-after", type=Path, required=True)
    parser.add_argument("--autodrag-before", type=Path)
    parser.add_argument("--autodrag-after", type=Path)
    parser.add_argument("--study-before", type=Path, required=True)
    parser.add_argument("--study-after", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--trace-title", default="Battery trace, patched backend mission")
    parser.add_argument("--output-dir", type=Path, default=Path("docs/figures/verified_backend"))
    args = parser.parse_args()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    style(plt)
    before, after = load(args.drag_before), load(args.drag_after)
    figure_a(plt, before, after, args.output_dir)
    merged = []
    for label, report, extra, color, marker in (
        ("Before (stock 2.3.0)", before, args.autodrag_before, BEFORE, "o"),
        ("After (patched 2.3.0)", after, args.autodrag_after, AFTER, "s"),
    ):
        records = list(report["records"])
        if extra:
            records += load(extra)["records"]
        merged.append((label, {"records": records}, color, marker))
    figure_b(plt, merged, args.output_dir)
    study_before, study_after = load(args.study_before), load(args.study_after)
    figure_c(plt, study_before, study_after, args.output_dir)
    figure_d(plt, study_before, study_after, args.output_dir)
    figure_e(plt, args.trace, args.output_dir, args.trace_title)
    print(f"Figures: {args.output_dir}")


if __name__ == "__main__":
    main()
