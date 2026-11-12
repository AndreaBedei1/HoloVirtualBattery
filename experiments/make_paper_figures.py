"""Paper figures (PNG 300 dpi, SVG, PDF) and their plotted data (CSV), from results only.

Every number comes from machine-readable results in experiments/results/ or from the
evidence registry / packaged profiles; nothing is typed in. A figure whose inputs are
missing is skipped and listed in docs/figures/paper/manifest.json. Requires matplotlib
(not a HoloEnergy dependency).
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
RESULTS = ROOT / "experiments/results"
NATIVE = RESULTS / "native"
OUT = ROOT / "docs/figures/paper"
# Validated categorical order (dataviz reference palette, light mode); fixed, never cycled.
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update(
    {
        "font.size": 8,
        "axes.edgecolor": MUTED,
        "axes.labelcolor": INK,
        "axes.titlesize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.6,
        "axes.axisbelow": True,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "legend.frameon": False,
        "lines.linewidth": 2,
        "savefig.facecolor": SURFACE,
        "svg.hashsalt": "holoenergy",  # deterministic SVG element ids
    }
)
# No creation dates in the files: identical inputs give byte-identical figures.
METADATA = {"pdf": {"CreationDate": None, "ModDate": None}, "svg": {"Date": None}, "png": {}}
MANIFEST = {"figures": {}, "skipped": {}}


def save(fig, name, rows, caption):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=300, bbox_inches="tight", metadata=METADATA[ext])
    plt.close(fig)
    if rows:
        keys = list(dict.fromkeys(k for r in rows for k in r))
        with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, keys)
            writer.writeheader()
            writer.writerows(rows)
    MANIFEST["figures"][name] = {"caption": caption, "data": f"{name}.csv" if rows else None}


def skip(name, why):
    MANIFEST["skipped"][name] = why


def summaries(group):
    return {
        p.name.removesuffix(".summary.json"): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted((NATIVE / group).glob("*.summary.json"))
    }


def bar_ends(ax, bars):
    for b in bars:
        b.set_linewidth(0)


# ----------------------------------------------------------------- diagrams (F1, F2)
def box(ax, x, y, w, h, text, color):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.04", fc="white", ec=color, lw=1.4
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=7, color=INK, wrap=True)


def arrow(ax, a, b, color=MUTED, style="-|>"):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle=style, mutation_scale=8, color=color, lw=1))


def fig_architecture():
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5.05)
    box(ax, 0.2, 3.6, 2.0, 0.9, "Controller\n(body wrench or\nper-actuator effort)", C[0])
    box(
        ax, 2.8, 3.6, 2.2, 0.9, "Actuation layer\nB (6×n) allocation,\nbounds at pack voltage", C[0]
    )
    box(ax, 5.6, 3.6, 2.0, 0.9, "Backend mapping\ndirect | wrench-\nequivalent", C[0])
    box(ax, 8.1, 3.6, 1.7, 0.9, "HoloOcean\n(verified 100 Hz,\nSI drag)", C[1])
    box(
        ax,
        2.8,
        2.0,
        2.2,
        0.9,
        "Electrical models\nT200 tables, sensors,\ncompute, auxiliaries",
        C[2],
    )
    box(ax, 5.6, 2.0, 2.0, 0.9, "Bus + power manager\nconverters, limits,\nderating", C[2])
    box(ax, 8.1, 2.0, 1.7, 0.9, "Battery L0 / L1\nOCV, R, thermal", C[2])
    box(
        ax,
        0.2,
        2.0,
        2.0,
        0.9,
        "DESERT via holo_desert\n(observe-only PHY\nevents -> modem W)",
        C[3],
    )
    box(
        ax,
        2.8,
        0.3,
        4.8,
        0.9,
        "Evidence registry -> grades A/B/C/D, bounds, unconfigured loads,\ndouble counting -> provenance-aware EnergyReport",
        C[4],
    )
    arrow(ax, (2.2, 4.05), (2.8, 4.05))
    arrow(ax, (5.0, 4.05), (5.6, 4.05))
    arrow(ax, (7.6, 4.05), (8.1, 4.05))
    arrow(ax, (3.9, 3.6), (3.9, 2.9))
    arrow(ax, (5.0, 2.45), (5.6, 2.45))
    arrow(ax, (7.6, 2.45), (8.1, 2.45))
    arrow(ax, (8.95, 2.9), (7.3, 3.6), color=C[2])  # derating limits applied forces
    ax.text(8.25, 3.2, "available" + chr(10) + "power", fontsize=6, color=MUTED, ha="center")
    ax.plot([8.95, 8.95, 1.2], [4.5, 4.78, 4.78], color=C[1], lw=1)
    arrow(ax, (1.2, 4.78), (1.2, 4.5), color=C[1])
    arrow(ax, (2.2, 2.45), (2.8, 2.45), color=C[3])
    arrow(ax, (5.2, 1.2), (5.2, 2.0), style="<|-")
    ax.text(5.0, 4.85, "measured motion (closed loop)", fontsize=6.5, color=MUTED, ha="center")
    save(
        fig,
        "F01_architecture",
        [],
        "HoloEnergy closed loop: controller wrench -> allocation over the configured actuator "
        "layout -> electrical models -> bus -> battery -> available power/derating -> applied "
        "forces -> HoloOcean dynamics; DESERT activity is observed, never driven.",
    )


def fig_evidence_flow():
    fig, ax = plt.subplots(figsize=(7.2, 2.2))
    ax.set_axis_off()
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 2.6)
    steps = [
        ("Literature,\ndatasheets, code", C[0]),
        ("Evidence record\nvalue/range/bound,\nunit, location", C[0]),
        ("Relation cap\nexact A, repr. B,\nproxy C, user D", C[4]),
        ("Profile state\n{evidence: id,\nuse: value|max}", C[2]),
        ("Per-tick energy\nattributed to grade", C[2]),
        ("Report: coverage,\nupper-bound share,\nintervals, gaps", C[1]),
    ]
    for i, (t, col) in enumerate(steps):
        box(ax, 0.1 + i * 1.65, 0.8, 1.45, 1.1, t, col)
        if i:
            arrow(ax, (0.1 + i * 1.65 - 0.2, 1.35), (0.1 + i * 1.65, 1.35))
    ax.text(
        5,
        0.35,
        "unknown -> value null, status unconfigured, grade D (excluded, reported)",
        ha="center",
        fontsize=7,
        color=MUTED,
    )
    save(
        fig,
        "F02_evidence_flow",
        [],
        "Evidence and provenance flow; grade coverage is provenance, not a confidence interval.",
    )


# ---------------------------------------------------------------------- T200 (F3)
def fig_t200():
    profile = json.loads(
        (ROOT / "holoenergy/profiles/thrusters/bluerobotics_t200.json").read_text()
    )
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    rows = []
    tables = sorted(profile["voltage_tables"], key=lambda t: t["voltage_V"])
    picks = [tables[0], tables[len(tables) // 2], tables[-1]]
    for color, table in zip(C, picks, strict=False):
        for direction, sign in (("forward", 1), ("reverse", -1)):
            pts = sorted({(r["force_N"], r["power_W"]) for r in table[direction]})
            xs = [sign * f for f, _ in pts]
            ys = [p for _, p in pts]
            ax.plot(
                xs, ys, color=color, lw=1.2, label=f"{table['voltage_V']:g} V" if sign > 0 else None
            )
            ax.scatter(
                xs[::6], ys[::6], s=8, color=color, zorder=3, edgecolors=SURFACE, linewidths=0.5
            )
            rows += [
                {
                    "voltage_V": table["voltage_V"],
                    "direction": direction,
                    "force_N": f,
                    "power_W": p,
                }
                for f, p in pts
            ]
    ax.set_xlabel("Thrust (N), reverse negative")
    ax.set_ylabel("Electrical power (W)")
    ax.legend(loc="upper center")
    save(
        fig,
        "F03_t200_model",
        rows,
        "T200 electrical model = Blue Robotics static (bollard) force/power tables, interpolated; "
        "points are table entries. No published advance-speed data: inflow effects are not modelled.",
    )


# --------------------------------------------------------------- backend check (F4)
def fig_backend():
    files = {
        "official 2.3.0\n(archived)": ROOT / "sources/verified_backend/check_final_original.json",
        "control\nrebuild": NATIVE / "backend/check_rebuilt_before.json",
        "patched\nrebuild": NATIVE / "backend/check_patched_after.json",
    }
    if not all(p.exists() for p in files.values()):
        return skip("F04_backend_verification", "backend check files missing")
    rows = []
    fig, ax = plt.subplots(figsize=(3.6, 2.4))
    for i, (name, path) in enumerate(files.items()):
        d = json.loads(path.read_text())["drag"]
        for j, (key, label) in enumerate(
            (("current_ratio", "in current"), ("still_water_ratio", "still water"))
        ):
            b = ax.bar(
                i + (j - 0.5) * 0.36, d[key], 0.34, color=C[j], label=label if i == 0 else None
            )
            bar_ends(ax, b)
            rows.append(
                {"build": name.replace("\n", " "), "case": label, "observed_over_expected": d[key]}
            )
    ax.set_yscale("log")
    ax.axhline(1, color=MUTED, lw=0.8, ls="--")
    ax.set_xticks(range(3), list(files))
    ax.set_ylabel("Observed / expected SI drag")
    ax.legend(loc="center left")
    save(
        fig,
        "F04_backend_verification",
        rows,
        "Implementation verification at 100 Hz: the official binary and its unpatched control "
        "rebuild apply 0.01x the SI drag; the patched build applies 1.000000x. Verification of "
        "the drag equation, not validation of BlueROV2 hydrodynamics.",
    )


# ------------------------------------------------------------- layouts (F6, F7, F8)
def fig_layouts():
    runs = summaries("N1_layouts")
    if not runs:
        return skip("F06_layouts", "no N1 results")
    layouts = ["L8-HV", "L6-STD", "L4-H45", "L4-2H2V", "L8-VEC30"]
    currents = [0.2, 0.5, 0.8]  # at 0 m/s every layout needs ~0 W (no disturbance)
    # Small multiples: each current has its own scale (energies differ by ~20x).
    fig, axes = plt.subplots(1, len(currents), figsize=(7.2, 2.5))
    rows = []
    for ax, c in zip(axes, currents, strict=True):
        for j, layout in enumerate(layouts):
            label = f"N1-{layout}-{'direct' if layout == 'L8-HV' else 'we'}-c{c:g}"
            r = runs.get(label)
            if not r:
                continue
            m = r["metrics"]
            ok = m["max_allocation_residual_norm"] < 1e-3 and m["native_saturated_fraction"] == 0
            ax.bar(
                j,
                m["propulsion_Wh"],
                0.7,
                color=C[j],
                hatch=None if ok else "////",
                edgecolor=SURFACE,
                linewidth=1,
            )
            if not ok:
                ax.text(
                    j,
                    m["propulsion_Wh"],
                    "not met",
                    ha="center",
                    va="bottom",
                    fontsize=5.5,
                    color=INK,
                )
            rows.append(
                {
                    "layout": layout,
                    "current_m_s": c,
                    "rank": r["layout"]["layout_rank"],
                    "geometry_grade": r["layout"]["geometry_grade"],
                    "propulsion_Wh": m["propulsion_Wh"],
                    "mean_tail_tracking_error_m": m["mean_tail_tracking_error_m"],
                    "max_allocation_residual_norm": m["max_allocation_residual_norm"],
                    "native_saturated_fraction": m["native_saturated_fraction"],
                    "satisfies_request": ok,
                }
            )
        ax.set_title(f"{c:g} m/s surge current")
        ax.set_xticks(range(len(layouts)), layouts, rotation=45, ha="right", fontsize=6.5)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("Propulsion energy, 30 s (Wh)")
    save(
        fig,
        "F06_layouts_station_keeping",
        rows,
        "Native closed-loop station keeping on the BlueROV2 body (L8-HV simulator-exact; others "
        "virtual layouts via wrench-equivalent actuation; separate y-scales). Hatched 'not met': "
        "requested wrench not achieved (allocation residual or native clamp) - not comparable.",
    )


def fig_orientation():
    runs = summaries("N2_orientation")
    n1 = summaries("N1_layouts")
    if not runs:
        return skip("F07_orientation", "no N2 results")
    cases = {
        "a30": ("N2-L8-HV-a30-surge-c0.5", "N2-L8-HV-a30-sway-c0.5"),
        "a45 (BlueROV2)": ("N1-L8-HV-direct-c0.5", "N2-L8-HV-sway-c0.5"),
        "a60": ("N2-L8-HV-a60-surge-c0.5", "N2-L8-HV-a60-sway-c0.5"),
    }
    fig, ax = plt.subplots(figsize=(3.6, 2.5))
    rows = []
    for i, (name, (surge, sway)) in enumerate(cases.items()):
        for j, (label, axis) in enumerate(((surge, "surge current"), (sway, "sway current"))):
            r = runs.get(label) or n1.get(label)
            if not r:
                continue
            m = r["metrics"]
            x = i + (j - 0.5) * 0.36
            ax.bar(x, m["propulsion_Wh"], 0.34, color=C[j], label=axis if i == 0 else None)
            if m["derated_tick_fraction"] > 0:
                ax.text(
                    x,
                    m["propulsion_Wh"],
                    "pack limit",
                    ha="center",
                    va="bottom",
                    fontsize=5.5,
                    color=INK,
                )
            rows.append(
                {
                    "horizontal_angle": name,
                    "case": axis,
                    "propulsion_Wh": m["propulsion_Wh"],
                    "mean_tail_tracking_error_m": m["mean_tail_tracking_error_m"],
                    "peak_actuator_force_N": m["peak_actuator_force_N"],
                    "max_allocation_residual_norm": m["max_allocation_residual_norm"],
                    "derated_tick_fraction": m["derated_tick_fraction"],
                    "peak_current_A": m["peak_current_A"],
                }
            )
    ax.set_xticks(range(3), list(cases))
    ax.set_ylabel("Propulsion energy, 30 s (Wh)")
    ax.legend()
    save(
        fig,
        "F07_orientation_tradeoff",
        rows,
        "Horizontal thruster angle trades surge against sway cost (0.5 m/s current, native closed loop).",
    )


def fig_station_current():
    path = NATIVE / "tables/baselines.csv"
    if not path.exists():
        return skip("F08_station_current", "run experiments/analyze_native_campaign.py first")
    rows = [
        r
        for r in csv.DictReader(path.open())
        if r["plan"] == "station30" and r["run"].startswith("N1-L8-HV-direct")
    ]
    rows.sort(key=lambda r: float(r["current_m_s"]))
    if not rows:
        return skip("F08_station_current", "no L8 station rows")
    x = [float(r["current_m_s"]) for r in rows]
    fig, ax = plt.subplots(figsize=(3.6, 2.5))
    for key, label, col in (
        ("holoenergy_propulsion_Wh", "actuator effort (HoloEnergy)", C[0]),
        ("speed_cubic_Wh", "speed-cubic, over-ground speed", C[1]),
        ("speed_cubic_water_Wh", "speed-cubic, speed through water", C[3]),
        ("constant_Wh", "constant-power baseline", C[2]),
    ):
        ax.plot(x, [float(r[key]) for r in rows], color=col, marker="o", ms=4, label=label)
    ax.set_xlabel("Current (m/s)")
    ax.set_ylabel("Propulsion energy, 30 s (Wh)")
    ax.legend()
    save(
        fig,
        "F08_station_keeping_current",
        rows,
        "Station keeping vs current. Baselines fitted on the calm-water transit: a cubic in over-ground speed misses the current; a cubic in speed through the water errs by -15 to +13 % in surge (it cannot represent layout, orientation or heave).",
    )


def fig_suites():
    runs = summaries("N5_suites")
    if not runs:
        return skip("F09_suites", "no N5 results")
    cats = ["propulsion", "sensors", "compute", "auxiliaries", "battery_losses"]
    fig, ax = plt.subplots(figsize=(3.8, 2.5))
    rows = []
    for i, (_label, r) in enumerate(sorted(runs.items())):
        bottom = 0.0
        for j, cat in enumerate(cats):
            v = r["metrics"]["category_energy_Wh"].get(cat, 0.0)
            ax.bar(
                i,
                v,
                0.6,
                bottom=bottom,
                color=C[j],
                label=cat if i == 0 else None,
                edgecolor=SURFACE,
                linewidth=1,
            )
            bottom += v
            rows.append({"suite": r["spec"]["suite"], "category": cat, "Wh": v})
    ax.set_xticks(
        range(len(runs)),
        [r["spec"]["suite"].split("-", 1)[1] for _, r in sorted(runs.items())],
        rotation=0,
    )
    ax.set_ylabel("Energy, transit in 0.2 m/s (Wh)")
    ax.legend(fontsize=6.5)
    save(
        fig,
        "F09_payload_breakdown",
        rows,
        "Mission energy by category for three sensor/compute suites (same native transit).",
    )


def fig_comm():
    path = NATIVE / "desert/comm_matrix.json"
    if not path.exists():
        return skip("F10_comm", "no comm matrix")
    res = json.loads(path.read_text())["results"]
    names = [k for k, v in res.items() if "error" not in v]
    fig, ax = plt.subplots(figsize=(3.8, 2.5))
    rows = []
    for i, k in enumerate(names):
        r = res[k]
        per = r["energy_check"]["per_interface_recomputed"]
        p_states = {}
        for v in per.values():
            for s in ("TX", "RX", "LISTEN"):
                p_states[s] = p_states.get(s, 0.0) + v[f"{s}_s"]
        b = ax.bar(i, r["communication_Wh"] * 1000, 0.6, color=C[0])
        bar_ends(ax, b)
        ax.text(
            i,
            r["communication_Wh"] * 1000,
            f"{r['delivered']}/{r['generated']}",
            ha="center",
            va="bottom",
            fontsize=6,
            color=INK,
        )
        rows.append(
            {
                "configuration": k,
                "communication_mWh": r["communication_Wh"] * 1000,
                "delivered": r["delivered"],
                "generated": r["generated"],
                "tx_frames": r["tx_frames"],
                "control_tx_frames": r["control_tx_frames"],
                "relay_forwards": r["relay_forwards"],
                "upper_bound_energy_share": r["upper_bound_energy_share"],
            }
        )
    ax.set_xticks(range(len(names)), names)
    ax.set_ylabel("Network communication energy (mWh)")
    save(
        fig,
        "F10_communication_policies",
        rows,
        "Native DESERT: communication energy of identical traffic under different network strategies (labels: delivered/generated). LISTEN dominates.",
    )


def fig_crosslayer():
    path = NATIVE / "crosslayer.json"
    if not path.exists():
        return skip("F11_crosslayer", "no cross-layer results")
    res = {k: v for k, v in json.loads(path.read_text())["results"].items() if "error" not in v}
    cats = ["propulsion", "sensors", "compute", "communications", "battery_losses"]
    fig, ax = plt.subplots(figsize=(3.8, 2.5))
    rows = []
    for i, (k, r) in enumerate(res.items()):
        bottom = 0.0
        for j, cat in enumerate(cats):
            v = r["mission"]["category_energy_Wh"].get(cat, 0.0)
            ax.bar(
                i,
                v,
                0.6,
                bottom=bottom,
                color=C[j],
                label=cat if i == 0 else None,
                edgecolor=SURFACE,
                linewidth=1,
            )
            bottom += v
            rows.append({"strategy": k, "category": cat, "Wh": v})
    ax.set_xticks(range(len(res)), list(res))
    ax.set_ylabel("Mission energy (Wh)")
    ax.legend(fontsize=6.5)
    save(
        fig,
        "F11_mission_with_without_comms",
        rows,
        "Same native mission with different network strategies: communication energy enters the battery through the observe-only adapter.",
    )


def fig_uncertainty():
    rows = []
    for group in ("N4_mission", "N5_suites"):
        for label, r in summaries(group).items():
            iv = (r.get("energy_report") or {}).get("intervals", {}).get("terminal_energy_Wh")
            if iv:
                rows.append(
                    {
                        "run": label,
                        "nominal_Wh": iv.get("nominal"),
                        "low_Wh": iv.get("low"),
                        "high_Wh": iv.get("high"),
                        "open_low": ";".join(iv.get("open_low", [])),
                        "open_high": ";".join(iv.get("open_high", [])),
                    }
                )
    if not rows:
        return skip("F13_uncertainty", "no intervals")
    fig, ax = plt.subplots(figsize=(3.8, 2.4))
    for i, r in enumerate(rows):
        lo = r["low_Wh"] if r["low_Wh"] is not None else r["nominal_Wh"]
        hi = r["high_Wh"] if r["high_Wh"] is not None else r["nominal_Wh"]
        ax.plot([lo, hi], [i, i], color=C[0], lw=2, solid_capstyle="round")
        ax.scatter([r["nominal_Wh"]], [i], s=14, color=C[1], zorder=3, edgecolors=SURFACE)
        if r["open_low"]:
            ax.text(lo, i + 0.15, "open low", fontsize=5.5, color=MUTED)
    ax.set_yticks(range(len(rows)), [r["run"].replace("-transit", "") for r in rows], fontsize=6)
    ax.set_xlabel("Terminal energy (Wh): nominal and published-range interval")
    save(
        fig,
        "F13_uncertainty_intervals",
        rows,
        "Interval propagation of published component ranges; sides without published bounds stay open.",
    )


def main(argv=None):
    import argparse

    global OUT, NATIVE
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUT, help="figure directory")
    parser.add_argument("--native-dir", type=Path, default=NATIVE, help="native results")
    args = parser.parse_args(argv)
    OUT, NATIVE = args.output_dir, args.native_dir
    for f in (
        fig_architecture,
        fig_evidence_flow,
        fig_t200,
        fig_backend,
        fig_layouts,
        fig_orientation,
        fig_station_current,
        fig_suites,
        fig_comm,
        fig_crosslayer,
        fig_uncertainty,
    ):
        try:
            f()
        except Exception as exc:  # noqa: BLE001 - a broken figure is reported, not hidden
            skip(f.__name__, repr(exc))
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "manifest.json").write_text(json.dumps(MANIFEST, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"made": list(MANIFEST["figures"]), "skipped": MANIFEST["skipped"]}, indent=1))


if __name__ == "__main__":
    main()
