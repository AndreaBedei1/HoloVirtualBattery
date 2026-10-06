import csv
import json

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError


def test_component_balance_and_existing_state_preserved(fake, config):
    with EnergyAwareEnv(fake, config=config) as env:
        state = env.step([10.0] * 8)
        e = state["Energy"]
        assert state["Sensor"] is fake.state["Sensor"]
        assert "Energy" not in fake.state
        assert e["power_total_W"] == pytest.approx(
            sum(
                e[k]
                for k in [
                    "power_propulsion_W",
                    "power_payload_W",
                    "power_hotel_W",
                    "power_conversion_loss_W",
                ]
            )
        )
        assert e["power_propulsion_W"] == pytest.approx(sum(e["thruster_power_W"]))
        assert e["power_payload_W"] == pytest.approx(sum(e["sensor_power_W"].values()))
        assert e["energy_used_Wh"] == pytest.approx(e["power_total_W"] * 0.1 / 3600)
        assert e["chemical_energy_used_Wh"] == pytest.approx(
            e["energy_used_Wh"] + e["battery_internal_loss_Wh"]
        )


def test_derating_is_applied_before_simulation(fake, config):
    with EnergyAwareEnv(fake, config=config) as env:
        original = [40.0] * 8
        e = env.step(original)["Energy"]
        assert 0 < e["derating_factor"] < 1
        assert e["current_A"] <= 20 + 1e-8
        assert e["battery_state"] == "POWER_LIMITED"
        assert fake.actions[-1] == pytest.approx(e["applied_action"])
        assert original == [40] * 8
        assert e["dynamics_energy_consistent"]


def test_public_simulator_force_bounds_limit_modelled_actions(fake, config):
    class ActionSpace:
        shape = [8]

        def get_low(self):
            return [-10] * 8

        def get_high(self):
            return [10] * 8

    fake.action_space = ActionSpace()
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([40.0] * 8)["Energy"]
        assert e["derating_factor"] == pytest.approx(0.25)
        assert fake.actions[-1] == pytest.approx([10] * 8)
        assert e["power_propulsion_W"] == pytest.approx(200)
        assert e["power_total_W"] == pytest.approx(218.75)


def test_runtime_pid_action_space_is_rejected_before_advancing(fake, config):
    fake.action_space = type("PIDSpace", (), {"shape": [6]})()
    with EnergyAwareEnv(fake, config=config) as env:
        with pytest.raises(ConfigurationError, match="direct thruster vector"):
            env.step([5] * 8)
        assert not fake.actions


def test_nonlinear_derating_solves_action_curve_rather_than_watt_ratio(fake, config):
    tables = config["propulsion"]["thruster"]["voltage_tables"]
    for table in tables:
        for direction in ("forward", "reverse"):
            table[direction][1]["power_W"] = 10
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([40.0] * 8)["Energy"]
        # Fixture branch: per-thruster P=3F-20, auxiliaries=18.75 W, supply=280 W.
        expected = (280 - 18.75 + 160) / (24 * 40)
        assert e["derating_factor"] == pytest.approx(expected, abs=1e-8)
        assert e["derating_factor"] > e["available_power_W"] / e["requested_power_W"]
        assert e["power_total_W"] == pytest.approx(280, abs=1e-6)


def test_nonzero_thrust_below_measured_voltage_domain_fails(fake, config):
    config["battery"]["ocv_curve"] = [[0, 7], [1, 8]]
    config["battery"]["cutoff_voltage_V"] = 5
    with EnergyAwareEnv(fake, config=config) as env:
        with pytest.raises(ValueError, match="below.*measured"):
            env.step([5.0] * 8)
        assert not fake.actions


def test_context_manager_backend_can_be_closed_without_close_method(config):
    class ContextOnlyEnv:
        def __init__(self):
            self.exited = False

        def __exit__(self, *args):
            self.exited = True

    config["power_manager"]["apply_derating_to_actions"] = False
    base = ContextOnlyEnv()
    with EnergyAwareEnv(base, config=config):
        pass
    assert base.exited


def test_accounting_only_marks_dynamics_mismatch(fake, config):
    config["power_manager"]["apply_derating_to_actions"] = False
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([40.0] * 8)["Energy"]
        assert fake.actions[-1] == [40] * 8
        assert e["derating_factor"] < 1
        assert not e["dynamics_energy_consistent"]


@pytest.mark.parametrize("thermal", [True, False])
def test_cutoff_removes_thruster_actions(fake, config, thermal):
    if thermal:
        config["thermal"]["initial_temperature_C"] = 51
    else:
        config["battery"]["cutoff_voltage_V"] = 17
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([10.0] * 8)["Energy"]
        assert e["battery_state"] == "CUTOFF"
        assert e["power_total_W"] == 0
        assert fake.actions[-1] == [0] * 8


def test_fixed_load_shortfall_preserves_accounting(fake, config):
    config["battery"]["max_current_A"] = 0.1
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([5.0] * 8)["Energy"]
        assert e["auxiliary_service_factor"] < 1
        assert e["power_propulsion_W"] == 0
        assert e["power_payload_W"] < 5
        assert e["unmet_power_W"] > 0


def test_ticks_integrate_all_intervals_and_reset(fake, config):
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([5.0] * 8, ticks=10)["Energy"]
        assert len(fake.actions) == 10
        assert e["time_s"] == pytest.approx(1)
        assert e["dt_s"] == pytest.approx(1)
        assert e["energy_used_Wh"] == pytest.approx(e["power_total_W"] / 3600)
        env.reset()
        assert env.battery.soc == 1 and env.battery.energy_used_Wh == 0
        assert env.thermal.temperature_C == 20 and env.time_s == 0


@pytest.mark.parametrize("format", ["csv", "jsonl"])
def test_log_one_row_per_step_and_metadata(fake, config, tmp_path, format):
    path = tmp_path / f"energy.{format}"
    config["logging"] = {"enabled": True, "format": format, "path": str(path)}
    with EnergyAwareEnv(fake, config=config) as env:
        env.step([5.0] * 8, ticks=5)
        env.step([0.0] * 8)
    if format == "jsonl":
        rows = [json.loads(line) for line in path.read_text().splitlines()]
    else:
        with path.open() as f:
            rows = list(csv.DictReader(f))
        assert len(json.loads(rows[0]["thruster_power_W"])) == 8
    assert len(rows) == 2
    assert float(rows[0]["dt_s"]) == pytest.approx(0.5)
    metadata = json.loads(path.with_suffix(path.suffix + ".metadata.json").read_text())
    assert metadata["run_id"] == rows[0]["run_id"]
    assert metadata["resolved_config"]["battery"]["capacity_Ah"] == 10


def test_invalid_control_contract_rejected(fake, config):
    fake.energy_action_contract["control_scheme"] = 1
    with pytest.raises(ConfigurationError, match="control_scheme"):
        EnergyAwareEnv(fake, config=config)


def test_derating_requires_contract(config):
    class AnonymousEnv:
        pass

    with pytest.raises(ConfigurationError, match="requires control_contract"):
        EnergyAwareEnv(AnonymousEnv(), config=config)


def test_invalid_action_does_not_advance(fake, config):
    with EnergyAwareEnv(fake, config=config) as env:
        for action in ([1] * 6, [float("nan")] * 8):
            with pytest.raises(ValueError):
                env.step(action)
        assert not fake.actions and env.time_s == 0


def test_backend_failure_faults_wrapper_without_charging_failed_tick(fake, config, tmp_path):
    config["logging"] = {
        "enabled": True,
        "format": "jsonl",
        "path": str(tmp_path / "partial.jsonl"),
    }
    fake.fail_on = 1
    with EnergyAwareEnv(fake, config=config) as env:
        with pytest.raises(RuntimeError, match="backend failed"):
            env.step([5] * 8, ticks=3)
        assert env.time_s == pytest.approx(0.1)
        with pytest.raises(RuntimeError, match="reset"):
            env.step([5] * 8)
        row = json.loads((tmp_path / "partial.jsonl").read_text())
        assert not row["step_completed"]
        fake.fail_on = None
        env.reset()
        assert env.step([0] * 8)["Energy"]["episode"] == 1
