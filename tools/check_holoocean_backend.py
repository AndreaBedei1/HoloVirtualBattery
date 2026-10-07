"""Smoke test of the native HoloOcean backend used under HoloEnergy (verification only).

Runs a short native BlueROV2 test (about one simulator start) and reports:

* drag scale: inferred applied drag / source SI drag for a 0.4 m/s current and for a
  0.4 m/s vehicle in still water, with a known 10 N thruster force validating the
  force reconstruction;
* physics step: integrated step versus the client clock at the requested rate.

PASS means the backend implements its declared SI drag equation and integrates the
client time step. It does not validate vehicle hydrodynamics. Nothing is compensated:
HoloEnergy never rescales drag, currents or energy.

Exit status: 0 PASS, 1 FAIL, 2 INCONCLUSIVE.
"""

import argparse
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_holoocean_drag import (  # noqa: E402
    drag_force_N,
    runtime_provenance,
    source_parameters,
    write_json,
)
from tools.holoocean_backend import make_env  # noqa: E402

# Literals of the official v2.3.0 BlueROV2 source (BlueROV2.cpp, HolodeckBuoyantAgent.h,
# Conversion.h), used when no --source-dir is given. Not fitted to runtime data.
HOLOOCEAN_2_3_0_BLUEROV2 = {
    "mass_kg": 11.5,
    "drag_coefficient": 0.8,
    "area_m2": 0.45,
    "density_kg_m3": 997.0,
    "linear_damping_per_s": 1.0,
    "fully_submerged_ratio": 1.0,
    "ue_units_per_m": 100.0,
    "parameter_origin": "HoloOcean v2.3.0 BlueROV2 source literals",
}
UNPATCHED_SCALE = 0.01
TOLERANCE = 0.02  # relative; measured scatter is ~1e-7, this only rejects real errors
UE_MAX_PHYSICS_DT_S = 1.0 / 30.0


def scenario(tps):
    return {
        "name": "HoloEnergy backend check",
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
                    {
                        "sensor_type": "DynamicsSensor",
                        "configuration": {"UseCOM": True, "UseRPY": True},
                    }
                ],
            }
        ],
    }


def first_step(env, params, tps, current=(0, 0, 0), velocity=(0, 0, 0), thrust=False):
    """Force inferred on the first measured step, damping removed by the UE integrator."""
    import numpy as np

    env.reset()
    env.set_ocean_currents("rov0", list(velocity))  # no relative flow while priming
    env.agents["rov0"].set_physics_state(
        np.array([0, 0, -5]), np.zeros(3), np.array(velocity, dtype=float), np.zeros(3)
    )
    before = env.step(np.zeros(8))["DynamicsSensor"].astype(float)
    env.set_ocean_currents("rov0", list(current))
    value = 10 / (2 * math.sqrt(2)) if thrust else 0.0
    after = env.step(np.array([0.0] * 4 + [value] * 4))["DynamicsSensor"].astype(float)
    dt = 1 / tps
    gain = 1 - params["linear_damping_per_s"] * dt
    v0, v1 = before[3:6], after[3:6]
    force = params["mass_kg"] * (v1 / gain - v0) / dt
    position_step = after[6:9] - before[6:9]
    return v0.tolist(), force.tolist(), position_step.tolist(), v1.tolist()


def scale(observed, expected):
    norm2 = sum(e * e for e in expected)
    return sum(o * e for o, e in zip(observed, expected, strict=True)) / norm2


def verdict(ratio):
    if math.isclose(ratio, 1, rel_tol=TOLERANCE):
        return "PASS", f"observed/expected = {ratio:.6f}"
    if math.isclose(ratio, UNPATCHED_SCALE, rel_tol=TOLERANCE):
        return "FAIL", (
            f"detected ~{ratio:.4f} drag scaling associated with unpatched HoloOcean 2.3.0 "
            "(missing N -> UE force conversion; see patches/README.md)"
        )
    return "FAIL", f"unexpected drag scale {ratio:.6f}; run the full audit"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, help="Package executable; default: installed Ocean")
    parser.add_argument("--source-dir", type=Path, help="HoloOcean source to read parameters from")
    parser.add_argument("--ticks-per-sec", type=int, default=100)
    parser.add_argument("--output", type=Path, help="Optional JSON report path")
    args = parser.parse_args()
    if args.ticks_per_sec < 2:
        parser.error("--ticks-per-sec must be at least 2")
    params = (
        source_parameters(args.source_dir)["parameters"]
        if args.source_dir
        else dict(HOLOOCEAN_2_3_0_BLUEROV2)
    )
    params.setdefault("fully_submerged_ratio", 1.0)
    tps = args.ticks_per_sec
    with make_env(scenario(tps), tps, args.binary) as env:
        _, thrust_force, thrust_dx, thrust_v1 = first_step(env, params, tps, thrust=True)
        _, current_force, _, _ = first_step(env, params, tps, current=(0.4, 0, 0))
        v0, auto_force, auto_dx, auto_v1 = first_step(env, params, tps, velocity=(0.4, 0, 0))
    expected_current = drag_force_N([0, 0, 0], [0.4, 0, 0], params)
    expected_auto = drag_force_N(v0, [0, 0, 0], params)
    thrust_error = abs(thrust_force[0] - 10.0)
    references_ok = thrust_error < 0.05 and abs(thrust_force[1]) < 0.05
    current_ratio = scale(current_force, expected_current)
    auto_ratio = scale(auto_force, expected_auto)
    physics_dt = [dx / v for dx, v in ((thrust_dx[0], thrust_v1[0]), (auto_dx[0], auto_v1[0]))]
    dt_ratio = sum(physics_dt) / len(physics_dt) * tps
    if not references_ok:
        drag_status, drag_detail = (
            "INCONCLUSIVE",
            (
                f"10 N reference reconstructed as {thrust_force[0]:.4f} N; "
                "physics step and client clock differ, see the timestep line"
            ),
        )
    else:
        statuses = [verdict(current_ratio), verdict(auto_ratio)]
        drag_status = "PASS" if all(s == "PASS" for s, _ in statuses) else "FAIL"
        drag_detail = f"current {statuses[0][1]}; still water {statuses[1][1]}"
    step_ok = abs(dt_ratio - 1) < 1e-3
    step_status = "PASS" if step_ok else "FAIL"
    step_detail = f"physics/client step ratio {dt_ratio:.6f}"
    if not step_ok and 1 / tps > UE_MAX_PHYSICS_DT_S:
        step_detail += (
            f"; {tps} Hz exceeds the UE 5.3 default MaxPhysicsDeltaTime (1/30 s, no "
            "substepping): use >= 30 Hz, 100 Hz verified"
        )
    print(f"HoloOcean backend drag scale: {drag_status}: {drag_detail}")
    print(f"HoloOcean physics step at {tps} Hz: {step_status}: {step_detail}")
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "implementation smoke test; not vehicle hydrodynamic validation",
        "runtime": runtime_provenance(args.binary),
        "parameters": params,
        "ticks_per_sec": tps,
        "thrust_reference_N": thrust_force,
        "current_case": {"expected_N": expected_current, "inferred_N": current_force},
        "still_water_case": {"expected_N": expected_auto, "inferred_N": auto_force},
        "drag": {
            "status": drag_status,
            "current_ratio": current_ratio,
            "still_water_ratio": auto_ratio,
        },
        "physics_step": {"status": step_status, "physics_to_client_ratio": dt_ratio},
    }
    if args.output:
        write_json(args.output, report)
    if "INCONCLUSIVE" in (drag_status,):
        raise SystemExit(2)
    raise SystemExit(0 if drag_status == step_status == "PASS" else 1)


if __name__ == "__main__":
    main()
