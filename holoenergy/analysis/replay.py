"""Replay an explicit fixed-tick command history against independent model runs."""

import copy
import csv
import json
from pathlib import Path
from time import perf_counter

from .. import EnergyAwareEnv
from .._validation import ConfigurationError, number
from ..config import with_fidelity
from ..provenance import digest, write_json
from .metrics import summarize


class ReplayBackend:
    """Energy-only backend. No position, velocity or mission success is simulated."""

    def __init__(self, config):
        sim, propulsion = config["simulation"], config["propulsion"]
        self.energy_action_contract = {
            "agent_type": sim.get("expected_agent_type", "explicit_replay"),
            "control_scheme": sim.get("control_scheme", 0),
            "action_units": propulsion["action_units"],
            "thruster_count": propulsion["thruster_count"],
            "dt_s": sim["dt_s"],
        }
        if "agent_name" in sim:
            self.energy_action_contract["agent_name"] = sim["agent_name"]

    def step(self, action):
        return {"Backend": "energy-only command replay; no vehicle dynamics"}

    def close(self):
        pass


def read_mission(path, dt_s):
    """CSV rows are tick-starts in seconds; actions are force/command JSON arrays."""
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for i, row in enumerate(rows):
        t = number(float(row["time_s"]), "mission time_s", minimum=0)
        if abs(t - i * dt_s) > 1e-8 * max(1, t):
            raise ConfigurationError("Mission must start at 0 with one row per configured dt_s")
        item = {"action": json.loads(row["action"])}
        if row.get("sensor_states"):
            item["sensor_states"] = json.loads(row["sensor_states"])
        if row.get("water_temperature_C"):
            item["water_temperature_C"] = number(
                float(row["water_temperature_C"]), "water_temperature_C", minimum=-273.14
            )
        result.append(item)
    if not result:
        raise ConfigurationError("Mission has no command rows")
    return result


def run_mission(
    config,
    commands,
    output_dir,
    *,
    backend_factory=None,
    action_adapter=None,
    completion_observer=None,
    reserve_soc=None,
    input_path=None,
    seed=None,
):
    """Factory(config)->(reset backend, contract); observer(state)->bool defines a real goal.

    No completion observer means mission_completed=null, including energy-only runs.
    Wrapper and backend step times are measured separately; startup is excluded.
    """
    commands = copy.deepcopy(list(commands))
    if not commands:
        raise ConfigurationError("Mission must contain at least one tick")
    config = copy.deepcopy(config)
    output_dir = Path(output_dir)
    config["logging"] = {
        "enabled": True,
        "format": "jsonl",
        "path": str(output_dir / "energy.jsonl"),
    }
    provenance = config.setdefault("provenance", {})
    provenance["random_seed"] = seed
    provenance.setdefault("purpose", "model comparison / sensitivity; no physical validation")
    if input_path is not None:
        provenance["input_datasets"] = [str(Path(input_path).resolve())]
    if backend_factory is None:
        base = ReplayBackend(config)
        contract = base.energy_action_contract
        provenance["scenario"] = "energy-only replay"
    else:
        base, contract = backend_factory(config)
    rows, backend_seconds, wrapped_seconds = [], 0.0, 0.0
    completion, completion_time = None if completion_observer is None else False, None
    original_step = base.step

    def timed_step(action, **kwargs):
        nonlocal backend_seconds
        start = perf_counter()
        try:
            return original_step(action, **kwargs)
        finally:
            backend_seconds += perf_counter() - start

    base.step = timed_step
    try:
        with EnergyAwareEnv(base, config=config, control_contract=contract) as env:
            for item in commands:
                action = item["action"]
                for name, state in item.get("sensor_states", {}).items():
                    env.set_payload_state(name, state)
                if "water_temperature_C" in item:
                    env.energy.set_environment(water_temperature_C=item["water_temperature_C"])
                if "phase" in item:
                    env.energy.mark_phase(item["phase"])
                for name, state in item.get("component_states", {}).items():
                    env.energy.set_component_state(name, state)
                for name, inputs in item.get("component_inputs", {}).items():
                    env.energy.set_component_input(name, **inputs)
                start = perf_counter()
                state = env.step(action if action_adapter is None else action_adapter(action))
                wrapped_seconds += perf_counter() - start
                rows.append(state["Energy"])
                if completion_observer is not None and completion_observer(state):
                    if not completion:
                        completion, completion_time = True, rows[-1]["time_s"]
        metadata = env.logger.metadata
    finally:
        base.step = original_step
        # Covers constructor failures as well as normal context-managed shutdown.
        if "env" not in locals():
            close = getattr(base, "close", None)
            if close is not None:
                close()
            elif getattr(base, "__exit__", None) is not None:
                base.__exit__(None, None, None)
    metrics = summarize(
        rows,
        mission_completed=completion,
        completion_time_s=completion_time,
        reserve_soc=reserve_soc,
    )
    metrics.update(
        {
            "backend_step_wall_time_s": backend_seconds,
            "wrapped_step_wall_time_s": wrapped_seconds,
            "wrapper_overhead_s": max(0, wrapped_seconds - backend_seconds),
        }
    )
    metadata.update(
        {
            "command_history_sha256": digest(commands),
            "command_history": commands,
            "status": "closed",
            "mission_metrics": metrics,
        }
    )
    write_json(output_dir / "energy.jsonl.metadata.json", metadata)
    write_json(output_dir / "metrics.json", metrics)
    return {"metrics": metrics, "provenance": metadata, "output_dir": str(output_dir)}


def compare_models(config, commands, output_dir, *, levels=("L0", "L1"), **kwargs):
    commands = list(commands)
    results = {
        level: run_mission(
            with_fidelity(config, level), commands, Path(output_dir) / level, **kwargs
        )
        for level in levels
    }
    write_json(Path(output_dir) / "comparison.json", results)
    with (Path(output_dir) / "comparison.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["metric", *levels])
        for metric in next(iter(results.values()))["metrics"]:
            writer.writerow([metric, *(results[level]["metrics"][metric] for level in levels)])
    return results
