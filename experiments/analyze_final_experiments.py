"""Summarise the final native runs (EXP3-EXP6, EXP8) into one table, without re-tuning anything.

For every run in <results-dir>/<EXP>/<label>.summary.json (written by run_final_experiments.py):

* energies by category, terminal and OCV work; steady-state propulsion (last 30 s, station plans);
* feasibility of the energy chain ("request met": no allocation residual, no native saturation, no
  derating, chain closure PASS) kept separate from tracking (final position error and speed are
  reported as numbers; no tolerance is imposed here);
* evidence shares (proxy, upper-bound) and the EnergyReport interval when present;
* Unreal linear damping versus quadratic drag (review B-07): from the 0.1 s trace, the time-mean
  force magnitudes m c |v| (world-frame velocity) and 1/2 rho Cd A |v - v_c|^2, per run and per
  phase, and the damping share of their sum. The 0.1 s sampling is a downsample of the 100 Hz run.

    uv run python experiments/analyze_final_experiments.py [--results-dir experiments/results/final/native]
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
from pathlib import Path

from holoenergy.evidence import default_registry

ROOT = Path(__file__).resolve().parents[1]
RESIDUAL_TOL = 1e-6


def constants():
    reg = default_registry()

    def v(rid):
        return reg.get(rid).si()

    k = 0.5 * v("holoocean_bluerov2.water_density") * v("holoocean_bluerov2.drag_coefficient")
    k *= v("holoocean_bluerov2.drag_area")
    return {
        "drag_k_N_s2_per_m2": k,
        "mass_kg": v("holoocean_bluerov2.mass"),
        "linear_damping_1_per_s": v("holoocean_bluerov2.linear_damping"),
    }


def norm(x):
    return math.sqrt(sum(c * c for c in x))


def trace_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def damping_split(rows, const):
    mc = const["mass_kg"] * const["linear_damping_1_per_s"]
    k = const["drag_k_N_s2_per_m2"]
    per_phase = {}
    for r in rows:
        v = r["com_velocity_m_s"]
        vr = [a - b for a, b in zip(v, r["current_m_s"], strict=True)]
        acc = per_phase.setdefault(r["phase"], [0.0, 0.0, 0])
        acc[0] += mc * norm(v)
        acc[1] += k * norm(vr) ** 2
        acc[2] += 1
    out = {}
    tot_d = tot_q = 0.0
    n = 0
    for phase, (d, q, count) in per_phase.items():
        out[phase] = {
            "mean_damping_force_N": d / count,
            "mean_drag_force_N": q / count,
            "damping_share": d / (d + q) if d + q > 0 else None,
        }
        tot_d, tot_q, n = tot_d + d, tot_q + q, n + count
    return {
        "mean_damping_force_N": tot_d / n if n else None,
        "mean_drag_force_N": tot_q / n if n else None,
        "damping_share": tot_d / (tot_d + tot_q) if tot_d + tot_q > 0 else None,
        "phases": out,
    }


def summarise(path, const):
    s = json.loads(path.read_text(encoding="utf-8"))
    spec, m, ev = s["spec"], s["metrics"], s["evidence"]
    rows = trace_rows(path.with_name(s["traces"]["downsampled_0.1s"]["path"]))
    last = rows[-1]
    min_derating = min(r["derating_factor"] for r in rows)
    request_met = (
        m["max_allocation_residual_norm"] < RESIDUAL_TOL
        and m["native_saturated_fraction"] == 0
        and min_derating >= 1.0
        and s["chain"]["status"] == "PASS"
    )
    steady_met = None
    if spec["plan"] == "station":
        window = s["provenance"]["steady_window_s"]
        t_end = rows[-1]["time_s"]
        tail = [r for r in rows if r["time_s"] >= t_end - window - 1e-9]
        steady_met = all(
            r["allocation_residual_norm"] < RESIDUAL_TOL
            and not r["allocation_saturated"]
            and not r["native_saturated"]
            and r["derating_factor"] >= 1.0
            for r in tail
        )
    intervals = s["energy_report"].get("intervals") or {}
    terminal_interval = intervals.get("terminal_energy_Wh") if isinstance(intervals, dict) else None
    damping = damping_split(rows, const)
    return {
        "label": spec["label"],
        "group": spec["group"],
        "layout": spec["layout"],
        "mapping": spec["mapping"],
        "geometry_grade": s["layout"]["geometry_grade"],
        "plan": spec["plan"],
        "current_m_s": spec["current_m_s"],
        "suite": spec.get("suite"),
        "schedule": spec.get("schedule"),
        "fidelity": spec.get("fidelity", "L1"),
        "initial_soc": (spec.get("battery") or {}).get("initial_soc"),
        "duration_s": m["duration_s"],
        "terminal_Wh": m["terminal_Wh"],
        "ocv_work_Wh": s["summary"]["total_ocv_work_Wh"],
        **{f"{k}_Wh": v for k, v in m["category_energy_Wh"].items()},
        "steady_propulsion_W": m["mean_tail_propulsion_W"] if spec["plan"] == "station" else None,
        "request_met": request_met,
        "steady_window_request_met": steady_met,
        "max_allocation_residual_N": m["max_allocation_residual_norm"],
        "native_saturated_fraction": m["native_saturated_fraction"],
        "allocation_saturated_fraction": m["allocation_saturated_fraction"],
        "min_derating_factor": min_derating,
        "battery_cutoff": any(r["battery_state"] == "CUTOFF" for r in rows),
        "min_voltage_V": min(r["voltage_V"] for r in rows),
        "chain_status": s["chain"]["status"],
        "final_tracking_error_m": m["final_tracking_error_m"],
        "final_speed_m_s": norm(last["com_velocity_m_s"]),
        "max_abs_roll_pitch_deg": m["max_abs_roll_pitch_deg"],
        "proxy_share_percent": ev.get("proxy_share_percent"),
        "upper_bound_share_percent": ev.get("upper_bound_share_percent"),
        "terminal_interval_Wh": terminal_interval,
        "damping_share_of_resistance": damping["damping_share"],
        "mean_damping_force_N": damping["mean_damping_force_N"],
        "mean_drag_force_N": damping["mean_drag_force_N"],
        "damping_by_phase": damping["phases"],
        "commit": s["provenance"]["git"].get("commit"),
        "dirty": s["provenance"]["git"].get("dirty"),
        "result_file": path.name,
        "summary_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--results-dir", type=Path, default=ROOT / "experiments/results/final/native"
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/results/final")
    args = parser.parse_args(argv)
    const = constants()
    runs = [summarise(p, const) for p in sorted(args.results_dir.glob("*/*.summary.json"))]
    commits = {r["commit"] for r in runs}
    out = {
        "constants": const,
        "runs": runs,
        "commits": sorted(c for c in commits if c),
        "single_commit": len(commits) == 1,
        "any_dirty": any(r["dirty"] for r in runs),
        "definitions": {
            "request_met": "whole run: max allocation residual < 1e-6 N, no native saturation, no "
            "derating, chain closure PASS; tracking is reported separately",
            "steady_window_request_met": "station plans, last steady_window_s of the 0.1 s trace: "
            "no allocation residual, no allocation or native saturation, no derating",
            "damping_share_of_resistance": "time-mean m c |v| / (m c |v| + 1/2 rho Cd A |v - v_c|^2) "
            "over the 0.1 s trace",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "final_runs.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    flat = [{k: v for k, v in r.items() if k != "damping_by_phase"} for r in runs]
    with (args.output_dir / "final_runs.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, list(flat[0]))
        writer.writeheader()
        writer.writerows(flat)
    print(f"{len(runs)} runs, commits {out['commits']}, dirty {out['any_dirty']}")
    for r in runs:
        steady = r["steady_propulsion_W"]
        print(
            f"{r['label']:34s} E={r['terminal_Wh']:.4f} Wh "
            f"steady={'-' if steady is None else f'{steady:6.1f}'} W met={r['request_met']!s:5s} "
            f"steady_met={r['steady_window_request_met']!s:5s} "
            f"err={r['final_tracking_error_m']:.3f} m damp={r['damping_share_of_resistance'] or 0:.2f}"
        )


if __name__ == "__main__":
    main()
