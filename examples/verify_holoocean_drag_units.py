"""Controlled native force audit, with no controller and no HoloEnergy wrapper."""

import argparse
import csv
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_holoocean_drag import (  # noqa: E402
    classify,
    drag_force_N,
    file_hash,
    git_info,
    predicted_velocity,
    runtime_provenance,
    source_parameters,
    write_json,
)
from tools.holoocean_backend import make_env  # noqa: E402


def scenario(tps):
    return {
        "name": "Native drag implementation audit",
        "package_name": "Ocean",
        "world": "SimpleUnderwater",
        "main_agent": "rov0",
        "ticks_per_sec": tps,
        "frames_per_sec": False,
        "agents": [
            {
                "agent_name": "rov0",
                "agent_type": "BlueROV2",
                "control_scheme": 0,
                "location": [0, 0, -5],
                "rotation": [0, 0, 0],
                "sensors": [
                    {"sensor_type": "PoseSensor"},
                    {"sensor_type": "VelocitySensor"},
                    {"sensor_type": "CollisionSensor"},
                    {
                        "sensor_type": "DynamicsSensor",
                        "configuration": {"UseCOM": True, "UseRPY": True},
                    },
                ],
            }
        ],
    }


def cases():
    result = [{"name": "neutral_zero", "current": [0, 0, 0]}]
    result += [{"name": f"current_x_{u:g}", "current": [u, 0, 0]} for u in (0.1, 0.2, 0.4, 0.8)]
    result += [{"name": "current_x_negative", "current": [-0.4, 0, 0]}]
    for axis in (1, 2):
        for sign in (-1, 1):
            current = [0, 0, 0]
            current[axis] = sign * 0.4
            result.append({"name": f"current_{axis}_{sign}", "current": current})
    result.append({"name": "yaw90_world_current", "current": [0.4, 0, 0], "yaw_deg": 90})
    for axis in range(3):
        result.append({"name": f"thrust_{axis}_10N", "current": [0, 0, 0], "thrust_axis": axis})
    result += [
        {"name": "gravity_air", "current": [0, 0, 0], "in_air": True},
        {"name": "moving_zero_current", "current": [0, 0, 0], "initial_velocity": [0.4, 0, 0]},
        {
            "name": "moving_matched_current",
            "current": "match_velocity",
            "initial_velocity": [0.4, 0, 0],
        },
    ]
    return result


def autodrag_cases():
    """Moving vehicle in still water, plus the absolute force references of the audit."""
    result = [
        {"name": "neutral_zero", "current": [0, 0, 0]},
        {"name": "thrust_0_10N", "current": [0, 0, 0], "thrust_axis": 0},
        {"name": "gravity_air", "current": [0, 0, 0], "in_air": True},
    ]
    for speed in (0.2, 0.4, 0.8):
        result.append(
            {
                "name": f"autodrag_x_{speed:g}",
                "current": [0, 0, 0],
                "initial_velocity": [speed, 0, 0],
            }
        )
    for axis in range(3):
        for sign in (-1, 1):
            if axis == 0 and sign == 1:
                continue
            velocity = [0, 0, 0]
            velocity[axis] = sign * 0.4
            result.append(
                {
                    "name": f"autodrag_{axis}_{sign}",
                    "current": [0, 0, 0],
                    "initial_velocity": velocity,
                }
            )
    result.append(
        {
            "name": "autodrag_yaw90_world_x",
            "current": [0, 0, 0],
            "initial_velocity": [0.4, 0, 0],
            "yaw_deg": 90,
        }
    )
    return result


CASE_SETS = {"standard": cases, "autodrag": autodrag_cases}


def thrust_action(axis):
    if axis == 2:
        return [2.5] * 4 + [0] * 4
    value = 10 / (2 * math.sqrt(2))
    return [0] * 4 + ([value] * 4 if axis == 0 else [value, -value, value, -value])


def norm(values):
    return math.sqrt(sum(v * v for v in values))


def projected_scale(observed, expected):
    """Least-squares scale s minimizing |observed - s * expected|; None without drag."""
    magnitude = norm(expected)
    if magnitude <= 1e-9:
        return None
    return sum(a * b for a, b in zip(observed, expected, strict=True)) / magnitude**2


def run_case(env, case, parameters, tps, trial, steps):
    import numpy as np

    zero = np.zeros(8)
    env.reset()
    initial_velocity = case.get("initial_velocity", [0, 0, 0])
    env.set_ocean_currents("rov0", list(initial_velocity))
    env.agents["rov0"].set_physics_state(
        np.array([0, 0, -5]),
        np.array([0, 0, case.get("yaw_deg", 0)]),
        np.array(initial_velocity),
        np.zeros(3),
    )
    previous = env.step(zero)
    # Prime sensor derivative caches after teleport; no initialization jump is
    # interpreted as a physical acceleration. Public state arrays are copied.
    v0 = previous["DynamicsSensor"][3:6].astype(float).tolist()
    t0 = float(previous["t"])
    current = v0 if case["current"] == "match_velocity" else case["current"]
    env.set_ocean_currents("rov0", current)
    if case.get("in_air"):
        env.agents["rov0"].set_physics_state(
            np.array([0, 0, 20]), np.zeros(3), np.zeros(3), np.zeros(3)
        )
        v0 = [0, 0, 0]
    thrust = [0.0, 0.0, 0.0]
    if "thrust_axis" in case:
        thrust[case["thrust_axis"]] = 10
        action = np.array(thrust_action(case["thrust_axis"]))
    else:
        action = zero
    rows = []
    dt = 1 / tps
    damping_gain = max(0, 1 - parameters["linear_damping_per_s"] * dt)
    if damping_gain <= 0:
        raise ValueError("Audit needs a positive integration/damping gain")
    for step in range(steps):
        state = env.step(action)
        d = state["DynamicsSensor"].astype(float)
        velocity = d[3:6].tolist()
        time = float(state["t"])
        delta_t = time - t0
        if not math.isclose(delta_t, dt, abs_tol=1e-9):
            raise ValueError(f"Timestamp increment {delta_t} differs from configured {dt}")
        acceleration = [(v - old) / delta_t for v, old in zip(velocity, v0, strict=True)]
        gravity = [0, 0, -parameters["mass_kg"] * 9.8] if case.get("in_air") else [0, 0, 0]
        expected_drag = [0, 0, 0] if case.get("in_air") else drag_force_N(v0, current, parameters)
        reconstructed = [
            parameters["mass_kg"] * (v / damping_gain - old) / delta_t
            for v, old in zip(velocity, v0, strict=True)
        ]
        observed_drag = [f - t - g for f, t, g in zip(reconstructed, thrust, gravity, strict=True)]
        applied_model_force = [
            t + g + parameters["source_drag_scale_to_SI"] * drag
            for t, g, drag in zip(thrust, gravity, expected_drag, strict=True)
        ]
        predicted = predicted_velocity(v0, applied_model_force, dt, parameters)
        row = {
            "case": case["name"],
            "trial": trial,
            "ticks_per_sec": tps,
            "step": step,
            "time_s": time,
            "dt_s": delta_t,
            "current_m_s": list(current),
            "velocity_before_m_s": list(v0),
            "velocity_m_s": velocity,
            "position_m": d[6:9].tolist(),
            "angular_velocity_rad_s": d[12:15].tolist(),
            "rpy_deg": d[15:18].tolist(),
            "acceleration_fd_m_s2": acceleration,
            "acceleration_sensor_m_s2": d[:3].tolist(),
            "force_ma_N": [parameters["mass_kg"] * a for a in acceleration],
            "force_reconstructed_N": reconstructed,
            "thrust_reference_N": thrust,
            "expected_drag_N": expected_drag,
            "observed_drag_N": observed_drag,
            "predicted_source_velocity_m_s": predicted,
            "source_prediction_velocity_error_m_s": norm(
                [v - p for v, p in zip(velocity, predicted, strict=True)]
            ),
            "damping_gain": damping_gain,
            "collision": bool(np.any(state["CollisionSensor"])),
        }
        if not all(math.isfinite(x) for x in velocity + acceleration + reconstructed):
            raise ValueError("Nonfinite runtime observation")
        rows.append(row)
        v0, t0 = velocity, time
    first = rows[0]
    first_summary = {
        **first,
        "observed_expected_scale": projected_scale(
            first["observed_drag_N"], first["expected_drag_N"]
        ),
        "step_observed_expected_scales": [
            projected_scale(r["observed_drag_N"], r["expected_drag_N"]) for r in rows
        ],
        "maximum_angular_velocity_rad_s": max(norm(r["angular_velocity_rad_s"]) for r in rows),
        "any_collision": any(r["collision"] for r in rows),
        "maximum_sensor_fd_error_m_s2": max(
            norm(
                [
                    a - b
                    for a, b in zip(
                        r["acceleration_fd_m_s2"], r["acceleration_sensor_m_s2"], strict=True
                    )
                ]
            )
            for r in rows
        ),
        "maximum_source_prediction_error_m_s": max(
            r["source_prediction_velocity_error_m_s"] for r in rows
        ),
    }
    return rows, first_summary


def family_summary(rows):
    """First-pulse and every-step drag scales of one family of drag cases."""
    if not rows:
        return None
    first = [r["observed_expected_scale"] for r in rows if r["observed_expected_scale"] is not None]
    steps = [s for r in rows for s in r.get("step_observed_expected_scales", []) if s is not None]
    summary = {
        "cases": sorted({r["case"] for r in rows}),
        "first_pulse_records": len(first),
        "first_pulse_scale_mean": statistics.mean(first),
        "first_pulse_scale_min": min(first),
        "first_pulse_scale_max": max(first),
        "first_pulse_scale_stdev": statistics.stdev(first) if len(first) > 1 else 0.0,
        "maximum_source_prediction_error_m_s": max(
            r["maximum_source_prediction_error_m_s"] for r in rows
        ),
    }
    if steps:
        summary |= {
            "step_observations": len(steps),
            "step_scale_mean": statistics.mean(steps),
            "step_scale_min": min(steps),
            "step_scale_max": max(steps),
        }
    return summary


def evaluate(records, parameters):
    currents = [
        r
        for r in records
        if r["case"].startswith("current_x_") and r["case"] != "current_x_negative"
    ]
    signed = [
        r
        for r in records
        if r["case"] in ("current_x_negative", "yaw90_world_current")
        or r["case"].startswith(("current_1_", "current_2_"))
    ]
    autodrag = [
        r
        for r in records
        if r["case"] == "moving_zero_current" or r["case"].startswith("autodrag_")
    ]
    # Classification uses the current magnitudes, as in the decisive campaign; an
    # autodrag-only campaign uses its +X speed series instead.
    primary = currents or [r for r in autodrag if r["case"].startswith("autodrag_x_")]
    scales = [r["observed_expected_scale"] for r in primary]
    refs = [r for r in records if r["case"].startswith("thrust_")]
    thrust_errors = [
        norm(
            [
                a - b
                for a, b in zip(r["force_reconstructed_N"], r["thrust_reference_N"], strict=True)
            ]
        )
        for r in refs
    ]
    dry = [r for r in records if r["case"] == "gravity_air"]
    gravity_errors = [abs(r["force_reconstructed_N"][2] / parameters["mass_kg"] + 9.8) for r in dry]
    quiet = [r for r in records if r["case"] == "neutral_zero"]
    checks = {
        "thrust_10N_absolute_error_below_0_05N": max(thrust_errors) < 0.05,
        "gravity_default_9_8_error_below_0_02_m_s2": max(gravity_errors) < 0.02,
        "neutral_zero_motion_below_1e_6_m_s": max(norm(r["velocity_m_s"]) for r in quiet) < 1e-6,
        "no_collisions": not any(r["any_collision"] for r in records),
        "sensor_delta_time_consistent_with_timestamp": max(
            r["maximum_sensor_fd_error_m_s2"] for r in records
        )
        < 1e-3,
        "angular_motion_below_1e_4_rad_s": max(r["maximum_angular_velocity_rad_s"] for r in records)
        < 1e-4,
    }
    scale = statistics.mean(scales)
    doubling = []
    for tps, trial in sorted({(r["ticks_per_sec"], r["trial"]) for r in primary}):
        ordered = sorted(
            [r for r in primary if (r["ticks_per_sec"], r["trial"]) == (tps, trial)],
            key=lambda r: norm(
                [v - c for v, c in zip(r["velocity_before_m_s"], r["current_m_s"], strict=True)]
            ),
        )
        doubling.append(
            {
                "ticks_per_sec": tps,
                "trial": trial,
                "observed_force_ratios": [
                    norm(b["observed_drag_N"]) / norm(a["observed_drag_N"])
                    for a, b in zip(ordered, ordered[1:], strict=False)
                ],
            }
        )
    checks["quadratic_doubling_ratios_near_4"] = all(
        math.isclose(ratio, 4, rel_tol=0.01)
        for r in doubling
        for ratio in r["observed_force_ratios"]
    )
    return {
        "case": classify(scale, all(checks.values()), parameters),
        "observed_expected_scale_mean": scale,
        "scale_min": min(scales),
        "scale_max": max(scales),
        "references_verified": all(checks.values()),
        "checks": checks,
        "max_thrust_reference_error_N": max(thrust_errors),
        "max_gravity_error_m_s2": max(gravity_errors),
        "quadratic_doubling": doubling,
        "drag_families": {
            "current_x_magnitudes": family_summary(currents),
            "signed_axes_and_yaw": family_summary(signed),
            "autodrag_still_water": family_summary(autodrag),
        },
        "force_reconstruction": "m*(v_next/(1-linear_damping*dt)-v_before)/dt; known UE5.3 integrator, no physical fitting",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--binary",
        type=Path,
        help="Executable of a separately built package (<package>/Windows/Holodeck/Binaries/"
        "Win64/Holodeck.exe); launched with the same parameters as holoocean.make",
    )
    parser.add_argument("--ticks-per-sec", nargs="+", type=int, default=[60, 100, 200])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--steps-per-case", type=int, default=8)
    parser.add_argument("--case-set", choices=sorted(CASE_SETS), default="standard")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs/drag_audit")
    args = parser.parse_args()
    if min(args.ticks_per_sec) < 2 or args.repeats <= 0 or args.steps_per_case < 2:
        parser.error("Positive repeats, >=2 steps and >=2 ticks/s required")
    case_list = CASE_SETS[args.case_set]()

    audit = source_parameters(args.source_dir)
    params = audit["parameters"]
    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "holoenergy_repository": git_info(ROOT),
        "tooling_sha256": {
            relative: file_hash(ROOT / relative)
            for relative in (
                "examples/verify_holoocean_drag_units.py",
                "tools/audit_holoocean_drag.py",
                "tools/holoocean_backend.py",
            )
        },
        "case_set": args.case_set,
        "cases": case_list,
        "source": audit,
        "runtime": runtime_provenance(args.binary),
        "arguments": vars(args)
        | {
            "source_dir": str(args.source_dir),
            "binary": str(args.binary) if args.binary else None,
            "output_dir": str(args.output_dir),
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records, raw = [], []
    for tps in args.ticks_per_sec:
        definition = scenario(tps)
        write_json(args.output_dir / f"scenario_{tps}.json", definition)
        with make_env(definition, tps, args.binary) as env:
            for trial in range(args.repeats):
                for case in case_list:
                    rows, record = run_case(env, case, params, tps, trial, args.steps_per_case)
                    raw.extend(rows)
                    records.append(record)
                print(f"Completed {tps} Hz, repetition {trial + 1}/{args.repeats}", flush=True)
    path = args.output_dir / "raw.jsonl"
    path.write_text(
        "".join(json.dumps(row, allow_nan=False) + "\n" for row in raw), encoding="utf-8"
    )
    with (args.output_dir / "first_pulse.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(
            {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()}
            for row in records
        )
    result = {
        "scope": "physics implementation verification; not physical vehicle validation",
        "source_binary_identity": "behavioral agreement is not proof of exact build commit",
        "provenance": provenance,
        "result": evaluate(records, params),
        "result_by_tick_rate": {
            str(tps): evaluate([r for r in records if r["ticks_per_sec"] == tps], params)
            for tps in args.ticks_per_sec
        },
        "records": records,
        "raw_sha256": file_hash(path),
        "scenario_sha256": {
            str(tps): file_hash(args.output_dir / f"scenario_{tps}.json")
            for tps in args.ticks_per_sec
        },
    }
    write_json(args.output_dir / "report.json", result)
    print(json.dumps(result["result"], indent=2), flush=True)
    if result["result"]["case"] == "INCONCLUSIVE":
        raise SystemExit("Force-reference prerequisites unresolved; inspect raw outputs")


if __name__ == "__main__":
    main()
