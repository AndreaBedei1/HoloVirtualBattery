"""Figures of the final results (PNG 300 dpi, SVG, PDF), each with its plotted data (CSV).

Inputs are only the committed final results in experiments/results/final/. Nothing is typed in.
The style and the validated categorical palette come from make_paper_figures.py. The manifest
(docs/figures/final/manifest.json) records every input file with its SHA256 and the commit that
produced it.

    uv run python experiments/make_final_figures.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from make_paper_figures import METADATA, MUTED, C, plt  # noqa: E402

FINAL = ROOT / "experiments/results/final"
OUT = ROOT / "docs/figures/final"
MANIFEST = {"inputs": {}, "figures": {}}


def load(name):
    path = FINAL / name
    MANIFEST["inputs"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text(encoding="utf-8"))


def save(fig, name, rows, caption, sources):
    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg", "pdf"):
        fig.savefig(OUT / f"{name}.{ext}", dpi=300, bbox_inches="tight", metadata=METADATA[ext])
    plt.close(fig)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (OUT / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, keys)
        writer.writeheader()
        writer.writerows(rows)
    MANIFEST["figures"][name] = {"caption": caption, "data": f"{name}.csv", "sources": sources}


def runs():
    return {r["label"]: r for r in load("final_runs.json")["runs"]}


def fig_layouts(r):
    layouts = [
        ("L8-HV", "EXP3-L8-HV"),
        ("L6-STD", "EXP3-L6-STD"),
        ("L4-H45", "EXP3-L4-H45"),
        ("L4-2H2V", "EXP3-L4-2H2V"),
        ("L8-VEC30", "EXP3-L8-VEC30"),
        ("L8-HV 30°", "EXP4-a30"),
        ("L8-HV 60°", "EXP4-a60"),
    ]
    cases = [("head-on", "headon0.5"), ("oblique 45°", "oblique0.5"), ("sway", "sway0.5")]
    rows = []
    fig, ax = plt.subplots(figsize=(6.2, 2.8))
    width = 0.26
    for j, (case, suffix) in enumerate(cases):
        xs, ys = [], []
        for i, (name, prefix) in enumerate(layouts):
            run = r.get(f"{prefix}-{suffix}")
            if run is None:
                ax.text(
                    i + (j - 1) * width,
                    8,
                    "not run",
                    rotation=90,
                    ha="center",
                    va="bottom",
                    fontsize=5.5,
                    color=MUTED,
                    alpha=0.6,
                )
                continue
            held = run["steady_window_request_met"]
            rows.append(
                {
                    "layout": name,
                    "case": case,
                    "current_m_s": 0.5,
                    "steady_propulsion_W": run["steady_propulsion_W"],
                    "steady_window_request_met": held,
                    "run": run["label"],
                }
            )
            x = i + (j - 1) * width
            if held:
                xs.append(x)
                ys.append(run["steady_propulsion_W"])
            else:
                ax.text(
                    x, 8, "not held", rotation=90, ha="center", va="bottom", fontsize=6, color=MUTED
                )
        bars = ax.bar(xs, ys, width=width * 0.92, color=C[j], label=case)
        for b in bars:
            b.set_linewidth(0)
    ax.set_xticks(range(len(layouts)), [n for n, _ in layouts])
    ax.set_ylabel("Steady propulsion power (W)")
    ax.legend(ncols=3, loc="upper left")
    save(
        fig,
        "FF1_layout_orientation",
        rows,
        "Steady propulsion power (last 30 s of 90 s) holding position in a 0.5 m/s current, by layout "
        "and current direction. HoloOcean body and isotropic drag; 'not held' means the steady window "
        "had allocation residual or saturation; 'not run' marks cases outside the final matrix. L8-HV, L6-STD and L4-H45 coincide because only the "
        "four vectored horizontals work on the decoupled simulated body.",
        ["final_runs.json"],
    )


def fig_current(r, sens):
    rows = []
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    for k, law in enumerate(
        (
            "HoloOcean 2.3.0 literals",
            "von Benzon et al. 2022 identified damping (Heavy)",
            "Gabl et al. 2021 restrained load (standard BlueROV2)",
        )
    ):
        pts = [
            p
            for p in sens["part1_drag_model"]
            if p["drag_model"] == law
            and p.get("propulsion_power_W") is not None
            and p.get("feasible_within_clamp")
            and "extrapolated" not in p["note"]
        ]
        for p in pts:
            rows.append(
                {
                    "source": "offline steady allocation",
                    "drag_model": law,
                    "current_m_s": p["current_m_s"],
                    "propulsion_W": p["propulsion_power_W"],
                }
            )
        ax.plot(
            [p["current_m_s"] for p in pts],
            [p["propulsion_power_W"] for p in pts],
            color=C[k],
            marker="o",
            ms=4,
            label=law.split(" (")[0],
        )
    native = [
        ("EXP5-station-c0", 0.0),
        ("EXP3-L8-HV-headon0.2", 0.2),
        ("EXP3-L8-HV-headon0.5", 0.5),
    ]
    for label, u in native:
        rows.append(
            {
                "source": "native closed loop (steady window)",
                "drag_model": "HoloOcean 2.3.0",
                "current_m_s": u,
                "propulsion_W": r[label]["steady_propulsion_W"],
            }
        )
    ax.plot(
        [u for _, u in native],
        [r[lab]["steady_propulsion_W"] for lab, _ in native],
        ls="none",
        marker="s",
        ms=6,
        mfc="none",
        mec=MUTED,
        mew=1.2,
        label="native run, HoloOcean",
    )
    ax.set_xlabel("Head-on current (m/s)")
    ax.set_ylabel("Steady propulsion power (W)")
    ax.legend(fontsize=6, loc="upper left")
    save(
        fig,
        "FF2_current_drag_models",
        rows,
        "Station-keeping propulsion power of the 8-thruster BlueROV2 Heavy versus head-on current, "
        "under three published, mutually inconsistent surge-resistance descriptions (steady "
        "allocation, T200 tables at 15.5 V), with the native closed-loop steady values (HoloOcean "
        "drag). Points beyond the identified range or the thruster clamp are omitted.",
        ["final_runs.json", "sensitivity.json"],
    )


def fig_transit(r):
    labels = [
        ("calm", "EXP5-transit-c0"),
        ("0.2 m/s", "EXP5-transit-c0.2"),
        ("0.4 m/s", "EXP5-transit-c0.4"),
    ]
    cats = ["propulsion", "sensors", "compute", "battery_losses"]
    rows = []
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    bottom = [0.0] * len(labels)
    for k, cat in enumerate(cats):
        vals = [r[lab][f"{cat}_Wh"] for _, lab in labels]
        bars = ax.bar(
            range(len(labels)),
            vals,
            bottom=bottom,
            color=C[k],
            width=0.55,
            label=cat.replace("_", " "),
            edgecolor="#fcfcfb",
            linewidth=1,
        )
        bottom = [b + v for b, v in zip(bottom, vals, strict=True)]
        del bars
    for i, (name, lab) in enumerate(labels):
        run = r[lab]
        rows.append(
            {
                "case": name,
                "run": lab,
                **{f"{c}_Wh": run[f"{c}_Wh"] for c in cats},
                "damping_share_of_resistance": run["damping_share_of_resistance"],
            }
        )
        ax.text(
            i,
            bottom[i],
            f"damping {run['damping_share_of_resistance']:.0%}",
            ha="center",
            va="bottom",
            fontsize=6,
            color=MUTED,
        )
    ax.set_xticks(range(len(labels)), [n for n, _ in labels])
    ax.set_ylabel("Energy (Wh)")
    ax.legend(fontsize=6, loc="upper left")
    save(
        fig,
        "FF3_transit_categories",
        rows,
        "Energy of the same settled transit (out, stop, yaw, return, hold) by category at three "
        "head-on currents. 'damping' is the share of Unreal's ground-referenced linear damping in the "
        "time-mean resistance; it has no physical counterpart in current.",
        ["final_runs.json"],
    )


def fig_payload(r):
    pairs = [("inspection (S5)", "EXP6-S5-inspection"), ("AI vision (S6)", "EXP6-S6-ai")]
    rows = []
    fig, ax = plt.subplots(figsize=(3.6, 2.4))
    for k, mode in enumerate(("continuous", "scheduled")):
        vals = []
        for name, prefix in pairs:
            run = r[f"{prefix}-{mode}"]
            vals.append(run["terminal_Wh"])
            rows.append(
                {
                    "suite": name,
                    "mode": mode,
                    "terminal_Wh": run["terminal_Wh"],
                    "run": run["label"],
                }
            )
        bars = ax.bar(
            [i + (k - 0.5) * 0.3 for i in range(len(pairs))],
            vals,
            width=0.28,
            color=C[k],
            label=mode,
        )
        for b in bars:
            b.set_linewidth(0)
    base = r["EXP6-S0-propulsion-only"]["terminal_Wh"]
    rows.append(
        {
            "suite": "propulsion only (S0)",
            "mode": "-",
            "terminal_Wh": base,
            "run": "EXP6-S0-propulsion-only",
        }
    )
    ax.axhline(base, color=MUTED, lw=1, ls="--")
    ax.text(1.45, base, "propulsion only", ha="right", va="bottom", fontsize=6, color=MUTED)
    ax.set_xticks(range(len(pairs)), [n for n, _ in pairs])
    ax.set_ylabel("Mission energy (Wh)")
    ax.legend(fontsize=6, loc="upper right")
    save(
        fig,
        "FF4_payload_scheduling",
        rows,
        "Mission energy on the 0.2 m/s transit with the payload powered for the whole mission or only "
        "in the inspection phases (stop, hold, yaw). The sonar's step-up converter is unconfigured, so "
        "the inspection values are lower bounds with respect to conversion loss.",
        ["final_runs.json"],
    )


def fig_acoustic(sens):
    rows = [r for r in sens["part2_acoustic_modem"]["rows"] if r["strategy"] == "direct"]
    fig, ax = plt.subplots(figsize=(3.6, 2.6))
    variants = [
        ("DESERT PHY as simulated", "RS-232"),
        ("DESERT PHY as simulated", "Ethernet"),
        ("device bitrate (payload bits only)", "RS-232"),
        ("device bitrate (payload bits only)", "Ethernet"),
    ]
    for k, (airtime, iface) in enumerate(variants):
        pts = sorted(
            (r["tx_W"], r["share_of_terminal"])
            for r in rows
            if r["airtime"] == airtime and r["interface"] == iface
        )
        ax.plot(
            [p[0] for p in pts],
            [100 * p[1] for p in pts],
            color=C[k],
            marker="o",
            ms=4,
            label=f"{airtime.split(' (')[0]}, {iface}",
        )
    sim = next(r for r in rows if r["as_simulated"])
    ax.plot(
        [sim["tx_W"]],
        [100 * sim["share_of_terminal"]],
        ls="none",
        marker="o",
        ms=9,
        mfc="none",
        mec=MUTED,
        mew=1.2,
    )
    ax.annotate(
        "as simulated",
        (sim["tx_W"], 100 * sim["share_of_terminal"]),
        xytext=(10, 4),
        textcoords="offset points",
        fontsize=6,
        color=MUTED,
    )
    ax.set_xlabel("Published TX power setting (W)")
    ax.set_ylabel("Modem share of mission energy (%)")
    ax.legend(fontsize=6)
    save(
        fig,
        "FF5_acoustic_share_sensitivity",
        rows,
        "Share of the acoustic modem (EvoLogics S2C M 18/34, direct link, 2 s period) in the energy of "
        "the 0.2 m/s transit, recomputed from the simulated state durations for every published TX "
        "setting, RS-232 or Ethernet interface, and airtime from the DESERT PHY or the device bitrate. "
        "RX/listen at the published upper bound; 24 V conversion not modelled.",
        ["sensitivity.json", "crosslayer.json"],
    )


def fig_crosslayer(cross):
    order = ["direct", "ack", "multihop", "flooding", "relay-vehicle", "relay-fixed", "optical"]
    rows = []
    fig, ax = plt.subplots(figsize=(4.6, 2.6))
    for k, (key, label) in enumerate(
        (("vehicle_modem_Wh_on_bus", "vehicle"), ("network_wide_modem_Wh", "all nodes"))
    ):
        vals = []
        for s in order:
            n = cross["results"][s]["network"]
            vals.append(n[key])
            if k == 0:
                rows.append(
                    {
                        "strategy": s,
                        "vehicle_modem_Wh": n["vehicle_modem_Wh_on_bus"],
                        "network_wide_modem_Wh": n["network_wide_modem_Wh"],
                        "delivered": n["delivered"],
                        "generated": n["generated"],
                    }
                )
        bars = ax.bar(
            [i + (k - 0.5) * 0.36 for i in range(len(order))],
            vals,
            width=0.34,
            color=C[k],
            label=label,
        )
        for b in bars:
            b.set_linewidth(0)
    ax.set_xticks(range(len(order)), order, rotation=25, ha="right")
    ax.set_ylabel("Modem energy (Wh)")
    ax.legend(fontsize=6, loc="upper left")
    save(
        fig,
        "FF6_crosslayer_strategies",
        rows,
        "Modem energy on the vehicle and over all nodes for each communication strategy on the same "
        "0.2 m/s transit (one seed per strategy). Relays move energy from the vehicle to other nodes.",
        ["crosslayer.json"],
    )


def main(argv=None):
    import argparse
    import subprocess

    global OUT
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=OUT)
    OUT = parser.parse_args(argv).output_dir

    r = runs()
    sens = load("sensitivity.json")
    cross = load("crosslayer.json")
    fig_layouts(r)
    fig_current(r, sens)
    fig_transit(r)
    fig_payload(r)
    fig_acoustic(sens)
    fig_crosslayer(cross)
    MANIFEST["code_commit"] = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT, check=False
    ).stdout.strip()
    MANIFEST["result_commits"] = {
        "native": load("final_runs.json")["commits"],
        "crosslayer": cross["git"]["commit"],
        "comm_matrix": load("comm_matrix.json")["git"]["commit"],
    }
    (OUT / "manifest.json").write_text(json.dumps(MANIFEST, indent=2) + "\n", encoding="utf-8")
    print(f"{len(MANIFEST['figures'])} figures -> {OUT}")


if __name__ == "__main__":
    main()
