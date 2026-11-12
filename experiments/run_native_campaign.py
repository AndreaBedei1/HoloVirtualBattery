"""Native closed-loop provenance-aware campaign on the verified (drag-patched) HoloOcean backend.

Every run is one HoloOcean process (BlueROV2 agent, control scheme 0, 100 Hz, verified
patched package) driven in closed loop:

    world current -> HoloOcean dynamics (SI drag) -> controller body wrench
    -> HoloEnergy allocation over the configured layout (T200 bounds at the pack voltage)
    -> per-actuator force -> T200 electrical power -> bus -> L1 battery (I, V, SOC, T)
    -> power limit / derating -> applied forces -> backend mapping (direct, or
       wrench-equivalent re-allocation on the native 8-thruster body within its clamp)
    -> HoloOcean motion -> controller ...

Nothing is fitted or rescaled. The controller (gains of examples/native_current_energy_study.py)
is user-selected policy, not a scientific parameter. For every run the chain is closed
tick by tick: the measured centre-of-mass acceleration is compared with native thrust +
SI source drag; T200 power is recomputed independently from the applied (virtual) forces;
the virtual wrench B_v f_v is compared with the native wrench B_n f_n.

Instances: each run starts its own package process with a random UUID (HoloOcean 2.3 on
Windows uses UUID-named shared memory and semaphores, no TCP port). Run at most two
campaign processes at a time (``--runs`` selects disjoint subsets).
"""

from __future__ import annotations

import argparse
import copy
import gzip
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples"))
sys.path.insert(0, str(ROOT / "experiments"))

from native_current_energy_study import (  # noqa: E402
    GAINS,
    TRANSIT_SPEED_M_S,
    mission_plan,
    rotation_z,
    smooth_ramp,
)
from run_offline_campaign import NATIVE, layouts, suite_components  # noqa: E402

from holoenergy import EnergyAwareEnv, __version__  # noqa: E402
from holoenergy.allocation import ThrustAllocator  # noqa: E402
from holoenergy.config import load_config, with_fidelity  # noqa: E402
from holoenergy.evidence import default_registry  # noqa: E402
from holoenergy.provenance import file_hash, git_state  # noqa: E402
from tools.audit_holoocean_drag import drag_force_N, source_parameters  # noqa: E402
from tools.holoocean_backend import make_env, package_identity  # noqa: E402
from tools.verify_energy_chain import (  # noqa: E402
    T200Tables,
    runtime_force,
    thruster_force_world,
)

DT = 0.01  # verified physics rate (docs/holoocean_timestep_report.md); never 20 Hz here
SCENARIO = {
    "name": "HoloEnergy-native-campaign",
    "package_name": "Ocean",
    "world": "SimpleUnderwater",
    "main_agent": "rov0",
    "ticks_per_sec": 100,
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
                {
                    "sensor_type": "DynamicsSensor",
                    "configuration": {"UseCOM": True, "UseRPY": True},
                },
            ],
        }
    ],
}
CONTRACT = {
    "agent_type": "BlueROV2",
    "agent_name": "rov0",
    "control_scheme": 0,
    "action_units": "force_N",
    "thruster_count": 8,
    "dt_s": DT,
}
NATIVE_B = ThrustAllocator(NATIVE).B
LAYOUTS = layouts()


# ----------------------------------------------------------------------------- plans
def station_plan(seconds):
    return [
        {"phase": "station_keeping", "velocity": (0.0, 0.0, 0.0), "yaw": 0.0, "yaw_rate": 0.0}
    ] * round(seconds / DT)


def transit_plan():
    """Accelerate, transit, stop, yaw 180 deg, return (examples/native_current_energy_study.py)."""
    return [
        {
            "phase": t["phase"],
            "velocity": (t["speed"], 0.0, 0.0),
            "yaw": t["yaw"],
            "yaw_rate": t["yaw_rate"],
        }
        for t in mission_plan(DT)
    ]


def heave_plan(speed=0.2):
    segments = [
        ("hold_start", 3, 0),
        ("ascend_ramp", 3, 1),
        ("ascend", 8, 2),
        ("ascend_stop", 3, 3),
    ]
    segments.append(("hold_end", 3, 0))
    ticks = []
    for name, seconds, kind in segments:
        count = round(seconds / DT)
        for i in range(count):
            f = (i + 1) / count
            w = {1: speed * smooth_ramp(f), 2: speed, 3: speed * (1 - smooth_ramp(f))}.get(
                kind, 0.0
            )
            ticks.append({"phase": name, "velocity": (0.0, 0.0, w), "yaw": 0.0, "yaw_rate": 0.0})
    return ticks


PLANS = {"station30": lambda: station_plan(30.0), "transit": transit_plan, "heave": heave_plan}


# ------------------------------------------------------------------------ controller
class WrenchController:
    """World-frame PID on position, attitude PD; output is the body wrench (N, N*m).

    Same policy and gains as examples/native_current_energy_study.PoseController, without
    its fixed pseudo-inverse: allocation is HoloEnergy's, over the configured layout.
    """

    def __init__(self):
        import numpy as np

        self.integral = np.zeros(3)

    def __call__(self, state, position_ref, velocity_ref, yaw_ref, yaw_rate_ref):
        import numpy as np

        pose = np.asarray(state["PoseSensor"])
        rotation, position = pose[:3, :3], pose[:3, 3]
        velocity = np.asarray(state["VelocitySensor"])
        error = position_ref - position
        clip = GAINS["integral_clip_m_s"]
        self.integral = np.clip(self.integral + error * DT, -clip, clip)
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
        return np.r_[rotation.T @ world_force, torque]


# --------------------------------------------------------------------------- configs
def layout_config(layout, mapping, *, suite=None, fidelity="L1", battery=None):
    geometry, description, grade = LAYOUTS[layout]
    actuators = [
        {
            "id": g.id,
            "role": "vertical" if abs(g.direction[2]) > 0.99 else "horizontal",
            "profile": "package:actuators/bluerobotics_t200.yaml",
            "position_m": list(g.position_m),
            "direction": list(g.direction),
        }
        for g in geometry
    ]
    backend = {"mapping": mapping, "native_clamp_N": 28.75, "agent_type": "BlueROV2"}
    if mapping == "direct":
        if layout != "L8-HV":
            raise ValueError("Only the simulator-exact L8-HV layout maps directly")
        # HoloOcean order (agents_2.3.0.json): V1..V4 -> 0..3, H1..H4 -> 4..7.
        native_of = {"V1": 0, "V2": 1, "V3": 2, "V4": 3, "H1": 4, "H2": 5, "H3": 6, "H4": 7}
        for a in actuators:
            a["backend_index"] = native_of[a["id"]]
    else:
        backend["native_geometry"] = [
            {"id": a.id, "position_m": list(a.position_m), "direction": list(a.direction)}
            for a in NATIVE
        ]
    data = {
        "profile": "package:vehicles/bluerov2_heavy_holoocean.yaml",
        "actuators": actuators,
        "actuation": {
            "action_mode": "wrench",
            "allocation": {"method": "redistributed"},
            "backend": backend,
        },
        "simulation": {"dt_s": DT, "expected_agent_type": "BlueROV2", "control_scheme": 0},
        "power_manager": {"apply_derating_to_actions": True},
        "logging": {"enabled": False},
        # Relation of the actuation layout to a real vehicle: simulator-exact Heavy layout
        # (representative of the physical Heavy), Standard 6T (proxy), design layouts (user).
        "evidence": {
            "geometry": {
                "record": None,
                "relation": {"A": "exact", "C": "proxy"}.get(grade, "user"),
            },
            "vehicle_relation": {"A": "representative", "C": "proxy"}.get(grade, "user"),
        },
    }
    if suite is not None:
        data["components"] = suite_components(suite)
    if battery:
        data["battery"] = battery
    config = load_config(data=data)
    if fidelity == "L0":
        config = with_fidelity(config, "L0")
    meta = {"layout": layout, "description": description, "geometry_grade": grade}
    return config, meta


# ------------------------------------------------------------------------------ run
def run(spec, binary, source_parameters_, tables):
    import numpy as np

    config, meta = layout_config(
        spec["layout"],
        spec["mapping"],
        suite=spec.get("suite"),
        fidelity=spec.get("fidelity", "L1"),
        battery=spec.get("battery"),
    )
    current = list(spec["current_m_s"])
    plan = PLANS[spec["plan"]]()
    scenario = copy.deepcopy(SCENARIO)
    wall0 = time.perf_counter()
    base = make_env(scenario, round(1 / DT), binary)
    ticks, step_wall = [], 0.0
    try:
        with EnergyAwareEnv(base, config=config, control_contract=CONTRACT) as env:
            state = base.reset()
            env.energy.set_environment(current_velocity_m_s=current, current_mode="native")
            controller = WrenchController()
            target = np.asarray(state["PoseSensor"])[:3, 3].copy()
            phase = None
            for item in plan:
                if item["phase"] != phase:
                    phase = item["phase"]
                    env.energy.mark_phase(phase)
                velocity_ref = np.array(item["velocity"])
                target = target + velocity_ref * DT
                wrench = controller(state, target, velocity_ref, item["yaw"], item["yaw_rate"])
                t0 = time.perf_counter()
                state = env.step(wrench)
                step_wall += time.perf_counter() - t0
                ticks.append(tick_row(state, phase, target, wrench, current))
            summary = env.energy.summary()
            report = env.energy.report()
            describe = env.actuation.describe()
    finally:
        close = getattr(base, "close", None)
        if close is not None:
            try:
                close()
            except Exception:  # noqa: BLE001 - shutdown errors are reported, not hidden
                pass
    wall = time.perf_counter() - wall0
    result = {
        "spec": spec,
        "layout": meta | describe,
        "metrics": metrics(ticks, summary),
        "chain": close_chain(ticks, source_parameters_, tables, spec["mapping"]),
        "evidence": summary.get("evidence"),
        "energy_report": report.to_dict(),
        "timing": {
            "wall_s": wall,
            "env_step_wall_s": step_wall,
            "ticks": len(ticks),
            "simulated_s": len(ticks) * DT,
            "real_time_factor": len(ticks) * DT / step_wall if step_wall else None,
        },
    }
    return result, ticks


def tick_row(state, phase, target, wrench, current):
    import numpy as np

    e = state["Energy"]
    a = e["actuation"]
    pose = np.asarray(state["PoseSensor"])
    dyn = np.asarray(state["DynamicsSensor"])
    return {
        "t_s": e["time_s"],
        "phase": phase,
        "current_m_s": current,
        "position_m": pose[:3, 3].tolist(),
        "position_ref_m": target.tolist(),
        "com_velocity_m_s": dyn[3:6].tolist(),
        "rpy_deg": dyn[15:18].tolist(),
        "speed_m_s": e["linear_speed_m_s"],
        "requested_wrench": [float(v) for v in wrench],
        "allocated_wrench": a["allocated_wrench"],
        "allocation_residual_norm": a["allocation_residual_norm"],
        "allocation_saturated": any(a["allocation_saturated"]),
        "applied_N": list(map(float, e["applied_action"])),
        "applied_wrench": a["applied_wrench"],
        "backend_N": a["backend_action"],
        "backend_residual_norm": a["backend_residual_norm"],
        "native_saturated": any(a.get("native_saturated", [])),
        "thruster_power_W": e["thruster_power_W"],
        "power_propulsion_W": e["power_propulsion_W"],
        "power_total_W": e["power_total_W"],
        "voltage_V": e["voltage_V"],
        "current_A": e["current_A"],
        "soc": e["soc"],
        "battery_temperature_C": e["battery_temperature_C"],
        "derating_factor": e["derating_factor"],
        "battery_state": e["battery_state"],
    }


def close_chain(ticks, parameters, tables, mapping):
    """Mechanical, electrical and wrench-equivalence residuals, tick by tick."""
    import numpy as np

    force_worst, sq = [0.0] * 3, [0.0] * 3
    for a, b in zip(ticks, ticks[1:], strict=False):
        drag = drag_force_N(a["com_velocity_m_s"], b["current_m_s"], parameters)
        thrust = thruster_force_world(b["backend_N"], a["rpy_deg"])
        measured = runtime_force(a["com_velocity_m_s"], b["com_velocity_m_s"], DT, parameters)
        for k in range(3):
            r = measured[k] - (thrust[k] + drag[k])
            force_worst[k] = max(force_worst[k], abs(r))
            sq[k] += r * r
    power_worst = 0.0
    for t in ticks:
        powers = [tables.power(f, t["voltage_V"]) for f in t["applied_N"]]
        power_worst = max(
            power_worst, *(abs(p - q) for p, q in zip(powers, t["thruster_power_W"], strict=True))
        )
    equivalence = [
        float(
            np.linalg.norm(np.asarray(t["applied_wrench"]) - NATIVE_B @ np.asarray(t["backend_N"]))
        )
        for t in ticks
    ]
    inconsistent = sum(r > 1e-6 for r in equivalence)
    steps = max(1, len(ticks) - 1)
    return {
        "force_steps": len(ticks) - 1,
        "max_abs_force_residual_N": force_worst,
        "rms_force_residual_N": [math.sqrt(s / steps) for s in sq],
        "max_abs_thruster_power_residual_W": power_worst,
        "wrench_equivalence": {
            "mapping": mapping,
            "max_residual_norm": max(equivalence),
            "mean_residual_norm": float(np.mean(equivalence)),
            "ticks_above_1e-6": inconsistent,
            "fraction_above_1e-6": inconsistent / len(ticks),
        },
        "status": "PASS"
        if max(force_worst) < 1e-3 and power_worst < 1e-6 and inconsistent == 0
        else (
            "PASS_WITH_INCONSISTENT_TICKS"
            if max(force_worst) < 1e-3 and power_worst < 1e-6
            else "FAIL"
        ),
    }


def metrics(ticks, summary):
    import numpy as np

    pos = np.array([t["position_m"] for t in ticks])
    ref = np.array([t["position_ref_m"] for t in ticks])
    err = np.linalg.norm(pos - ref, axis=1)
    tail = slice(-max(1, round(10.0 / DT)), None)
    applied = np.abs(np.array([t["applied_N"] for t in ticks]))
    alloc_res = np.array([t["allocation_residual_norm"] for t in ticks])
    rpy = np.array([t["rpy_deg"] for t in ticks])
    cat = summary["category_energy_Wh"]
    return {
        "duration_s": len(ticks) * DT,
        "mean_tracking_error_m": float(err.mean()),
        "max_tracking_error_m": float(err.max()),
        "final_tracking_error_m": float(err[-1]),
        "mean_tail_tracking_error_m": float(err[tail].mean()),
        "max_abs_roll_pitch_deg": float(np.max(np.abs(rpy[:, :2]))),
        "mean_allocation_residual_norm": float(alloc_res.mean()),
        "max_allocation_residual_norm": float(alloc_res.max()),
        "allocation_saturated_fraction": float(np.mean([t["allocation_saturated"] for t in ticks])),
        "native_saturated_fraction": float(np.mean([t["native_saturated"] for t in ticks])),
        "max_backend_residual_norm": float(max(t["backend_residual_norm"] for t in ticks)),
        "peak_actuator_force_N": float(applied.max()),
        "mean_tail_actuator_force_N": applied[tail].mean(axis=0).tolist(),
        "peak_total_power_W": float(max(t["power_total_W"] for t in ticks)),
        "mean_total_power_W": float(np.mean([t["power_total_W"] for t in ticks])),
        "mean_tail_propulsion_W": float(np.mean([t["power_propulsion_W"] for t in ticks[tail]])),
        "propulsion_Wh": cat.get("propulsion", 0.0),
        "sensors_Wh": cat.get("sensors", 0.0),
        "compute_Wh": cat.get("compute", 0.0),
        "auxiliaries_Wh": cat.get("auxiliaries", 0.0),
        "communications_Wh": cat.get("communications", 0.0),
        "battery_losses_Wh": cat.get("battery_losses", 0.0),
        "category_energy_Wh": cat,
        "terminal_Wh": summary["terminal_energy_Wh"],
        "phase_energy_Wh": summary.get("phases"),
        "initial_soc": ticks[0]["soc"],
        "final_soc": ticks[-1]["soc"],
        "soc_loss": ticks[0]["soc"] - ticks[-1]["soc"],
        "peak_current_A": float(max(t["current_A"] for t in ticks)),
        "min_voltage_V": float(min(t["voltage_V"] for t in ticks)),
        "min_derating_factor": float(min(t["derating_factor"] for t in ticks)),
        "derated_tick_fraction": float(np.mean([t["derating_factor"] < 1 - 1e-9 for t in ticks])),
        "battery_states": sorted({t["battery_state"] for t in ticks}),
        "peak_battery_temperature_C": float(max(t["battery_temperature_C"] for t in ticks)),
    }


# ----------------------------------------------------------------------------- matrix
def matrix():
    runs = {}

    def add(label, group, layout, mapping, current, plan, **extra):
        runs[label] = {
            "label": label,
            "group": group,
            "layout": layout,
            "mapping": mapping,
            "current_m_s": current,
            "plan": plan,
            **extra,
        }

    for c in (0.0, 0.2, 0.5, 0.8):
        add(f"N1-L8-HV-direct-c{c:g}", "N1_layouts", "L8-HV", "direct", [c, 0, 0], "station30")
        for layout in ("L8-HV", "L6-STD", "L4-H45", "L4-2H2V", "L8-VEC30"):
            add(
                f"N1-{layout}-we-c{c:g}",
                "N1_layouts",
                layout,
                "wrench_equivalent",
                [c, 0, 0],
                "station30",
            )
    for layout in ("L8-HV", "L8-HV-a30", "L8-HV-a60", "L4-2H2V"):
        mapping = "direct" if layout == "L8-HV" else "wrench_equivalent"
        add(f"N2-{layout}-sway-c0.5", "N2_orientation", layout, mapping, [0, 0.5, 0], "station30")
    for layout in ("L8-HV-a30", "L8-HV-a60"):
        add(
            f"N2-{layout}-surge-c0.5",
            "N2_orientation",
            layout,
            "wrench_equivalent",
            [0.5, 0, 0],
            "station30",
        )
    for layout, mapping in (
        ("L8-HV", "direct"),
        ("L6-STD", "wrench_equivalent"),
        ("L4-H45", "wrench_equivalent"),
    ):
        add(f"N3-{layout}-heave", "N3_heave", layout, mapping, [0, 0, 0], "heave")
    for c in (0.0, 0.2, 0.4):
        add(f"N4-L8-HV-transit-c{c:g}", "N4_mission", "L8-HV", "direct", [c, 0, 0], "transit")
    add(
        "N4-L6-STD-transit-c0.2",
        "N4_mission",
        "L6-STD",
        "wrench_equivalent",
        [0.2, 0, 0],
        "transit",
    )
    for suite in ("S0-propulsion-only", "S5-inspection", "S6-ai-vision"):
        add(
            f"N5-{suite}-transit-c0.2",
            "N5_suites",
            "L8-HV",
            "direct",
            [0.2, 0, 0],
            "transit",
            suite=suite,
        )
    add(
        "N6-L8-HV-L0-transit-c0.2",
        "N6_battery",
        "L8-HV",
        "direct",
        [0.2, 0, 0],
        "transit",
        fidelity="L0",
    )
    # Power limiting: same station case started from a nearly empty pack (scenario setting,
    # not a parameter): the cutoff/limit path of the L1 pack must reduce applied thrust.
    add(
        "N6-L8-HV-lowsoc-c0.5",
        "N6_battery",
        "L8-HV",
        "direct",
        [0.5, 0, 0],
        "station30",
        battery={"initial_soc": 0.03},
    )
    return runs


def downsample(rows, every=10):
    return [r for i, r in enumerate(rows) if i % every == 0 or i == len(rows) - 1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--binary", type=Path, required=True, help="verified patched Holodeck.exe")
    parser.add_argument("--source-dir", type=Path, required=True, help="patched HoloOcean source")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "experiments/results/native")
    parser.add_argument("--full-trace-dir", type=Path, default=ROOT / "logs/native_campaign")
    parser.add_argument("--runs", nargs="*", help="labels or group names; default all")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    args = parser.parse_args(argv)
    runs = matrix()
    if args.list:
        for label, spec in runs.items():
            print(label, spec["group"])
        return 0
    selected = [
        label
        for label, spec in runs.items()
        if not args.runs or label in args.runs or spec["group"] in args.runs
    ]
    identity = package_identity(args.binary)
    if identity["build_patch_sha256"] is None:
        raise SystemExit("Refusing an unpatched/unknown package for quantitative native runs")
    parameters = source_parameters(args.source_dir)["parameters"]
    if parameters["source_drag_scale_to_SI"] != 1:
        raise SystemExit("Source tree does not contain the drag-units patch")
    tables = T200Tables(
        json.loads((ROOT / "holoenergy/profiles/thrusters/bluerobotics_t200.json").read_text())
    )
    registry = default_registry()
    provenance = {
        "holoenergy_version": __version__,
        "git": git_state(),
        "backend": identity,
        "source_parameters": parameters,
        "physics_rate_hz": round(1 / DT),
        "instance_isolation": "random UUID per process (shared memory/semaphores); no TCP port",
        "scenario": SCENARIO,
        "controller": GAINS,
        "transit_speed_m_s": TRANSIT_SPEED_M_S,
        "evidence_registry": {
            "version": registry.version,
            "records": len(registry.records),
            "sources": len(registry.sources),
        },
        "random_seed": "none (deterministic plan and controller)",
    }
    for label in selected:
        spec = runs[label]
        out_dir = args.output_dir / spec["group"]
        out_dir.mkdir(parents=True, exist_ok=True)
        summary_path = out_dir / f"{label}.summary.json"
        if args.skip_existing and summary_path.exists():
            continue
        print(f"== {label}", flush=True)
        started = datetime.now(timezone.utc).isoformat()
        try:
            result, ticks = run(spec, args.binary, parameters, tables)
        except Exception as exc:  # noqa: BLE001 - failures are recorded, not hidden
            summary_path.with_suffix(".error.json").write_text(
                json.dumps({"spec": spec, "error": repr(exc), "started_utc": started}, indent=2),
                encoding="utf-8",
            )
            print(f"FAILED {label}: {exc!r}", flush=True)
            continue
        args.full_trace_dir.mkdir(parents=True, exist_ok=True)
        full = args.full_trace_dir / f"{label}.trace.jsonl.gz"
        with gzip.open(full, "wt", encoding="utf-8") as handle:
            for row in ticks:
                handle.write(json.dumps(row) + "\n")
        small = out_dir / f"{label}.trace10.jsonl.gz"
        with gzip.open(small, "wt", encoding="utf-8") as handle:
            for row in downsample(ticks):
                handle.write(json.dumps(row) + "\n")
        result["provenance"] = provenance | {"started_utc": started}
        result["traces"] = {
            "full_per_tick": {"path": str(full), "sha256": file_hash(full)},
            "downsampled_0.1s": {"path": small.name, "sha256": file_hash(small)},
        }
        summary_path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        m, c = result["metrics"], result["chain"]
        print(
            f"   {c['status']} force {max(c['max_abs_force_residual_N']):.1e} N, "
            f"equiv {c['wrench_equivalence']['max_residual_norm']:.1e}; "
            f"prop {m['propulsion_Wh']:.4f} Wh, total {m['terminal_Wh']:.4f} Wh, "
            f"err {m['mean_tail_tracking_error_m']:.3f} m, RTF {result['timing']['real_time_factor']:.2f}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
