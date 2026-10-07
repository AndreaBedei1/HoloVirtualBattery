"""Current-aware energy study on a verified native HoloOcean backend.

Experiments (BlueROV2, control scheme 0, verified 100 Hz unless --dt is given):

* station: station keeping under constant world-X currents;
* mission: accelerate, transit, stop, yaw 180 deg, return, under world-X currents;
* temperature: station keeping at one current for several water temperatures;
* payload: base, electrical payload, different battery, physical payload declaration.

Physics comes from HoloOcean, effort from an example controller (user-selected gains),
electrical demand from HoloEnergy. Nothing rescales drag, currents, effort or energy.
Run with --holoocean-binary to select a separately built (e.g. drag-patched) package.
"""

import copy
import gzip
import json
import math
import sys

from _common import ROOT, backend, parser, settings

from holoenergy import EnergyAwareEnv
from holoenergy.provenance import file_hash, write_json

sys.path.insert(0, str(ROOT))
from tools.audit_holoocean_drag import runtime_provenance  # noqa: E402

# Native BlueROV2 geometry (HoloOcean 2.3.0 BlueROV2.h, UE cm left-handed -> NWU m).
THRUSTER_POSITIONS_M = [
    [0.12, -0.2181, 0.0809],
    [0.12, 0.2181, 0.0809],
    [-0.12, 0.2181, 0.0809],
    [-0.12, -0.2181, 0.0809],
    [0.1562, -0.0988, 0],
    [0.1562, 0.0988, 0],
    [-0.1562, 0.0988, 0],
    [-0.1562, -0.0988, 0],
]
BACKEND_THRUST_LIMIT_N = 28.75  # public HoloOcean action bound for BlueROV2 scheme 0
GAINS = {
    "position_P_N_per_m": 20.0,
    "velocity_D_Ns_per_m": 15.0,
    "position_I_N_per_m_s": 5.0,
    "integral_clip_m_s": 10.0,
    "attitude_P_Nm_per_rad": 5.0,
    "angular_D_Nms_per_rad": 2.0,
    "origin": "user-selected demonstration gains, not calibrated; unchanged from "
    "examples/native_station_keeping.py",
}
TRANSIT_SPEED_M_S = 0.25


def allocation_inverse():
    import numpy as np

    positions = np.array(THRUSTER_POSITIONS_M)
    d = 1 / np.sqrt(2)
    directions = np.array([[0, 0, 1]] * 4 + [[d, d, 0], [d, -d, 0], [d, d, 0], [d, -d, 0]])
    return np.linalg.pinv(np.vstack([directions.T, np.cross(positions, directions).T]))


def rotation_z(yaw):
    import numpy as np

    c, s = math.cos(yaw), math.sin(yaw)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class PoseController:
    """World-frame PID on position plus attitude PD towards a yaw reference."""

    def __init__(self, dt):
        import numpy as np

        self.dt = dt
        self.integral = np.zeros(3)
        self.inverse = allocation_inverse()

    def __call__(self, state, position_ref, velocity_ref, yaw_ref, yaw_rate_ref):
        import numpy as np

        pose = np.asarray(state["PoseSensor"])
        rotation, position = pose[:3, :3], pose[:3, 3]
        velocity = np.asarray(state["VelocitySensor"])
        error = position_ref - position
        clip = GAINS["integral_clip_m_s"]
        self.integral = np.clip(self.integral + error * self.dt, -clip, clip)
        world_force = (
            GAINS["position_P_N_per_m"] * error
            + GAINS["velocity_D_Ns_per_m"] * (velocity_ref - velocity)
            + GAINS["position_I_N_per_m_s"] * self.integral
        )
        relative = rotation_z(yaw_ref).T @ rotation
        attitude_error = (
            np.array(
                [
                    relative[2, 1] - relative[1, 2],
                    relative[0, 2] - relative[2, 0],
                    relative[1, 0] - relative[0, 1],
                ]
            )
            / 2
        )
        angular_body = rotation.T @ np.asarray(state["DynamicsSensor"])[12:15]
        torque = -GAINS["attitude_P_Nm_per_rad"] * attitude_error - GAINS[
            "angular_D_Nms_per_rad"
        ] * (angular_body - np.array([0, 0, yaw_rate_ref]))
        return self.inverse @ np.r_[rotation.T @ world_force, torque]


def smooth_ramp(fraction):
    fraction = min(max(fraction, 0.0), 1.0)
    return 0.5 - 0.5 * math.cos(math.pi * fraction)


def mission_plan(dt):
    """Reference velocity/yaw per tick; positions are the integral of velocity."""
    segments = [
        ("hold_start", 3, "hold"),
        ("accelerate", 4, "up+"),
        ("transit_out", 16, "cruise+"),
        ("stop", 4, "down+"),
        ("hold_turn", 3, "hold"),
        ("yaw", 10, "yaw"),
        ("return_accelerate", 4, "up-"),
        ("return_transit", 16, "cruise-"),
        ("return_stop", 4, "down-"),
        ("hold_end", 3, "hold"),
    ]
    ticks = []
    yaw = 0.0
    for name, seconds, kind in segments:
        count = round(seconds / dt)
        for i in range(count):
            f = (i + 1) / count
            speed = {
                "up+": TRANSIT_SPEED_M_S * smooth_ramp(f),
                "cruise+": TRANSIT_SPEED_M_S,
                "down+": TRANSIT_SPEED_M_S * (1 - smooth_ramp(f)),
                "up-": -TRANSIT_SPEED_M_S * smooth_ramp(f),
                "cruise-": -TRANSIT_SPEED_M_S,
                "down-": -TRANSIT_SPEED_M_S * (1 - smooth_ramp(f)),
            }.get(kind, 0.0)
            yaw_rate = 0.0
            if kind == "yaw":
                yaw = math.pi * smooth_ramp(f)
                yaw_rate = math.pi * 0.5 * math.pi / seconds * math.sin(math.pi * f)
            ticks.append({"phase": name, "speed": speed, "yaw": yaw, "yaw_rate": yaw_rate})
    return ticks


def downsample(rows, every):
    return [r for i, r in enumerate(rows) if i % every == 0 or i == len(rows) - 1]


def compact(energy, state, refs, current):
    import numpy as np

    pose = np.asarray(state["PoseSensor"])
    rpy = np.asarray(state["DynamicsSensor"])[15:18]
    return {
        "t_s": energy["time_s"],
        "phase": refs["phase"],
        "current_m_s": list(current),
        "position_m": pose[:3, 3].tolist(),
        "position_ref_m": refs["position"].tolist(),
        "velocity_m_s": np.asarray(state["VelocitySensor"]).tolist(),
        "rpy_deg": rpy.tolist(),
        "speed_m_s": energy["linear_speed_m_s"],
        "angular_speed_rad_s": energy["angular_speed_rad_s"],
        "requested_N": list(map(float, energy["requested_action"])),
        "applied_N": list(map(float, energy["applied_action"])),
        "thruster_power_W": energy["thruster_power_W"],
        "power_propulsion_W": energy["power_propulsion_W"],
        "power_total_W": energy["power_total_W"],
        "voltage_V": energy["voltage_V"],
        "current_A": energy["current_A"],
        "soc": energy["soc"],
        "battery_temperature_C": energy["battery_temperature_C"],
        "water_temperature_C": energy["water_temperature_C"],
        "derating_factor": energy["derating_factor"],
        "battery_state": energy["battery_state"],
        "energy_used_Wh": energy["energy_used_Wh"],
    }


def run(args, baseline, label, current, plan, water_temperature_C=None, mutate=None):
    import numpy as np

    config = copy.deepcopy(baseline)
    if mutate:
        mutate(config)
    config["logging"]["path"] = str(args.output_dir / f"{label}.jsonl")
    config["provenance"]["scenario"]["experiment"] = {"label": label, "current_m_s": current}
    base, contract = backend(args, config)
    dt = config["simulation"]["dt_s"]
    trace = []
    with EnergyAwareEnv(base, config=config, control_contract=contract) as env:
        state = base.reset()
        # "native" applies the current through HoloOcean's public set_ocean_currents;
        # the default "descriptive" mode would only label it.
        environment = {"current_velocity_m_s": list(current), "current_mode": "native"}
        if water_temperature_C is not None:
            environment["water_temperature_C"] = water_temperature_C
        # reset clears native current state; reapply through the documented public API.
        env.energy.set_environment(**environment)
        controller = PoseController(dt)
        start = np.asarray(state["PoseSensor"])[:3, 3].copy()
        target = start.copy()
        phase = None
        for item in plan:
            if item["phase"] != phase:
                phase = item["phase"]
                env.energy.mark_phase(phase)
            velocity_ref = np.array([item["speed"], 0.0, 0.0])
            target = target + velocity_ref * dt
            action = controller(state, target, velocity_ref, item["yaw"], item["yaw_rate"])
            state = env.step(action)
            refs = {"phase": phase, "position": target}
            trace.append(compact(state["Energy"], state, refs, current))
        summary = env.energy.summary()
    return trace, summary, config


def metrics(trace, summary, config, tail_s):
    import numpy as np

    dt = config["simulation"]["dt_s"]
    tail = trace[-max(1, round(tail_s / dt)) :]
    requested = np.array([r["requested_N"] for r in trace])
    applied = np.array([r["applied_N"] for r in trace])
    errors = [
        float(np.linalg.norm(np.array(r["position_m"]) - np.array(r["position_ref_m"])))
        for r in trace
    ]
    saturated = np.max(np.abs(requested), axis=1) > BACKEND_THRUST_LIMIT_N + 1e-9
    phases = {}
    for r in trace:
        phases.setdefault(r["phase"], []).append(r)
    return {
        "duration_s": trace[-1]["t_s"],
        "ticks": len(trace),
        "energy_dt_s": dt,
        "physics_dt_s": dt,
        "physics_dt_basis": "client step verified equal to integrated step at this rate",
        "tail_window_s": tail_s,
        "mean_tail_speed_m_s": float(np.mean([r["speed_m_s"] for r in tail])),
        "max_speed_m_s": float(max(r["speed_m_s"] for r in trace)),
        "mean_tail_position_error_m": float(np.mean(errors[-len(tail) :])),
        "max_position_error_m": float(max(errors)),
        "final_position_error_m": errors[-1],
        "max_angular_speed_rad_s": float(max(r["angular_speed_rad_s"] for r in trace)),
        "max_abs_roll_pitch_deg": float(
            max(max(abs(r["rpy_deg"][0]), abs(r["rpy_deg"][1])) for r in trace)
        ),
        "mean_tail_requested_effort_N": np.mean(np.abs(requested[-len(tail) :]), axis=0).tolist(),
        "mean_tail_applied_effort_N": np.mean(np.abs(applied[-len(tail) :]), axis=0).tolist(),
        "mean_tail_applied_effort_norm_N": float(
            np.mean(np.linalg.norm(applied[-len(tail) :], axis=1))
        ),
        "saturated_tick_fraction": float(np.mean(saturated)),
        "tail_saturated_tick_fraction": float(np.mean(saturated[-len(tail) :])),
        "min_derating_factor": float(min(r["derating_factor"] for r in trace)),
        "mean_tail_propulsion_W": float(np.mean([r["power_propulsion_W"] for r in tail])),
        "mean_tail_total_W": float(np.mean([r["power_total_W"] for r in tail])),
        "propulsion_Wh": summary["category_energy_Wh"].get("propulsion"),
        "terminal_Wh": summary["terminal_energy_Wh"],
        "battery_losses_Wh": summary["category_energy_Wh"].get("battery_losses"),
        "category_energy_Wh": summary["category_energy_Wh"],
        "phase_energy_Wh": summary["phases"],
        "phase_mean_propulsion_W": {
            name: float(np.mean([r["power_propulsion_W"] for r in rows]))
            for name, rows in phases.items()
        },
        "min_voltage_V": float(min(r["voltage_V"] for r in trace)),
        "final_voltage_V": trace[-1]["voltage_V"],
        "mean_current_A": float(np.mean([r["current_A"] for r in trace])),
        "peak_current_A": float(max(r["current_A"] for r in trace)),
        "initial_soc": trace[0]["soc"],
        "final_soc": trace[-1]["soc"],
        "final_battery_temperature_C": trace[-1]["battery_temperature_C"],
        "peak_battery_temperature_C": float(max(r["battery_temperature_C"] for r in trace)),
        "battery_states": sorted({r["battery_state"] for r in trace}),
    }


def save(args, label, trace, summary, config, tail_s):
    path = args.output_dir / f"{label}.trace.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        for row in downsample(trace, args.trace_every):
            handle.write(json.dumps(row, allow_nan=False) + "\n")
    result = metrics(trace, summary, config, tail_s)
    result["trace"] = {
        "path": path.name,
        "sha256": file_hash(path),
        "every_ticks": args.trace_every,
    }
    log = args.output_dir / f"{label}.jsonl"
    result["energy_log"] = {"path": log.name, "sha256": file_hash(log)}
    return result


def main():
    p = parser(__doc__)
    p.set_defaults(scenario=ROOT / "configs/bluerov2_realtime_holoocean.json")
    p.add_argument(
        "--experiments",
        nargs="+",
        choices=["station", "mission", "temperature", "payload"],
        default=["station", "mission", "temperature", "payload"],
    )
    p.add_argument("--currents", nargs="+", type=float, default=[0, 0.2, 0.5, 0.8])
    p.add_argument("--mission-currents", nargs="+", type=float, default=[0, 0.2, 0.4])
    p.add_argument("--water-temperatures", nargs="+", type=float, default=[5, 15, 25])
    p.add_argument("--temperature-current", type=float, default=0.5)
    p.add_argument("--payload-current", type=float, default=0.2)
    p.add_argument("--station-seconds", type=float, default=30)
    p.add_argument("--temperature-seconds", type=float, default=60)
    p.add_argument("--tail-seconds", type=float, default=10)
    p.add_argument("--trace-every", type=int, default=10)
    p.add_argument("--label", default="study")
    args = p.parse_args()
    if args.backend != "holoocean":
        p.error("This study requires the native HoloOcean backend")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline = settings(args)
    dt = baseline["simulation"]["dt_s"]
    records = {}

    def station_plan(seconds):
        return [{"phase": "station_keeping", "speed": 0.0, "yaw": 0.0, "yaw_rate": 0.0}] * round(
            seconds / dt
        )

    def execute(name, current, plan, tail_s, **kwargs):
        trace, summary, config = run(args, baseline, name, current, plan, **kwargs)
        records[name] = save(args, name, trace, summary, config, tail_s) | {
            "current_m_s": current,
            "water_temperature_C": trace[-1]["water_temperature_C"],
        }
        r = records[name]
        print(
            f"{name}: tail speed {r['mean_tail_speed_m_s']:.4f} m/s, tail propulsion "
            f"{r['mean_tail_propulsion_W']:.3f} W, propulsion {r['propulsion_Wh']:.5f} Wh, "
            f"terminal {r['terminal_Wh']:.5f} Wh, saturated {r['saturated_tick_fraction']:.3f}",
            flush=True,
        )

    if "station" in args.experiments:
        for u in args.currents:
            execute(
                f"station_{u:g}", [u, 0, 0], station_plan(args.station_seconds), args.tail_seconds
            )
    if "mission" in args.experiments:
        for u in args.mission_currents:
            execute(f"mission_{u:g}", [u, 0, 0], mission_plan(dt), 3)
    if "temperature" in args.experiments:
        for t in args.water_temperatures:
            execute(
                f"water_{t:g}C",
                [args.temperature_current, 0, 0],
                station_plan(args.temperature_seconds),
                args.tail_seconds,
                water_temperature_C=t,
            )
    if "payload" in args.experiments:
        u = [args.payload_current, 0, 0]

        def electrical(config):
            config.setdefault("components", []).append(
                {"name": "added_scientific_sensor", "active_W": 18}
            )

        def battery(config):
            config["battery"]["capacity_Ah"] = config["battery"]["capacity_Ah"] / 2

        def physical(config):
            config["vehicle"]["payload"] = {
                "mass_kg": 2.0,
                "displaced_volume_m3": 0.001,
                "position_m": [0.1, 0, -0.05],
            }

        for name, mutate in (
            ("payload_base", None),
            ("payload_electrical_18W", electrical),
            ("payload_battery_half_capacity", battery),
            ("payload_physical_declared", physical),
        ):
            execute(
                name,
                u,
                station_plan(args.station_seconds),
                args.tail_seconds,
                mutate=mutate,
            )
    report = {
        "evidence_kind": "implementation-verified native simulation coupled to configured energy "
        "models; not physical vehicle validation",
        "label": args.label,
        "runtime": runtime_provenance(args.holoocean_binary),
        "controller_policy": GAINS,
        "transit_speed_m_s": TRANSIT_SPEED_M_S,
        "backend_thrust_limit_N": BACKEND_THRUST_LIMIT_N,
        "dt_s": dt,
        "ticks_per_sec": round(1 / dt),
        "scenario_sha256": file_hash(args.scenario),
        "config_sha256": file_hash(args.config),
        "physical_payload_boundary": "Native HoloOcean 2.3.0 exposes no verified setter for "
        "agent mass/volume/drag: a declared physical payload is descriptive only and cannot "
        "change the simulated dynamics.",
        "records": records,
    }
    write_json(args.output_dir / f"{args.label}_report.json", report)
    print(f"Report: {args.output_dir / (args.label + '_report.json')}", flush=True)


if __name__ == "__main__":
    main()
