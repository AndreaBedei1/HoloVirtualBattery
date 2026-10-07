"""Example-only backend creation; synthetic mode never claims ROV dynamics."""

import argparse
import copy
import json
import sys
from pathlib import Path

from holoenergy.config import load_config
from holoenergy.provenance import file_hash

ROOT = Path(__file__).resolve().parents[1]
# UE 5.3 integrates at most MaxPhysicsDeltaTime = 1/30 s per tick without substepping;
# a longer energy step would integrate energy over time the physics never simulated.
NATIVE_MAX_DT_S = 1 / 30
# Native rate verified by tools/audit_holoocean_timestep.py and the drag audit.
NATIVE_DEFAULT_DT_S = 0.01


class SyntheticThrusterEnv:
    def __init__(self, dt_s=0.05):
        self.energy_action_contract = {
            "agent_type": "BlueROV2",
            "control_scheme": 0,
            "action_units": "force_N",
            "thruster_count": 8,
            "dt_s": dt_s,
        }
        self.last_action = [0.0] * 8
        self.closed = False

    def step(self, action, **kwargs):
        self.last_action = list(action)
        return {"Backend": "synthetic; energy only, no vehicle dynamics"}

    def reset(self):
        self.last_action = [0.0] * 8
        return {"Backend": "synthetic; energy only, no vehicle dynamics"}

    def close(self):
        self.closed = True


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--backend", choices=["holoocean", "synthetic"], default="holoocean")
    result.add_argument(
        "--scenario",
        type=Path,
        default=ROOT / "configs/bluerov2_holoocean.json",
        help="Native HoloOcean JSON with one BlueROV2 agent",
    )
    result.add_argument("--show-viewport", action="store_true", help="Show the simulator window")
    result.add_argument(
        "--holoocean-binary",
        type=Path,
        help="Executable of a separately built Ocean package (e.g. the drag-patched build)",
    )
    result.add_argument(
        "--dt",
        type=float,
        help=f"Energy and simulator step in s; native default {NATIVE_DEFAULT_DT_S} (verified)",
    )
    result.add_argument("--config", type=Path, default=ROOT / "configs/bluerov2_energy.yaml")
    result.add_argument("--steps", type=int, default=300)
    result.add_argument("--output-dir", type=Path, default=ROOT / "logs")
    result.add_argument("--log-format", choices=["jsonl", "csv"], default="jsonl")
    return result


def settings(args):
    if args.steps <= 0:
        raise ValueError("--steps must be positive")
    config = load_config(args.config)
    dt = getattr(args, "dt", None)
    if dt is None and args.backend == "holoocean":
        dt = NATIVE_DEFAULT_DT_S
    if dt is not None:
        if not dt > 0:
            raise ValueError("--dt must be positive")
        config["simulation"]["dt_s"] = dt
    config["power_manager"]["apply_derating_to_actions"] = True
    config["logging"] = {
        "enabled": True,
        "format": args.log_format,
        "path": str(args.output_dir / f"energy_demo.{args.log_format}"),
    }
    config["provenance"] = {
        "purpose": "software demonstration; not physical validation",
        "calibration_status": "uncalibrated demonstration",
        "scenario": {
            "backend": args.backend,
            "path": str(args.scenario.resolve()),
            "sha256": file_hash(args.scenario),
            "definition": json.loads(args.scenario.read_text(encoding="utf-8")),
            "overrides": {
                "ticks_per_sec": round(1 / config["simulation"]["dt_s"]),
                "frames_per_sec": False,
            },
            "holoocean_binary": str(binary)
            if (binary := getattr(args, "holoocean_binary", None))
            else None,
        },
    }
    return config


def backend(args, config):
    dt = config["simulation"]["dt_s"]
    contract = {
        "agent_type": "BlueROV2",
        "control_scheme": 0,
        "action_units": "force_N",
        "thruster_count": 8,
        "dt_s": dt,
    }
    if args.backend == "synthetic":
        return SyntheticThrusterEnv(dt), contract
    try:
        import holoocean
    except ImportError as exc:
        raise RuntimeError(
            "HoloOcean is not installed in this Python environment. Install HoloOcean and a "
            "world package using its official documentation, or explicitly use --backend synthetic."
        ) from exc
    if args.scenario is None:
        raise RuntimeError("--backend holoocean requires --scenario path/to/native_scenario.json")
    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    agents = scenario.get("agents", [])
    if len(agents) != 1 or agents[0].get("agent_type") != "BlueROV2":
        raise ValueError("Scenario must contain exactly one BlueROV2 Heavy agent")
    if agents[0].get("control_scheme", 0) != 0:
        raise ValueError("Scenario must use direct thruster control_scheme 0")
    tps = round(1 / dt)
    if abs(tps * dt - 1) > 1e-9:
        raise ValueError("dt_s must equal the reciprocal of an integer ticks_per_sec")
    if dt > NATIVE_MAX_DT_S + 1e-12:
        raise ValueError(
            f"dt_s={dt} exceeds the UE 5.3 physics step cap of 1/30 s (MaxPhysicsDeltaTime, "
            "no substepping): HoloOcean would integrate less time than the energy model. "
            f"Use dt_s <= 1/30; {NATIVE_DEFAULT_DT_S} s is verified "
            "(see docs/holoocean_timestep_report.md)."
        )
    scenario = copy.deepcopy(scenario)
    scenario["ticks_per_sec"] = tps
    scenario["frames_per_sec"] = False
    scenario["agents"][0]["control_scheme"] = 0
    contract["agent_name"] = scenario["agents"][0]["agent_name"]
    binary = getattr(args, "holoocean_binary", None)
    env = None
    try:
        if binary is None:
            env = holoocean.make(
                scenario_cfg=scenario,
                ticks_per_sec=tps,
                frames_per_sec=False,
                show_viewport=getattr(args, "show_viewport", False),
            )
        else:
            sys.path.insert(0, str(ROOT))
            from tools.holoocean_backend import make_env

            env = make_env(
                scenario, tps, binary, show_viewport=getattr(args, "show_viewport", False)
            )
        env.reset()
    except Exception as exc:
        if env is not None:
            close = getattr(env, "close", None)
            if close is not None:
                close()
            else:
                env.__exit__(None, None, None)
        raise RuntimeError(
            f"HoloOcean failed to start {args.scenario}: {exc}. "
            "Check world installation, simulator binary, GPU and native scenario validity."
        ) from exc
    return env, contract


def action_for_step(step):
    # Forces in N, in the documented order of four vertical then four angled thrusters.
    phase = (step // 50) % 6
    if phase == 0:
        return [0.0] * 8
    if phase == 1:
        return [5.0] * 4 + [0.0] * 4
    if phase == 2:
        return [0.0] * 4 + [10.0] * 4
    if phase == 3:
        return [0.0] * 4 + [10.0, -10.0, 10.0, -10.0]
    if phase == 4:
        return [50.0] * 8  # deliberately requests more than the continuous pack can supply
    return [0.0] * 8


def simulator_action(args, action):
    if args.backend == "holoocean":
        import numpy as np  # provided with HoloOcean, not required by the energy models

        return np.asarray(action, dtype=float)
    return action
