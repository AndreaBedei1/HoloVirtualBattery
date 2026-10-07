"""Close the chain from the HoloOcean drag equation to HoloEnergy electrical demand.

Input: per-tick traces of examples/native_current_energy_study.py (--trace-every 1) on a
native backend. For every tick, with nothing fitted:

1. drag from the HoloOcean source equation at the start-of-step relative velocity, times
   the drag scale of that source (1 when DragForce *= UEUnitsPerMeter is present, else 0.01);
2. thruster force from the efforts HoloEnergy applied, the BlueROV2 geometry of the source
   and the measured attitude;
3. net force inferred from the runtime centre-of-mass velocity change with the verified
   physics step, F = m (v1 / (1 - c dt) - v0) / dt (UE 5.3 Euler step, then ether damping);
4. per-thruster electrical power recomputed from the T200 profile tables with an
   independent piecewise-linear interpolation (force, then voltage) at the logged bus
   voltage, and propulsion energy integrated over the verified step.

The force residual F_runtime - (F_thrusters + F_drag) closes the mechanical part of the
chain inside the closed loop; the power and energy residuals close the electrical part.
The residual assuming the SI drag (scale 1) is also reported, so a backend that applies a
different scale is visible. Neutral buoyancy (net gravity + buoyancy = 0) is assumed and
checked by the vertical residual.
"""

import argparse
import gzip
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
from native_current_energy_study import THRUSTER_DIRECTIONS  # noqa: E402

from tools.audit_holoocean_drag import (  # noqa: E402
    drag_force_N,
    file_hash,
    source_parameters,
)

FORCE_TOLERANCE_N = 1e-3
POWER_TOLERANCE_W = 1e-6
ENERGY_RELATIVE_TOLERANCE = 1e-9


def rotation(rpy_deg):
    """World-from-body rotation R = Rz(yaw) Ry(pitch) Rx(roll), HoloOcean RPY in degrees."""
    r, p, y = (math.radians(a) for a in rpy_deg)
    cr, sr, cp, sp, cy, sy = (
        math.cos(r),
        math.sin(r),
        math.cos(p),
        math.sin(p),
        math.cos(y),
        math.sin(y),
    )
    return [
        [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr],
        [sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr],
        [-sp, cp * sr, cp * cr],
    ]


def thruster_force_world(applied_N, rpy_deg):
    body = [
        sum(f * d[axis] for f, d in zip(applied_N, THRUSTER_DIRECTIONS, strict=True))
        for axis in range(3)
    ]
    return [sum(row[j] * body[j] for j in range(3)) for row in rotation(rpy_deg)]


def runtime_force(v0, v1, dt, parameters):
    gain = 1 - parameters["linear_damping_per_s"] * dt
    return [parameters["mass_kg"] * (b / gain - a) / dt for a, b in zip(v0, v1, strict=True)]


def interp(points, x):
    """Piecewise linear, clamped at the ends (independent of holoenergy._validation)."""
    xs, ys = zip(*points, strict=True)
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        if x0 <= x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    raise AssertionError("unreachable")


class T200Tables:
    """Force -> power per direction and voltage, from the profile rows (max power per force)."""

    def __init__(self, profile):
        self.tables = []
        for table in profile["voltage_tables"]:
            curves = {}
            for direction in ("forward", "reverse"):
                best = {}
                for row in table[direction]:
                    best[row["force_N"]] = max(best.get(row["force_N"], 0.0), row["power_W"])
                curves[direction] = sorted(best.items())
            self.tables.append((table["voltage_V"], curves))

    def power(self, force_N, voltage_V):
        if force_N == 0:
            return 0.0
        direction = "forward" if force_N > 0 else "reverse"
        values = [(v, interp(c[direction], abs(force_N))) for v, c in self.tables]
        exact = [p for v, p in values if abs(v - voltage_V) < 1e-9]
        return exact[0] if exact else interp(values, voltage_V)


def close_trace(rows, parameters, scale, tables, dt):
    worst = {"force_N": [0.0] * 3, "force_si_N": [0.0] * 3, "power_W": 0.0, "propulsion_W": 0.0}
    peak = {"drag_N": 0.0, "thrust_N": 0.0, "runtime_force_N": 0.0}
    sum_sq = [0.0] * 3
    for a, b in zip(rows, rows[1:], strict=False):
        if abs(b["t_s"] - a["t_s"] - dt) > 1e-9:
            raise ValueError("trace is not per tick; run the study with --trace-every 1")
        drag_si = drag_force_N(a["com_velocity_m_s"], b["current_m_s"], parameters)
        thrust = thruster_force_world(b["applied_N"], a["rpy_deg"])
        measured = runtime_force(a["com_velocity_m_s"], b["com_velocity_m_s"], dt, parameters)
        for axis in range(3):
            residual = measured[axis] - (thrust[axis] + scale * drag_si[axis])
            residual_si = measured[axis] - (thrust[axis] + drag_si[axis])
            worst["force_N"][axis] = max(worst["force_N"][axis], abs(residual))
            worst["force_si_N"][axis] = max(worst["force_si_N"][axis], abs(residual_si))
            sum_sq[axis] += residual * residual
        peak["drag_N"] = max(peak["drag_N"], scale * math.hypot(*drag_si))
        peak["thrust_N"] = max(peak["thrust_N"], math.hypot(*thrust))
        peak["runtime_force_N"] = max(peak["runtime_force_N"], math.hypot(*measured))
    for row in rows:
        powers = [tables.power(f, row["voltage_V"]) for f in row["applied_N"]]
        worst["power_W"] = max(
            worst["power_W"],
            *(abs(p - q) for p, q in zip(powers, row["thruster_power_W"], strict=True)),
        )
        worst["propulsion_W"] = max(
            worst["propulsion_W"], abs(sum(powers) - row["power_propulsion_W"])
        )
    ticks = len(rows) - 1
    return {
        "force_steps": ticks,
        "max_abs_force_residual_N": worst["force_N"],
        "rms_force_residual_N": [math.sqrt(s / ticks) for s in sum_sq],
        "max_abs_force_residual_assuming_SI_drag_N": worst["force_si_N"],
        "peak_drag_N": peak["drag_N"],
        "peak_thrust_N": peak["thrust_N"],
        "peak_runtime_force_N": peak["runtime_force_N"],
        "max_abs_thruster_power_residual_W": worst["power_W"],
        "max_abs_propulsion_power_residual_W": worst["propulsion_W"],
        "propulsion_Wh_from_trace": sum(r["power_propulsion_W"] for r in rows) * dt / 3600,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True, help="study output directory")
    parser.add_argument("--report", required=True, help="study report file name in --run-dir")
    parser.add_argument(
        "--source-dir", type=Path, required=True, help="HoloOcean checkout of the build"
    )
    parser.add_argument(
        "--profile",
        type=Path,
        default=ROOT / "holoenergy/profiles/thrusters/bluerobotics_t200.json",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = source_parameters(args.source_dir)
    parameters = audit["parameters"]
    scale = parameters["source_drag_scale_to_SI"]
    report = json.loads((args.run_dir / args.report).read_text(encoding="utf-8"))
    tables = T200Tables(json.loads(args.profile.read_text(encoding="utf-8")))
    results = {}
    for name, record in report["records"].items():
        trace_path = args.run_dir / f"{name}.trace.jsonl.gz"
        with gzip.open(trace_path, "rt", encoding="utf-8") as handle:
            rows = [json.loads(line) for line in handle]
        dt = record["physics_dt_s"]
        result = close_trace(rows, parameters, scale, tables, dt)
        result["propulsion_Wh_reported"] = record["propulsion_Wh"]
        result["propulsion_Wh_relative_difference"] = (
            result["propulsion_Wh_from_trace"] / record["propulsion_Wh"] - 1
            if record["propulsion_Wh"]
            else result["propulsion_Wh_from_trace"]
        )
        result["trace_sha256"] = file_hash(trace_path)
        result["status"] = (
            "PASS"
            if max(result["max_abs_force_residual_N"]) < FORCE_TOLERANCE_N
            and result["max_abs_thruster_power_residual_W"] < POWER_TOLERANCE_W
            and abs(result["propulsion_Wh_relative_difference"]) < ENERGY_RELATIVE_TOLERANCE
            else "FAIL"
        )
        results[name] = result
        print(
            f"{result['status']} {name}: max force residual "
            f"{max(result['max_abs_force_residual_N']):.2e} N (peak drag {result['peak_drag_N']:.2f} N, "
            f"assuming SI drag {max(result['max_abs_force_residual_assuming_SI_drag_N']):.2e} N); "
            f"power {result['max_abs_thruster_power_residual_W']:.1e} W; "
            f"energy {result['propulsion_Wh_relative_difference']:.1e}",
            flush=True,
        )
    output = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "implementation chain closure on a closed-loop native run; not vehicle validation",
        "chain": [
            "HoloOcean drag equation (source literals)",
            "SI units -> UE force (source drag scale)",
            "runtime acceleration (centre-of-mass velocity change, verified physics step)",
            "applied actuator effort (HoloEnergy applied action, BlueROV2 geometry)",
            "HoloEnergy electrical demand (T200 tables at the logged bus voltage)",
        ],
        "source": {"root": audit["root"], "git": audit["git"], "files": audit["files"]},
        "parameters": parameters,
        "drag_scale_used": scale,
        "tolerances": {
            "force_N": FORCE_TOLERANCE_N,
            "thruster_power_W": POWER_TOLERANCE_W,
            "energy_relative": ENERGY_RELATIVE_TOLERANCE,
        },
        "study_report": {
            "path": str(args.run_dir / args.report),
            "sha256": file_hash(args.run_dir / args.report),
        },
        "profile_sha256": file_hash(args.profile),
        "records": results,
        "status": "PASS" if all(r["status"] == "PASS" for r in results.values()) else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Chain closure: {output['status']} -> {args.output}")
    return 0 if output["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
