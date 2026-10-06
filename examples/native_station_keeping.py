"""Native current/effort experiment; controller policy is outside the energy core.

The known source-level native drag-unit discrepancy must be resolved before
quantitative physical current/energy claims. This is a software coupling check.
"""

import copy

from _common import ROOT, backend, parser, settings

from holoenergy import EnergyAwareEnv
from holoenergy.provenance import write_json


def run(args, baseline, current_m_s):
    import numpy as np

    config = copy.deepcopy(baseline)
    config["logging"]["path"] = str(args.output_dir / f"station_{current_m_s:g}.jsonl")
    base, contract = backend(args, config)
    config["environment"] = {
        "water_temperature_C": 15,
        "current_mode": "native",
        "current_velocity_m_s": [current_m_s, 0, 0],
    }
    # Geometry converted from inspected BlueROV2.h (UE cm, left handed) to NWU m.
    # Native Perfect=true places COM at the horizontal-thruster plane.
    positions = np.array(
        [
            [0.12, -0.2181, 0.0809],
            [0.12, 0.2181, 0.0809],
            [-0.12, 0.2181, 0.0809],
            [-0.12, -0.2181, 0.0809],
            [0.1562, -0.0988, 0],
            [0.1562, 0.0988, 0],
            [-0.1562, 0.0988, 0],
            [-0.1562, -0.0988, 0],
        ]
    )
    d = 1 / np.sqrt(2)
    directions = np.array([[0, 0, 1]] * 4 + [[d, d, 0], [d, -d, 0], [d, d, 0], [d, -d, 0]])
    allocation = np.vstack([directions.T, np.cross(positions, directions).T])
    inverse = np.linalg.pinv(allocation)
    rows = []
    with EnergyAwareEnv(base, config=config, control_contract=contract) as env:
        state = base.reset()
        # reset clears native current state; reapply using the documented public API.
        env.energy.set_environment(current_velocity_m_s=[current_m_s, 0, 0])
        target = np.asarray(state["PoseSensor"])[:3, 3].copy()
        integral = np.zeros(3)
        env.energy.mark_phase("station_keeping")
        for _ in range(args.steps):
            pose = np.asarray(state["PoseSensor"])
            rotation, position = pose[:3, :3], pose[:3, 3]
            velocity = np.asarray(state["VelocitySensor"])
            error = target - position
            integral = np.clip(integral + error * env.dt_s, -10, 10)
            world_force = 20 * error - 15 * velocity + 5 * integral
            attitude_error = (
                np.array(
                    [
                        rotation[2, 1] - rotation[1, 2],
                        rotation[0, 2] - rotation[2, 0],
                        rotation[1, 0] - rotation[0, 1],
                    ]
                )
                / 2
            )
            angular = np.asarray(state["DynamicsSensor"])[12:15]
            torque = rotation.T @ (-5 * attitude_error - 2 * angular)
            action = inverse @ np.r_[rotation.T @ world_force, torque]
            state = env.step(action)
            rows.append(state["Energy"])
        final_position = np.asarray(state["PoseSensor"])[:3, 3]
        tail = rows[-min(100, len(rows)) :]
        report = {
            "current_m_s": current_m_s,
            "mean_tail_speed_m_s": float(np.mean([r["linear_speed_m_s"] for r in tail])),
            "mean_tail_propulsion_W": float(np.mean([r["power_propulsion_W"] for r in tail])),
            "mean_tail_effort_norm_N": float(
                np.mean([np.linalg.norm(r["applied_action"]) for r in tail])
            ),
            "final_position_error_m": float(np.linalg.norm(target - final_position)),
            "energy_summary": env.energy.summary(),
            "last_energy": rows[-1],
            "physical_validation": False,
            "dynamics": "native HoloOcean 2.3.0 currents; source drag-unit limitation",
        }
    return report


def main():
    p = parser(__doc__)
    p.set_defaults(scenario=ROOT / "configs/bluerov2_realtime_holoocean.json", steps=600)
    p.add_argument("--currents", nargs="+", type=float, default=[0, 0.2, 0.5, 0.8])
    args = p.parse_args()
    if args.backend != "holoocean":
        p.error("Station-keeping experiment requires the native HoloOcean backend")
    baseline = settings(args)
    records = []
    for current in args.currents:
        report = run(args, baseline, current)
        records.append(report)
        print(
            f"Current {current:g} m/s: speed {report['mean_tail_speed_m_s']:.6f} m/s; "
            f"propulsion {report['mean_tail_propulsion_W']:.6f} W",
            flush=True,
        )
    write_json(
        args.output_dir / "station_keeping_report.json",
        {
            "evidence_kind": "native software/controller coupling; not physical energy validation",
            "controller_policy": {
                "position_P_N_per_m": 20,
                "velocity_D_Ns_per_m": 15,
                "position_I_N_per_m_s": 5,
                "integral_clip_m_s": 10,
                "attitude_P_Nm_per_rad": 5,
                "angular_D_Nms_per_rad": 2,
                "origin": "user-selected demonstration gains, not calibrated physics",
            },
            "actuator_geometry_source": "inspected HoloOcean 2.3.0 BlueROV2.h; retained in sources/generic_native_source_inspection.json",
            "records": records,
        },
    )


if __name__ == "__main__":
    main()
