"""Example-only backend creation; synthetic mode never claims ROV dynamics."""

import argparse
import copy
import json
from pathlib import Path

from holoenergy.config import load_config

ROOT = Path(__file__).resolve().parents[1]


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
        "--scenario", type=Path, help="Native HoloOcean JSON with one BlueROV2 agent"
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
    config["power_manager"]["apply_derating_to_actions"] = True
    config["logging"] = {
        "enabled": True,
        "format": args.log_format,
        "path": str(args.output_dir / f"energy_demo.{args.log_format}"),
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
    scenario = copy.deepcopy(scenario)
    scenario["ticks_per_sec"] = tps
    scenario["agents"][0]["control_scheme"] = 0
    try:
        env = holoocean.make(scenario_cfg=scenario)
    except Exception as exc:
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
