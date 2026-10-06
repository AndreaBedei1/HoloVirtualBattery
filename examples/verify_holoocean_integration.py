"""Opt-in native integration check; launches HoloOcean, never real hardware.

The deliberately imposed 8 A test limit is a simulation intervention, not a
manufacturer rating or calibrated battery parameter.
"""

import copy
import importlib.metadata
import sys

from _common import backend, parser, settings, simulator_action

from holoenergy import EnergyAwareEnv
from holoenergy.provenance import file_hash, run_provenance, write_json


def run(args, config, apply_derating):
    import numpy as np

    config = copy.deepcopy(config)
    config["battery"]["max_current_A"] = 8.0
    metadata = config["battery"].setdefault("metadata", {})
    metadata["datasheet_fields"] = [
        f for f in metadata.get("datasheet_fields", []) if f != "max_current_A"
    ]
    metadata["user_settings"] = [*metadata.get("user_settings", []), "max_current_A"]
    metadata["max_current_A_origin"] = "8 A simulation intervention; not a manufacturer rating"
    config["power_manager"]["apply_derating_to_actions"] = apply_derating
    config["logging"]["path"] = str(
        args.output_dir / f"motion_derating_{str(apply_derating).lower()}.{args.log_format}"
    )
    base, contract = backend(args, config)
    initial = base.reset()
    start = np.asarray(initial["PoseSensor"])[:3, 3].copy()
    times, factors, currents, actions = [], [], [], []
    sent_actions = []
    native_step = base.step

    def recording_step(action, **kwargs):
        sent_actions.append(np.asarray(action).tolist())
        return native_step(action, **kwargs)

    base.step = recording_step
    with EnergyAwareEnv(base, config=config, control_contract=contract) as env:
        env.reset()
        for _ in range(4):
            state = env.step(simulator_action(args, [0.0] * 8))
            assert state["Energy"]["power_propulsion_W"] == 0
            assert sent_actions[-1] == [0.0] * 8
        start = np.asarray(state["PoseSensor"])[:3, 3].copy()
        low = list(base.action_space.get_low())
        high = list(base.action_space.get_high())
        for _ in range(args.steps):
            state = env.step(simulator_action(args, [0.0] * 4 + [20.0] * 4))
            e = state["Energy"]
            assert np.allclose(sent_actions[-1], e["applied_action"], atol=1e-10)
            expected = np.asarray([0.0] * 4 + [20.0] * 4) * (
                e["derating_factor"] if apply_derating else 1
            )
            assert np.allclose(sent_actions[-1], expected, atol=1e-10)
            assert e["dynamics_energy_consistent"] == apply_derating
            assert e["power_total_W"] <= e["available_power_W"] + 1e-6
            assert e["current_A"] <= 8 + 1e-8
            assert all(
                lo <= a <= hi for lo, a, hi in zip(low, e["applied_action"], high, strict=True)
            )
            times.append(float(state["t"]))
            factors.append(e["derating_factor"])
            currents.append(e["current_A"])
            actions.append(e["applied_action"])
        finish = np.asarray(state["PoseSensor"])[:3, 3].copy()
        assert np.isfinite(finish).all()
        assert np.allclose(np.diff(times), env.dt_s, atol=1e-9)
        energy_time = e["time_s"]
        energy_used = e["energy_used_Wh"]
    base.step = native_step
    displacement = finish - start
    return {
        "apply_derating": apply_derating,
        "control_contract": contract,
        "action_low_N": low,
        "action_high_N": high,
        "start_position_m": start.tolist(),
        "end_position_m": finish.tolist(),
        "surge_displacement_m": float(displacement[0]),
        "displacement_norm_m": float(np.linalg.norm(displacement)),
        "minimum_derating_factor": min(factors),
        "max_current_A": max(currents),
        "last_applied_action_N": actions[-1],
        "native_clock_increment_s": times[1] - times[0],
        "energy_time_s": energy_time,
        "terminal_energy_Wh": energy_used,
        "engine_process_closed": base._world_process.poll() is not None,
        "zero_action_ticks": 4,
        "sent_actions_verified": True,
        "provenance": env.logger.metadata,
    }


def main():
    args = parser(__doc__).parse_args()
    if args.backend != "holoocean":
        raise SystemExit("Native integration verification requires --backend holoocean")
    if args.steps < 2:
        raise SystemExit("--steps must be at least 2")
    config = settings(args)
    limited = run(args, config, True)
    uncurtailed = run(args, config, False)
    assert limited["minimum_derating_factor"] < 1
    assert 0 < limited["surge_displacement_m"] < uncurtailed["surge_displacement_m"]
    assert limited["engine_process_closed"] and uncurtailed["engine_process_closed"]
    report = {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "holoocean_version": importlib.metadata.version("holoocean"),
        "scenario": str(args.scenario.resolve()),
        "steps_per_comparison": args.steps,
        "test_current_limit_A": 8.0,
        "test_current_limit_kind": "simulation intervention, not a manufacturer rating",
        "derated": limited,
        "accounting_only": uncurtailed,
        "native_integration_passed": True,
        "physical_energy_model_calibrated": False,
        "sonar_note": "Default scenario renders a camera; sonar load is an electrical proxy",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    path = args.output_dir / "integration_report.json"
    write_json(path, report)
    metadata = run_provenance(config, context={"check": "native motion and lifecycle"})
    metadata.update({"status": "closed", "output_dataset_sha256": file_hash(path)})
    write_json(path.with_suffix(".json.metadata.json"), metadata)
    print("Native integration passed: BlueROV2 pose, timing, current limit and motion derating.")
    print(
        f"Surge displacement: derated {limited['surge_displacement_m']:.6f} m; "
        f"accounting-only {uncurtailed['surge_displacement_m']:.6f} m"
    )
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
