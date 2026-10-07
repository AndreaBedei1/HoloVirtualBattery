"""Native HoloOcean timestep audit: client clock versus effective physics step.

For each ``ticks_per_sec`` the client clock advances 1/tps per tick. Independent
references estimate the step actually integrated by the UE 5.3 Chaos solver
(``V += a*dt; V *= max(0, 1 - c*dt); X += V*dt``):

* gravity in air (velocity recursion, any initial velocity);
* known 10 N net thruster force in water, first step from rest (no drag at rest);
* linear-damping ratio of a body moving horizontally in air (mass/force free);
* kinematics ``x[n+1] - x[n] = v[n+1] * dt`` (mass/force/damping free);

and the world tick DeltaTime from the DynamicsSensor (acceleration = dv/DeltaTime).
Optionally, still-water deceleration from a high speed is compared with the exact
continuous solution of the source equation to expose explicit-Euler step effects.

Native only: no HoloEnergy import, no controller. Parameters come from the
inspected source, never from fitting runtime outputs.
"""

import argparse
import json
import math
import statistics
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_holoocean_drag import (  # noqa: E402
    file_hash,
    git_info,
    runtime_provenance,
    source_parameters,
    write_json,
)
from tools.holoocean_backend import make_env  # noqa: E402

GRAVITY_M_S2 = 9.8  # UE default world gravity -980 cm/s^2, verified by the drag audit
UE_MAX_PHYSICS_DT_S = 1.0 / 30.0  # UPhysicsSettings default in UE 5.3 (float)
CONSISTENCY_TOLERANCE = 1e-4


def f32(value):
    return struct.unpack("f", struct.pack("f", value))[0]


def predicted_physics_dt(tps):
    """UE 5.3 without substepping: min(world delta, MaxPhysicsDeltaTime), both float."""
    return min(f32(1.0 / tps), f32(UE_MAX_PHYSICS_DT_S))


def scenario(tps):
    return {
        "name": "Native timestep audit",
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
                    {"sensor_type": "CollisionSensor"},
                    {
                        "sensor_type": "DynamicsSensor",
                        "configuration": {"UseCOM": True, "UseRPY": True},
                    },
                ],
            }
        ],
    }


def cases(drag_stability):
    result = [
        {"name": "gravity_air", "location": [0, 0, 20], "velocity": [0, 0, 0]},
        {"name": "air_moving_x", "location": [0, 0, 20], "velocity": [1.0, 0, 0]},
        {"name": "thrust_x_10N_water", "location": [0, 0, -5], "velocity": [0, 0, 0], "thrust": 1},
    ]
    if drag_stability:
        result.append(
            {
                "name": "still_water_deceleration_2_5",
                "location": [0, 0, -5],
                "velocity": [2.5, 0, 0],
            }
        )
    return result


def thrust_action(enabled):
    value = 10 / (2 * math.sqrt(2)) if enabled else 0.0
    return [0.0] * 4 + [value] * 4


def run_case(env, case, tps, trial, steps):
    import numpy as np

    env.reset()
    env.set_ocean_currents("rov0", [0, 0, 0])
    env.agents["rov0"].set_physics_state(
        np.array(case["location"]), np.zeros(3), np.array(case["velocity"]), np.zeros(3)
    )
    previous = env.step(np.zeros(8))  # prime sensor caches after the teleport
    action = np.array(thrust_action(case.get("thrust")))
    d0 = previous["DynamicsSensor"].astype(float)
    rows = [
        {
            "case": case["name"],
            "trial": trial,
            "ticks_per_sec": tps,
            "step": -1,
            "time_s": float(previous["t"]),
            "velocity_m_s": d0[3:6].tolist(),
            "position_m": d0[6:9].tolist(),
            "acceleration_sensor_m_s2": d0[:3].tolist(),
            "angular_velocity_rad_s": d0[12:15].tolist(),
            "collision": bool(np.any(previous["CollisionSensor"])),
        }
    ]
    for step in range(steps):
        state = env.step(action)
        d = state["DynamicsSensor"].astype(float)
        rows.append(
            {
                "case": case["name"],
                "trial": trial,
                "ticks_per_sec": tps,
                "step": step,
                "time_s": float(state["t"]),
                "velocity_m_s": d[3:6].tolist(),
                "position_m": d[6:9].tolist(),
                "acceleration_sensor_m_s2": d[:3].tolist(),
                "angular_velocity_rad_s": d[12:15].tolist(),
                "collision": bool(np.any(state["CollisionSensor"])),
            }
        )
    values = [x for r in rows for x in r["velocity_m_s"] + r["position_m"]]
    if not all(math.isfinite(x) for x in values):
        raise ValueError("Nonfinite runtime observation")
    return rows


def smaller_root(a, b, c):
    """Smaller positive root of a*x^2 + b*x + c = 0 (a may be tiny)."""
    if abs(a) < 1e-15:
        return -c / b
    disc = b * b - 4 * a * c
    if disc < 0:
        raise ValueError("No real timestep solution")
    q = -0.5 * (b + math.copysign(math.sqrt(disc), b))
    roots = [r for r in (q / a, c / q) if r > 0]
    return min(roots)


def pairwise(rows):
    return list(zip(rows, rows[1:], strict=False))


def estimates(rows, parameters):
    """Per-step timestep estimates from one case; empty lists if not applicable."""
    c = parameters["linear_damping_per_s"]
    mass = parameters["mass_kg"]
    case = rows[0]["case"]
    out = {
        "python_timestamp": [b["time_s"] - a["time_s"] for a, b in pairwise(rows)],
        "world_delta_from_sensor": [],
        "gravity_velocity": [],
        "thrust_first_step": [],
        "damping_ratio": [],
        "kinematic_position": [],
    }
    for a, b in pairwise(rows):
        dv = [vb - va for va, vb in zip(a["velocity_m_s"], b["velocity_m_s"], strict=True)]
        axis = max(range(3), key=lambda i: abs(dv[i]))
        if abs(dv[axis]) > 1e-6 and abs(b["acceleration_sensor_m_s2"][axis]) > 1e-9:
            out["world_delta_from_sensor"].append(dv[axis] / b["acceleration_sensor_m_s2"][axis])
        # X motion starts at x = 0 where float32 positions resolve ~1e-9 m; the 20 m
        # altitude of the free-fall case would quantize z to ~2e-6 m.
        if abs(b["velocity_m_s"][0]) > 1e-3:
            out["kinematic_position"].append(
                (b["position_m"][0] - a["position_m"][0]) / b["velocity_m_s"][0]
            )
        if case == "gravity_air":
            vn, vm = a["velocity_m_s"][2], b["velocity_m_s"][2]
            # v[n+1] = (v[n] - g dt)(1 - c dt)
            out["gravity_velocity"].append(
                smaller_root(GRAVITY_M_S2 * c, -(GRAVITY_M_S2 + c * vn), vn - vm)
            )
        if case == "air_moving_x" and abs(a["velocity_m_s"][0]) > 1e-6:
            out["damping_ratio"].append((1 - b["velocity_m_s"][0] / a["velocity_m_s"][0]) / c)
    if case == "thrust_x_10N_water":
        first, second = rows[0], rows[1]
        if max(abs(v) for v in first["velocity_m_s"]) < 1e-9:
            accel = 10.0 / mass
            # v1 = (F/m) dt (1 - c dt)
            out["thrust_first_step"].append(
                smaller_root(accel * c, -accel, second["velocity_m_s"][0])
            )
    return out


def stats(values):
    if not values:
        return None
    return {
        "n": len(values),
        "mean": statistics.mean(values),
        "min": min(values),
        "max": max(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def continuous_still_water_velocity(v0, t, parameters):
    """Exact solution of m dv/dt = -K v|v| - c m v for v0 > 0 (source equation)."""
    c = parameters["linear_damping_per_s"]
    k = (
        0.5
        * parameters["density_kg_m3"]
        * parameters["drag_coefficient"]
        * parameters["area_m2"]
        * parameters["source_drag_scale_to_SI"]
        / parameters["mass_kg"]
    )
    decay = math.exp(-c * t)
    return c * v0 * decay / (c + k * v0 * (1 - decay))


def drag_stability(rows, parameters):
    v0 = rows[0]["velocity_m_s"][0]
    t0 = rows[0]["time_s"]
    trace = []
    for r in rows[1:]:
        dt_client = r["time_s"] - t0
        physics_t = predicted_physics_dt(r["ticks_per_sec"]) * (r["step"] + 1)
        trace.append(
            {
                "step": r["step"],
                "client_time_s": dt_client,
                "physics_time_s": physics_t,
                "velocity_m_s": r["velocity_m_s"][0],
                "continuous_velocity_m_s": continuous_still_water_velocity(
                    v0, physics_t, parameters
                ),
            }
        )
    k_over_m = (
        0.5
        * parameters["density_kg_m3"]
        * parameters["drag_coefficient"]
        * parameters["area_m2"]
        * parameters["source_drag_scale_to_SI"]
        / parameters["mass_kg"]
    )
    dt = predicted_physics_dt(rows[0]["ticks_per_sec"])
    return {
        "initial_velocity_m_s": v0,
        "explicit_step_number_K_v_dt_over_m": k_over_m * v0 * dt,
        "sign_reversal_observed": any(t["velocity_m_s"] < 0 for t in trace),
        "max_abs_error_vs_continuous_m_s": max(
            abs(t["velocity_m_s"] - t["continuous_velocity_m_s"]) for t in trace
        ),
        "trace": trace,
    }


def evaluate(all_rows, parameters, frequencies):
    by_rate = {}
    for tps in frequencies:
        rows_tps = [r for r in all_rows if r["ticks_per_sec"] == tps]
        groups = {}
        for r in rows_tps:
            groups.setdefault((r["case"], r["trial"]), []).append(r)
        merged = {}
        stability = []
        for (case, _), rows in sorted(groups.items()):
            rows.sort(key=lambda r: r["step"])
            for key, values in estimates(rows, parameters).items():
                merged.setdefault(key, []).extend(values)
            if case.startswith("still_water_deceleration"):
                stability.append(drag_stability(rows, parameters))
        physics = [
            v
            for key in ("gravity_velocity", "thrust_first_step", "damping_ratio")
            for v in merged[key]
        ]
        physics_dt = statistics.mean(physics)
        client_dt = 1.0 / tps
        kinematic = statistics.mean(merged["kinematic_position"])
        world = statistics.mean(merged["world_delta_from_sensor"])
        ratio = physics_dt / client_dt
        by_rate[str(tps)] = {
            "ticks_per_sec": tps,
            "client_dt_s": client_dt,
            "python_timestamp_dt_s": stats(merged["python_timestamp"]),
            "world_delta_from_sensor_s": stats(merged["world_delta_from_sensor"]),
            "physics_dt_estimates_s": {
                key: stats(merged[key])
                for key in (
                    "gravity_velocity",
                    "thrust_first_step",
                    "damping_ratio",
                    "kinematic_position",
                )
            },
            "effective_physics_dt_s": physics_dt,
            "effective_to_client_ratio": ratio,
            "kinematic_to_client_ratio": kinematic / client_dt,
            "world_delta_to_client_ratio": world / client_dt,
            "predicted_physics_dt_s": predicted_physics_dt(tps),
            "prediction_relative_error": physics_dt / predicted_physics_dt(tps) - 1,
            "physics_consistent_with_client_clock": abs(ratio - 1) < CONSISTENCY_TOLERANCE,
            "max_angular_velocity_rad_s": max(
                math.sqrt(sum(w * w for w in r["angular_velocity_rad_s"])) for r in rows_tps
            ),
            "any_collision": any(r["collision"] for r in rows_tps),
            "drag_stability": stability or None,
        }
    return by_rate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--binary",
        type=Path,
        help="Executable of a separately built package; default: installed Ocean package",
    )
    parser.add_argument("--ticks-per-sec", nargs="+", type=int, default=[20, 30, 40, 60, 100, 200])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--steps-per-case", type=int, default=12)
    parser.add_argument(
        "--drag-stability",
        action="store_true",
        help="Add still-water deceleration from 2.5 m/s versus the continuous solution",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs/timestep_audit")
    args = parser.parse_args()
    if min(args.ticks_per_sec) < 2 or args.repeats <= 0 or args.steps_per_case < 2:
        parser.error("Positive repeats, >=2 steps and >=2 ticks/s required")
    audit = source_parameters(args.source_dir)
    params = audit["parameters"]
    case_list = cases(args.drag_stability)
    provenance = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "holoenergy_repository": git_info(ROOT),
        "tooling_sha256": {
            relative: file_hash(ROOT / relative)
            for relative in (
                "tools/audit_holoocean_timestep.py",
                "tools/audit_holoocean_drag.py",
                "tools/holoocean_backend.py",
            )
        },
        "source": audit,
        "runtime": runtime_provenance(args.binary),
        "cases": case_list,
        "arguments": vars(args)
        | {
            "source_dir": str(args.source_dir),
            "binary": str(args.binary) if args.binary else None,
            "output_dir": str(args.output_dir),
        },
        "ue_reference": {
            "MaxPhysicsDeltaTime_default_s": UE_MAX_PHYSICS_DT_S,
            "bSubstepping_default": False,
            "rule": "FChaosScene::SetUpForFrame: MDeltaTime = min(DeltaSeconds, MaxPhysicsDeltaTime)",
        },
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw = []
    for tps in args.ticks_per_sec:
        definition = scenario(tps)
        write_json(args.output_dir / f"scenario_{tps}.json", definition)
        with make_env(definition, tps, args.binary) as env:
            for trial in range(args.repeats):
                for case in case_list:
                    raw.extend(run_case(env, case, tps, trial, args.steps_per_case))
        print(f"Completed {tps} Hz", flush=True)
    path = args.output_dir / "raw.jsonl"
    path.write_text(
        "".join(json.dumps(row, allow_nan=False) + "\n" for row in raw), encoding="utf-8"
    )
    by_rate = evaluate(raw, params, args.ticks_per_sec)
    verified = [
        r["ticks_per_sec"] for r in by_rate.values() if r["physics_consistent_with_client_clock"]
    ]
    result = {
        "scope": "physics implementation verification; not physical vehicle validation",
        "provenance": provenance,
        "result_by_tick_rate": by_rate,
        "verified_ticks_per_sec": verified,
        "rejected_ticks_per_sec": [t for t in args.ticks_per_sec if t not in verified],
        "consistency_tolerance": CONSISTENCY_TOLERANCE,
        "raw_sha256": file_hash(path),
        "scenario_sha256": {
            str(tps): file_hash(args.output_dir / f"scenario_{tps}.json")
            for tps in args.ticks_per_sec
        },
    }
    write_json(args.output_dir / "report.json", result)
    for tps, r in by_rate.items():
        print(
            f"{tps:>4} Hz client {r['client_dt_s']:.6f} s, physics {r['effective_physics_dt_s']:.9f} s,"
            f" ratio {r['effective_to_client_ratio']:.7f},"
            f" consistent={r['physics_consistent_with_client_clock']}",
            flush=True,
        )


if __name__ == "__main__":
    main()
