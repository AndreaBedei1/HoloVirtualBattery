"""Independent energy recomputation and conservation checks for the final native runs.

For every run in <final-dir>/results/*/ with its per-tick trace in <final-dir>/full/:

* E = sum P dt recomputed from the per-tick rows for one thruster, total propulsion, one
  sensor, every category, battery losses (also as sum I^2 R dt for L1), and the bus
  (terminal) energy, compared with the framework's summary;
* conservation: bus energy = sum of the categories except battery losses; OCV work =
  bus + battery losses; sum over mission phases = total energy and duration.

Deterministic formulas must agree to near machine precision (relative 1e-9).

    python experiments/verify_final_energy.py [--final-dir logs/final] [--output ...]
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOL = 1e-9
CATEGORY_KEYS = {
    "propulsion": "power_propulsion_W",
    "sensors": "power_sensors_W",
    "compute": "power_compute_W",
    "communications": "power_communications_W",
    "auxiliaries": "power_auxiliary_W",
    "converters": "power_conversion_loss_W",
    "battery_losses": "power_battery_loss_W",
}


def rel(a, b):
    if abs(b) < 1e-15:
        return abs(a - b)
    return abs(a / b - 1)


def integrate(rows, key):
    return sum((r[key] or 0.0) * r["dt_s"] for r in rows) / 3600


def verify_run(summary, rows, resistance_ohm=None):
    s = summary["summary"]
    cats = s["category_energy_Wh"]
    checks = {}

    def check(name, recomputed, reported):
        checks[name] = {
            "recomputed_Wh": recomputed,
            "reported_Wh": reported,
            "relative_error": rel(recomputed, reported),
        }

    for cat, key in CATEGORY_KEYS.items():
        check(f"category.{cat}", integrate(rows, key), cats.get(cat, 0.0))
    check("bus_terminal", integrate(rows, "power_total_W"), s["terminal_energy_Wh"])
    devices = s.get("device_energy_Wh", {})
    actuator_ids = [k for k in devices if k in summary["layout"].get("configured_actuators", [])]
    if actuator_ids:
        first = actuator_ids[0]
        idx = summary["layout"]["configured_actuators"].index(first)
        check(
            f"thruster.{first}",
            sum(r["thruster_power_W"][idx] * r["dt_s"] for r in rows) / 3600,
            devices[first],
        )
        check(
            "thrusters.sum_vs_propulsion",
            sum(sum(r["thruster_power_W"]) * r["dt_s"] for r in rows) / 3600,
            cats["propulsion"],
        )
    comps = sorted({k for r in rows for k in r["component_power_W"]})
    for name in comps:
        recomputed = sum(r["component_power_W"].get(name, 0.0) * r["dt_s"] for r in rows) / 3600
        if name in devices:
            check(f"component.{name}", recomputed, devices[name])
    # Conservation.
    bus_from_categories = sum(v for k, v in cats.items() if k != "battery_losses")
    check("conservation.bus_equals_categories", bus_from_categories, s["terminal_energy_Wh"])
    check(
        "conservation.ocv_equals_bus_plus_losses",
        s["terminal_energy_Wh"] + cats.get("battery_losses", 0.0),
        s["total_ocv_work_Wh"],
    )
    if resistance_ohm:
        check(
            "battery_losses.I2R",
            sum(r["current_A"] ** 2 * resistance_ohm * r["dt_s"] for r in rows) / 3600,
            cats.get("battery_losses", 0.0),
        )
    phases = s.get("phases") or {}
    if phases:
        check(
            "phases.sum_terminal",
            sum(p["terminal_energy_Wh"] for p in phases.values()),
            s["terminal_energy_Wh"],
        )
        dur = sum(p["duration_s"] for p in phases.values())
        checks["phases.sum_duration"] = {
            "recomputed_s": dur,
            "reported_s": len(rows) * rows[0]["dt_s"],
            "relative_error": rel(dur, len(rows) * rows[0]["dt_s"]),
        }
    worst = max(c["relative_error"] for c in checks.values())
    return {
        "checks": checks,
        "worst_relative_error": worst,
        "status": "PASS" if worst < TOL else "FAIL",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--final-dir", type=Path, default=ROOT / "logs/final")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/final/energy_verification.json"
    )
    args = parser.parse_args(argv)
    out = {"tolerance_relative": TOL, "runs": {}}
    for path in sorted((args.final_dir / "results").glob("*/*.summary.json")):
        summary = json.loads(path.read_text(encoding="utf-8"))
        label = summary["spec"]["label"]
        trace = args.final_dir / "full" / f"{label}.trace.jsonl.gz"
        if not trace.exists():
            out["runs"][label] = {"status": "NO_TRACE"}
            continue
        with gzip.open(trace, "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        battery = summary.get("battery") or {}
        resistance = (
            battery.get("internal_resistance_ohm") if battery.get("model") == "rint" else None
        )
        out["runs"][label] = verify_run(summary, rows, resistance)
        print(
            f"{out['runs'][label]['status']} {label}: worst relative error {out['runs'][label]['worst_relative_error']:.1e}"
        )
    out["status"] = (
        "PASS"
        if out["runs"] and all(r["status"] == "PASS" for r in out["runs"].values())
        else "FAIL"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(out["status"])
    return 0 if out["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
