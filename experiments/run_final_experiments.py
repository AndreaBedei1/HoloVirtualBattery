"""Final paper experiment set, native part (EXP3-EXP8), run from a clean committed tree.

Reuses the verified closed-loop components of experiments/run_native_campaign.py
(controller, layouts, chain closure) and adds what the paper-critical reruns need:

* refuses to start from a dirty working tree (unless --allow-dirty) and records commit,
  backend hashes, a SHA256 of every resolved configuration and of every result file;
* per-tick rows with every category, component, actuator and battery-loss power, so that
  experiments/verify_final_energy.py can recompute E = sum P dt independently;
* mission-phase component scheduling (devices switched on only in the phases where the
  mission uses them; the switch is rail gating, 0 W when OFF);
* station keeping over 90 s with a steady-state window (last 30 s) reported separately
  from the transient; currents head-on (and oblique 45 deg) so that horizontal thrusters
  work on the forward T200 branch; transits end with a 10 s hold at the start point.

Outputs go to --output-dir (default logs/final, ignored by git); copy the summaries and
0.1 s traces to experiments/results/final after the run. See docs/paper/FINAL_EXPERIMENTS.md.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_native_campaign import (  # noqa: E402
    CONTRACT,
    DT,
    GAINS,
    SCENARIO,
    WrenchController,
    close_chain,
    downsample,
    heave_plan,
    layout_config,
    metrics,
    station_plan,
    transit_plan,
    write_trace,
)

from holoenergy import EnergyAwareEnv, __version__  # noqa: E402
from holoenergy.evidence import default_registry  # noqa: E402
from holoenergy.provenance import file_hash, git_state  # noqa: E402
from tools.audit_holoocean_drag import source_parameters  # noqa: E402
from tools.holoocean_backend import make_env, package_identity  # noqa: E402
from tools.verify_energy_chain import T200Tables  # noqa: E402

STATION_S = 90.0
STEADY_S = 30.0
END_HOLD_S = 10.0
# Review B-01: the sign convention mapping HoloOcean's positive thruster force to the T200
# forward branch is an assumption. Station-keeping currents therefore come from the bow
# (current along -x with the vehicle facing +x), so the vehicle thrusts forward into the
# current, as in the restrained-load tests of Gabl et al. (head-on).
HEAD_ON = -1.0


def transit_settled():
    """Transit plan with a longer final hold so that every run ends settled (review B)."""
    plan = transit_plan()
    last = dict(plan[-1])
    last["phase"] = "hold_end"
    return plan + [last] * round(END_HOLD_S / DT)


PLANS = {
    "station": lambda: station_plan(STATION_S),
    "transit": transit_settled,
    "heave": heave_plan,
}
# Phases of the transit plan in which an inspection payload works (at the far point:
# stop, hold and yaw before returning). Scenario definition, not evidence.
INSPECTION_PHASES = ("stop", "hold_turn", "yaw")
SCHEDULES = {
    # device -> phases in which the device is on (other phases: OFF)
    "inspection-at-site": {
        "bluerobotics_4k_camera": INSPECTION_PHASES,
        "tritech_gemini_720is": INSPECTION_PHASES,
        "bluerobotics_lumen": INSPECTION_PHASES,
    },
    "ai-at-site": {"jetson_orin_nx_16gb": INSPECTION_PHASES},
}
ROW_KEYS = (
    "time_s",
    "dt_s",
    "power_total_W",
    "power_propulsion_W",
    "power_sensors_W",
    "power_compute_W",
    "power_communications_W",
    "power_auxiliary_W",
    "power_conversion_loss_W",
    "power_battery_loss_W",
    "voltage_V",
    "current_A",
    "soc",
    "battery_temperature_C",
    "derating_factor",
    "battery_state",
    "mission_phase",
)


def final_matrix():
    runs = {}

    def add(label, exp, layout, mapping, current, plan, **extra):
        runs[label] = {
            "label": label,
            "group": exp,
            "layout": layout,
            "mapping": mapping,
            "current_m_s": current,
            "plan": plan,
            **extra,
        }

    def surge(c):
        return [HEAD_ON * c, 0.0, 0.0]

    def oblique(c):
        s = c / 2**0.5
        return [HEAD_ON * s, HEAD_ON * s, 0.0]

    layouts = (
        ("L8-HV", "direct"),
        ("L6-STD", "wrench_equivalent"),
        ("L4-H45", "wrench_equivalent"),
        ("L4-2H2V", "wrench_equivalent"),
        ("L8-VEC30", "wrench_equivalent"),
    )
    for c in (0.2, 0.5):
        for layout, mapping in layouts:
            add(f"EXP3-{layout}-headon{c:g}", "EXP3", layout, mapping, surge(c), "station")
    for layout, mapping in layouts:
        add(f"EXP3-{layout}-oblique0.5", "EXP3", layout, mapping, oblique(0.5), "station")
    add("EXP3-L8-HV-headon0.8", "EXP3", "L8-HV", "direct", surge(0.8), "station")
    add("EXP3-L8-HV-sway0.5", "EXP3", "L8-HV", "direct", [0.0, HEAD_ON * 0.5, 0.0], "station")
    add(
        "EXP3-L4-2H2V-sway0.5",
        "EXP3",
        "L4-2H2V",
        "wrench_equivalent",
        [0.0, HEAD_ON * 0.5, 0.0],
        "station",
    )
    for layout, mapping in (
        ("L8-HV", "direct"),
        ("L6-STD", "wrench_equivalent"),
        ("L4-H45", "wrench_equivalent"),
    ):
        add(f"EXP3-{layout}-heave", "EXP3", layout, mapping, [0, 0, 0], "heave")
    for alpha in (30, 60):
        add(
            f"EXP4-a{alpha}-headon0.5",
            "EXP4",
            f"L8-HV-a{alpha}",
            "wrench_equivalent",
            surge(0.5),
            "station",
        )
        add(
            f"EXP4-a{alpha}-sway0.5",
            "EXP4",
            f"L8-HV-a{alpha}",
            "wrench_equivalent",
            [0.0, HEAD_ON * 0.5, 0.0],
            "station",
        )
    add("EXP5-station-c0", "EXP5", "L8-HV", "direct", [0, 0, 0], "station")
    for c in (0.0, 0.2, 0.4):
        add(f"EXP5-transit-c{c:g}", "EXP5", "L8-HV", "direct", surge(c), "transit")
    for suite, schedule, tag in (
        ("S0-propulsion-only", None, "S0-propulsion-only"),
        ("S5-inspection", None, "S5-inspection-continuous"),
        ("S5-inspection", "inspection-at-site", "S5-inspection-scheduled"),
        ("S6-ai-vision", None, "S6-ai-continuous"),
        ("S6-ai-vision", "ai-at-site", "S6-ai-scheduled"),
    ):
        extra = {"suite": suite} | ({"schedule": schedule} if schedule else {})
        add(f"EXP6-{tag}", "EXP6", "L8-HV", "direct", surge(0.2), "transit", **extra)
    add("EXP8-L0-transit-c0.2", "EXP8", "L8-HV", "direct", surge(0.2), "transit", fidelity="L0")
    add(
        "EXP8-lowsoc-headon0.5",
        "EXP8",
        "L8-HV",
        "direct",
        surge(0.5),
        "station",
        battery={"initial_soc": 0.03},
    )
    return runs


def config_hash(config):
    return hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()


def apply_schedule(env, config, schedule, phase):
    if not schedule:
        return
    for comp in config["components"]:
        phases = SCHEDULES[schedule].get(comp.get("device"))
        if phases is None:
            continue
        on = (
            comp.get("initial_state", "ACTIVE")
            if comp.get("initial_state", "ACTIVE") != "OFF"
            else "ACTIVE"
        )
        env.set_payload_state(comp["name"], on if phase in phases else "OFF")


def tick_row(state, phase, target, wrench, current):
    import numpy as np

    e = state["Energy"]
    a = e["actuation"]
    pose = np.asarray(state["PoseSensor"])
    dyn = np.asarray(state["DynamicsSensor"])
    row = {k: e.get(k) for k in ROW_KEYS}
    row.update(
        phase=phase,
        current_m_s=current,
        position_m=pose[:3, 3].tolist(),
        position_ref_m=target.tolist(),
        com_velocity_m_s=dyn[3:6].tolist(),
        rpy_deg=dyn[15:18].tolist(),
        speed_m_s=e["linear_speed_m_s"],
        requested_wrench=[float(v) for v in wrench],
        allocation_residual_norm=a["allocation_residual_norm"],
        allocation_saturated=any(a["allocation_saturated"]),
        applied_N=list(map(float, e["applied_action"])),
        applied_wrench=a["applied_wrench"],
        backend_N=a["backend_action"],
        backend_residual_norm=a["backend_residual_norm"],
        native_saturated=any(a.get("native_saturated", [])),
        thruster_power_W=e["thruster_power_W"],
        component_power_W=e["component_power_W"],
    )
    return row


def run(spec, binary, parameters, tables):
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
    base = make_env(copy.deepcopy(SCENARIO), round(1 / DT), binary)
    ticks, step_wall, wall0 = [], 0.0, time.perf_counter()
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
                    apply_schedule(env, env.config, spec.get("schedule"), phase)
                velocity_ref = np.array(item["velocity"])
                target = target + velocity_ref * DT
                wrench = controller(state, target, velocity_ref, item["yaw"], item["yaw_rate"])
                t0 = time.perf_counter()
                state = env.step(wrench)
                step_wall += time.perf_counter() - t0
                ticks.append(tick_row(state, phase, target, wrench, current))
            summary = env.energy.summary()
            report = env.energy.report().to_dict()
            describe = env.actuation.describe()
            warnings_ = list(env.warnings)
    finally:
        close = getattr(base, "close", None)
        if close is not None:
            close()
    m = metrics(ticks, summary)
    if spec["plan"] == "station":
        steady = ticks[-round(STEADY_S / DT) :]
        m["steady_window_s"] = STEADY_S
        m["steady_mean_propulsion_W"] = float(np.mean([t["power_propulsion_W"] for t in steady]))
        m["steady_propulsion_Wh"] = float(sum(t["power_propulsion_W"] for t in steady) * DT / 3600)
        m["steady_mean_tracking_error_m"] = m["mean_tail_tracking_error_m"]
        m["steady_derated_fraction"] = float(
            np.mean([t["derating_factor"] < 1 - 1e-9 for t in steady])
        )
    return {
        "spec": spec,
        "layout": meta | describe,
        "config_sha256": config_hash(config),
        "battery": {
            "model": config["battery"].get("model"),
            "internal_resistance_ohm": config["battery"].get("internal_resistance_ohm"),
        },
        "metrics": m,
        "chain": close_chain(ticks, parameters, tables, spec["mapping"]),
        "evidence": summary.get("evidence"),
        "summary": {
            k: summary[k]
            for k in (
                "category_energy_Wh",
                "terminal_energy_Wh",
                "total_ocv_work_Wh",
                "phases",
                "device_energy_Wh",
                "device_state_energy_Wh",
            )
            if k in summary
        },
        "energy_report": report,
        "warnings": warnings_,
        "timing": {
            "wall_s": time.perf_counter() - wall0,
            "env_step_wall_s": step_wall,
            "ticks": len(ticks),
        },
    }, ticks


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "logs/final")
    parser.add_argument("--runs", nargs="*", help="labels or EXP groups; default all")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--skip-existing", action="store_true")
    parser.add_argument("--allow-dirty", action="store_true", help="not for paper-critical runs")
    args = parser.parse_args(argv)
    runs = final_matrix()
    if args.list:
        for label, spec in runs.items():
            print(label, spec["group"])
        return 0
    git = git_state()
    if git.get("dirty") and not args.allow_dirty:
        raise SystemExit(f"Working tree is dirty ({git.get('working_tree_status')}); commit first")
    identity = package_identity(args.binary)
    if identity["build_patch_sha256"] is None:
        raise SystemExit("Refusing an unpatched/unknown package")
    parameters = source_parameters(args.source_dir)["parameters"]
    if parameters["source_drag_scale_to_SI"] != 1:
        raise SystemExit("Source tree does not contain the drag-units patch")
    tables = T200Tables(
        json.loads((ROOT / "holoenergy/profiles/thrusters/bluerobotics_t200.json").read_text())
    )
    registry = default_registry()
    provenance = {
        "holoenergy_version": __version__,
        "git": git,
        "backend": identity,
        "source_parameters": parameters,
        "physics_rate_hz": round(1 / DT),
        "controller": GAINS,
        "station_s": STATION_S,
        "end_hold_s": END_HOLD_S,
        "current_sign_convention": "head-on: station-keeping and transit currents along -x (vehicle faces +x)",
        "steady_window_s": STEADY_S,
        "schedules": SCHEDULES,
        "evidence_registry": {
            "version": registry.version,
            "records": len(registry.records),
            "sources": len(registry.sources),
        },
        "random_seed": "none (deterministic plan, controller and fixed-step physics)",
    }
    selected = [
        k for k, s in runs.items() if not args.runs or k in args.runs or s["group"] in args.runs
    ]
    for label in selected:
        spec = runs[label]
        out = args.output_dir / "results" / spec["group"]
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{label}.summary.json"
        if args.skip_existing and path.exists():
            continue
        print(f"== {label}", flush=True)
        started = datetime.now(timezone.utc).isoformat()
        try:
            result, ticks = run(spec, args.binary, parameters, tables)
        except Exception as exc:  # noqa: BLE001 - failures are recorded, not hidden
            path.with_suffix(".error.json").write_text(
                json.dumps({"spec": spec, "error": repr(exc)}, indent=2), encoding="utf-8"
            )
            print(f"FAILED {label}: {exc!r}", flush=True)
            continue
        full_dir = args.output_dir / "full"
        full_dir.mkdir(parents=True, exist_ok=True)
        full, small = full_dir / f"{label}.trace.jsonl.gz", out / f"{label}.trace10.jsonl.gz"
        content = {"full": write_trace(full, ticks), "small": write_trace(small, downsample(ticks))}
        result["provenance"] = provenance | {"started_utc": started}
        result["traces"] = {
            "full_per_tick": {"path": str(full), "content_sha256": content["full"]},
            "downsampled_0.1s": {"path": small.name, "content_sha256": content["small"]},
        }
        path.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
        m, c = result["metrics"], result["chain"]
        print(
            f"   {c['status']} prop {m['propulsion_Wh']:.4f} Wh total {m['terminal_Wh']:.4f} Wh err {m['mean_tail_tracking_error_m']:.3f} m result {file_hash(path)[:12]}",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
