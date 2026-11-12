"""Tables, baselines and ablations from the native closed-loop campaign (no simulator).

Reads experiments/results/native/<group>/*.summary.json and the committed 0.1 s traces
(*.trace10.jsonl.gz) and writes experiments/results/native/tables/*.csv + analysis.json.

Baselines (calibration/validation split, never evaluated on their own fitting data):
  * speed-cubic  P_prop = a + b |u|^3, least squares on the CALM-WATER TRANSIT (N4 c=0);
  * constant     P_prop = mean propulsion power of the same calm-water transit;
both are evaluated on every other native run (station keeping in current, transits in
current), against HoloEnergy's actuator-effort propulsion energy of that run.

Ablations are the additive category decomposition of one native run (loads do not feed
back into the dynamics unless the power limit is reached, which is checked), plus the
separate native runs that change the model (L0 vs L1, current on/off).
"""

from __future__ import annotations

import csv
import gzip
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "experiments/results/native"
TABLES = NATIVE / "tables"
CALIBRATION = "N4-L8-HV-transit-c0"


def load():
    runs = {}
    for path in sorted(NATIVE.glob("N*/*.summary.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        runs[data["spec"]["label"]] = data | {"_dir": path.parent}
    return runs


def trace(run):
    path = run["_dir"] / run["traces"]["downsampled_0.1s"]["path"]
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def write_csv(name, rows):
    TABLES.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with (TABLES / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, keys)
        writer.writeheader()
        writer.writerows(rows)


def base_row(run):
    s, m, c, lay = run["spec"], run["metrics"], run["chain"], run["layout"]
    return {
        "run": s["label"],
        "layout": s["layout"],
        "mapping": s["mapping"],
        "geometry_grade": lay["geometry_grade"],
        "layout_rank": lay["layout_rank"],
        "current_m_s": math.hypot(*s["current_m_s"][:2]),
        "current_axis": "y" if abs(s["current_m_s"][1]) > 0 else "x",
        "plan": s["plan"],
        "propulsion_Wh": m["propulsion_Wh"],
        "terminal_Wh": m["terminal_Wh"],
        "battery_losses_Wh": m["battery_losses_Wh"],
        "mean_tail_tracking_error_m": m["mean_tail_tracking_error_m"],
        "max_tracking_error_m": m["max_tracking_error_m"],
        "max_abs_roll_pitch_deg": m["max_abs_roll_pitch_deg"],
        "mean_allocation_residual_norm": m["mean_allocation_residual_norm"],
        "allocation_saturated_fraction": m["allocation_saturated_fraction"],
        "native_saturated_fraction": m["native_saturated_fraction"],
        "max_backend_residual_norm": m["max_backend_residual_norm"],
        "peak_actuator_force_N": m["peak_actuator_force_N"],
        "peak_total_power_W": m["peak_total_power_W"],
        "mean_tail_propulsion_W": m["mean_tail_propulsion_W"],
        "final_soc": m["final_soc"],
        "peak_current_A": m["peak_current_A"],
        "min_voltage_V": m["min_voltage_V"],
        "min_derating_factor": m["min_derating_factor"],
        "derated_tick_fraction": m["derated_tick_fraction"],
        "chain_status": c["status"],
        "max_force_residual_N": max(c["max_abs_force_residual_N"]),
        "max_thruster_power_residual_W": c["max_abs_thruster_power_residual_W"],
        "max_wrench_equivalence_residual": c["wrench_equivalence"]["max_residual_norm"],
        "wrench_inconsistent_tick_fraction": c["wrench_equivalence"]["fraction_above_1e-6"],
        "real_time_factor": run["timing"]["real_time_factor"],
    }


def requested_feasible(run, tolerance=1e-3):
    """The request is met only if allocation, native clamp and power limit never cut it."""
    m = run["metrics"]
    return (
        m["max_allocation_residual_norm"] < tolerance
        and m["native_saturated_fraction"] == 0
        and m["derated_tick_fraction"] == 0
    )


def ground_speed(row):
    return abs(row["speed_m_s"])


def water_speed(row):
    """Speed through the water |v_com - current| (what drag and thrust actually see)."""
    return math.dist(row["com_velocity_m_s"], row["current_m_s"])


def fit_baselines(rows, speed=ground_speed):
    """Least squares P = a + b|u|^3 and the constant mean, on calibration rows only."""
    xs = [speed(r) ** 3 for r in rows]
    ys = [r["power_propulsion_W"] for r in rows]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx if sxx else 0.0
    a = my - b * mx
    return {"speed_cubic": {"a_W": a, "b_W_per_m3s3": b}, "constant": {"P_W": my}}


def baseline_energy(rows, params, dt=0.1, water=None):
    def cubic(p, speed):
        a, b = p["speed_cubic"]["a_W"], p["speed_cubic"]["b_W_per_m3s3"]
        return sum(a + b * speed(r) ** 3 for r in rows) * dt / 3600

    return {
        "speed_cubic_Wh": cubic(params, ground_speed),
        "speed_cubic_water_Wh": cubic(water, water_speed) if water else None,
        "constant_Wh": params["constant"]["P_W"] * len(rows) * dt / 3600,
        "trace_propulsion_Wh": sum(r["power_propulsion_W"] for r in rows) * dt / 3600,
    }


def main(argv=None):
    import argparse

    global NATIVE, TABLES
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--native-dir", type=Path, default=NATIVE, help="native results to read")
    parser.add_argument(
        "--tables-dir", type=Path, default=None, help="default: <native-dir>/tables"
    )
    args = parser.parse_args(argv)
    NATIVE = args.native_dir
    TABLES = args.tables_dir or NATIVE / "tables"
    runs = load()
    groups = {}
    for run in runs.values():
        groups.setdefault(run["spec"]["group"], []).append(
            base_row(run) | {"satisfies_wrench": requested_feasible(run)}
        )
    for group, rows in groups.items():
        write_csv(f"{group}.csv", rows)

    analysis = {"runs": len(runs), "chain_status": {}}
    for label, run in runs.items():
        analysis["chain_status"].setdefault(run["chain"]["status"], []).append(label)

    # Wrench-equivalence identity: L8-HV direct vs wrench-equivalent on the same native body.
    identity = []
    for c in ("0", "0.2", "0.5", "0.8"):
        a, b = runs.get(f"N1-L8-HV-direct-c{c}"), runs.get(f"N1-L8-HV-we-c{c}")
        if a and b:
            identity.append(
                {
                    "current_m_s": float(c),
                    "direct_propulsion_Wh": a["metrics"]["propulsion_Wh"],
                    "wrench_equivalent_propulsion_Wh": b["metrics"]["propulsion_Wh"],
                    "relative_difference": (
                        b["metrics"]["propulsion_Wh"] / a["metrics"]["propulsion_Wh"] - 1
                    )
                    if a["metrics"]["propulsion_Wh"]
                    else b["metrics"]["propulsion_Wh"],
                    "final_position_difference_m": None,
                }
            )
    write_csv("wrench_equivalence_identity.csv", identity)
    analysis["wrench_equivalence_identity"] = identity

    # Baselines with a calibration/validation split.
    if CALIBRATION in runs:
        cal = trace(runs[CALIBRATION])
        params = fit_baselines(cal)
        water = fit_baselines(cal, water_speed)  # identical speeds in calm water
        rows = []
        for label, run in runs.items():
            if label == CALIBRATION or run["spec"]["layout"] != "L8-HV" or run["spec"].get("suite"):
                continue
            if run["spec"].get("fidelity") or run["spec"].get("battery"):
                continue
            if run["spec"]["mapping"] != "direct":  # same runs through the virtual mapping
                continue
            t = trace(run)
            e = baseline_energy(t, params, water=water)
            ref = run["metrics"]["propulsion_Wh"]
            rows.append(
                {
                    "run": label,
                    "role": "hold-out comparison (model vs model)",
                    "plan": run["spec"]["plan"],
                    "current_m_s": math.hypot(*run["spec"]["current_m_s"][:2]),
                    "holoenergy_propulsion_Wh": ref,
                    "speed_cubic_Wh": e["speed_cubic_Wh"],
                    "constant_Wh": e["constant_Wh"],
                    "speed_cubic_relative_error": e["speed_cubic_Wh"] / ref - 1 if ref else None,
                    "speed_cubic_water_Wh": e["speed_cubic_water_Wh"],
                    "speed_cubic_water_relative_error": e["speed_cubic_water_Wh"] / ref - 1
                    if ref
                    else None,
                    "constant_relative_error": e["constant_Wh"] / ref - 1 if ref else None,
                    "trace_vs_summary_relative": e["trace_propulsion_Wh"] / ref - 1
                    if ref
                    else None,
                    "request_met": requested_feasible(run),
                }
            )
        e = baseline_energy(cal, params)
        rows.insert(
            0,
            {
                "run": CALIBRATION,
                "role": "calibration (fit)",
                "plan": "transit",
                "current_m_s": 0.0,
                "holoenergy_propulsion_Wh": runs[CALIBRATION]["metrics"]["propulsion_Wh"],
                "speed_cubic_Wh": e["speed_cubic_Wh"],
                "constant_Wh": e["constant_Wh"],
                "speed_cubic_relative_error": None,
                "constant_relative_error": None,
                "trace_vs_summary_relative": e["trace_propulsion_Wh"]
                / runs[CALIBRATION]["metrics"]["propulsion_Wh"]
                - 1,
            },
        )
        write_csv("baselines.csv", rows)
        analysis["baselines"] = {
            "calibration_run": CALIBRATION,
            "parameters_ground_speed": params,
            "parameters_water_speed": water,
            "note": "speed_cubic uses over-ground speed (blind to current); speed_cubic_water "
            "uses speed through the water. Both are fitted on the calm-water transit only.",
            "rows": rows,
        }

    # Ablation: category decomposition of the native transit in current + model switches.
    ref = runs.get("N4-L8-HV-transit-c0.2")
    if ref:
        cat = ref["metrics"]["category_energy_Wh"]
        layers, total = [], 0.0
        for name, key in (
            ("propulsion only", "propulsion"),
            ("+ sensors", "sensors"),
            ("+ compute", "compute"),
            ("+ auxiliaries", "auxiliaries"),
            ("+ communications", "communications"),
            ("+ battery internal losses", "battery_losses"),
        ):
            total += cat.get(key, 0.0)
            layers.append(
                {
                    "layer": name,
                    "category": key,
                    "category_Wh": cat.get(key, 0.0),
                    "cumulative_Wh": total,
                }
            )
        switches = []
        for label, what in (
            ("N6-L8-HV-L0-transit-c0.2", "L0 battery (bucket) instead of L1"),
            ("N4-L8-HV-transit-c0", "without environmental current"),
            ("N5-S0-propulsion-only-transit-c0.2", "no payload/avionics components (native run)"),
        ):
            if label in runs:
                m = runs[label]["metrics"]
                switches.append(
                    {
                        "variant": what,
                        "run": label,
                        "terminal_Wh": m["terminal_Wh"],
                        "battery_losses_Wh": m["battery_losses_Wh"],
                        "propulsion_Wh": m["propulsion_Wh"],
                        "relative_to_reference_terminal": m["terminal_Wh"]
                        / ref["metrics"]["terminal_Wh"]
                        - 1,
                    }
                )
        write_csv("ablation_layers.csv", layers)
        write_csv("ablation_switches.csv", switches)
        analysis["ablation"] = {
            "reference_run": "N4-L8-HV-transit-c0.2",
            "reference_min_derating_factor": ref["metrics"]["min_derating_factor"],
            "layers": layers,
            "switches": switches,
        }
    (TABLES / "analysis.json").write_text(
        json.dumps(analysis, indent=2, default=str) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {k: (v if k != "baselines" else "...") for k, v in analysis.items()},
            indent=1,
            default=str,
        )[:3000]
    )


if __name__ == "__main__":
    main()
