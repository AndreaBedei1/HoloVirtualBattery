"""Independent supplied fixtures: no BlueROV profiles are imported by these tests."""

import copy
import json

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.config import load_config
from holoenergy.models.actuator import ActuatorEnergyModel
from holoenergy.models.propulsion import PropulsionModel


class CustomBackend:
    def __init__(self, count, units="force_N"):
        self.energy_action_contract = {
            "agent_type": "CustomRobot",
            "control_scheme": 0,
            "action_units": units,
            "thruster_count": count,
            "dt_s": 0.1,
        }
        self.actions = []

    def step(self, action):
        self.actions.append(list(action))
        return {"VehicleState": {"linear_speed_m_s": 0, "angular_speed_rad_s": 0, "depth_m": 5}}

    def reset(self):
        return {}

    def close(self):
        pass


def generic_config(count=6):
    return {
        "vehicle": {"name": "MyCustomROV"},
        "simulation": {"dt_s": 0.1},
        "battery": {
            "model": "rint",
            "chemistry": "LiFePO4",
            "capacity_Ah": 30,
            "nominal_voltage_V": 24,
            "initial_soc": 1,
            "internal_resistance_ohm": 0.1,
            "cutoff_voltage_V": 20,
            "max_current_A": 20,
            "ocv_curve": [[0, 21], [1, 26]],
        },
        "actuators": [
            {
                "count": count,
                "model": "custom_lookup",
                "force_power_tables": [
                    {
                        "voltage_V": v,
                        "forward": [[0, 0], [10, 30], [30, 150]],
                        "reverse": [[0, 0], [10, 40], [30, 180]],
                    }
                    for v in (20, 30)
                ],
            }
        ],
        "components": [
            {"name": "sonar", "active_W": 18},
            {"name": "dvl", "active_W": 7},
            {"name": "onboard_computer", "category": "compute", "active_W": 25},
        ],
        "environment": {"water_temperature_C": 8, "current_velocity_m_s": [0, 0, 0]},
        "thermal": {
            "initial_temperature_C": 20,
            "thermal_capacity_J_per_C": 1000,
            "cooling_coeff_W_per_C": 2,
            "derating_temperature_C": 40,
            "cutoff_temperature_C": 50,
        },
        "power_manager": {"apply_derating_to_actions": True},
    }


@pytest.mark.parametrize("count", [1, 4, 6, 8])
def test_arbitrary_actuators_stationary_consumption_and_balance(count):
    with EnergyAwareEnv(CustomBackend(count), config=generic_config(count)) as env:
        row = env.step([5] * count, ticks=3)["Energy"]
        assert row["linear_speed_m_s"] == 0
        assert row["power_propulsion_W"] == pytest.approx(15 * count)
        assert len(row["actuators"]) == count
        assert row["power_total_W"] == pytest.approx(15 * count + 50)
        assert row["chemistry"] == "LiFePO4"
        assert env.energy.summary()["terminal_energy_Wh"] == pytest.approx(row["energy_used_Wh"])
        assert sum(row["actuator_energy_Wh"].values()) == pytest.approx(15 * count * 0.3 / 3600)


def test_mixed_models_no_velocity_dependency():
    config = generic_config(1)
    config["actuators"][0]["id"] = "main"
    other = copy.deepcopy(config["actuators"][0])
    other["id"] = "secondary"
    for table in other["force_power_tables"]:
        table["forward"] = [[0, 0], [10, 60], [30, 250]]
    config["actuators"].append(other)
    with EnergyAwareEnv(CustomBackend(2), config=config) as env:
        row = env.step([5, 5])["Energy"]
        assert row["actuator_power_W"] == pytest.approx({"main": 15, "secondary": 30})
        assert isinstance(env.propulsion.actuators[0], ActuatorEnergyModel)


@pytest.mark.parametrize(
    "suite",
    [
        [],
        [{"name": "sensor", "active_W": 7.2}],
        [{"name": f"s{i}", "active_W": 2} for i in range(30)],
    ],
)
def test_arbitrary_sensor_suite(suite):
    config = generic_config(1)
    config["components"] = suite
    with EnergyAwareEnv(CustomBackend(1), config=config) as env:
        row = env.step([5])["Energy"]
        assert row["power_payload_W"] == pytest.approx(sum(c["active_W"] for c in suite))


def test_variable_load_state_transitions_reset_and_phases(tmp_path):
    config = generic_config(1)
    config["components"] = [
        {
            "name": "custom",
            "category": "compute",
            "initial_state": "STARTING",
            "startup_duration_s": 0.15,
            "states": {"STARTING": 20, "ACTIVE": 5, "PROCESSING": 10},
            "power_model": {
                "type": "lookup",
                "input": "compute_load",
                "initial_value": 0,
                "points": [[0, 5], [1, 15]],
            },
        }
    ]
    config["logging"] = {"enabled": True, "format": "csv", "path": str(tmp_path / "energy.csv")}
    with EnergyAwareEnv(CustomBackend(1), config=config) as env:
        env.energy.mark_phase("inspection")
        first = env.step([0], ticks=2)["Energy"]
        assert first["power_compute_W"] == pytest.approx(16.25)
        env.energy.set_component_input("custom", compute_load=0.5)
        assert env.step([0])["Energy"]["power_compute_W"] == 10
        env.energy.set_component_state("custom", "PROCESSING")
        env.energy.mark_phase("return")
        env.step([0])
        summary = env.energy.summary()
        assert set(summary["phases"]) == {"inspection", "return"}
        assert sum(x["terminal_energy_Wh"] for x in summary["phases"].values()) == pytest.approx(
            summary["terminal_energy_Wh"]
        )
        env.energy.export_summary(tmp_path / "summary.json")
        env.energy.export_summary(tmp_path / "summary.csv")
        with pytest.raises(ConfigurationError):
            env.energy.set_component_input("custom", compute_load=2)
        with pytest.raises(ConfigurationError):
            env.energy.set_component_state("custom", "UNCONFIGURED")
        env.reset()
        assert env.energy.summary()["terminal_energy_Wh"] == 0
    assert json.loads((tmp_path / "summary.json").read_text())["device_energy_Wh"]["custom"] > 0


def test_water_temperature_changes_heat_exchange_not_charge():
    config = generic_config(1)
    with (
        EnergyAwareEnv(CustomBackend(1), config=config) as cold,
        EnergyAwareEnv(CustomBackend(1), config=config) as warm,
    ):
        warm.energy.set_environment(water_temperature_C=30)
        a, b = cold.step([0], ticks=20)["Energy"], warm.step([0], ticks=20)["Energy"]
        assert a["battery_temperature_C"] < b["battery_temperature_C"]
        soc = warm.battery.soc
        warm.energy.set_environment(water_temperature_C=5)
        assert warm.battery.soc == soc
        assert warm.step([0])["Energy"]["water_temperature_C"] == 5


def test_native_current_is_explicit_no_battery_multiplier():
    base = CustomBackend(1)
    base.energy_action_contract["agent_name"] = "custom"
    calls = []
    base.set_ocean_currents = lambda n, v: calls.append((n, v))
    with EnergyAwareEnv(base, config=generic_config(1)) as env:
        env.energy.set_environment(current_velocity_m_s=[0.5, 0, 0], current_mode="native")
        row = env.step([5])["Energy"]
        assert calls == [("custom", [0.5, 0, 0])]
        assert row["power_propulsion_W"] == 15
        with pytest.raises(ConfigurationError, match="water-density"):
            env.energy.set_environment(water_density_kg_m3=1025)


def test_physical_payload_requires_explicit_dynamics_adapter():
    config = generic_config(1)
    config["vehicle"].update(
        dynamics_mode="adapter",
        payload={"mass_kg": 5, "displaced_volume_m3": 0.005, "position_m": [0, 0, 0]},
    )
    with pytest.raises(ConfigurationError, match="configure_vehicle"):
        EnergyAwareEnv(CustomBackend(1), config=config)

    class Adapter:
        def configure_vehicle(self, profile):
            self.profile = profile

        def set_environment(self, values):
            self.environment = values

    adapter = Adapter()
    with EnergyAwareEnv(CustomBackend(1), config=config, dynamics_adapter=adapter) as env:
        assert adapter.profile.config["payload"]["mass_kg"] == 5
        env.energy.set_environment(current_mode="adapter", water_density_kg_m3=997)
        assert adapter.environment["water_density_kg_m3"] == 997
        assert env.step([5])["Energy"]["vehicle_dynamics_status"] == "applied_by_explicit_adapter"


@pytest.mark.parametrize("chemistry", ["Li-ion", "LiPo", "LiFePO4", "NiMH", "custom"])
def test_chemistry_is_descriptive_not_coefficients(chemistry):
    config = generic_config(1)
    config["battery"]["chemistry"] = chemistry
    with EnergyAwareEnv(CustomBackend(1), config=config) as env:
        assert env.step([5])["Energy"]["power_total_W"] == pytest.approx(65)


@pytest.mark.parametrize(
    "case", ["duplicate", "negative_power", "invalid_curve", "voltage", "missing_state"]
)
def test_strong_generic_validation(case):
    config = generic_config(1)
    if case == "duplicate":
        config["actuators"] = [dict(config["actuators"][0], id="a")] * 2
    elif case == "negative_power":
        config["components"][0]["active_W"] = -1
    elif case == "invalid_curve":
        config["actuators"][0]["force_power_tables"][0]["forward"] = [[0, 0], [10, 10], [5, 20]]
    elif case == "voltage":
        config["battery"]["ocv_curve"] = [[0, 31], [1, 32]]
    else:
        config["components"][0]["initial_state"] = "STARTING"
    with pytest.raises(ValueError):
        with EnergyAwareEnv(CustomBackend(2 if case == "duplicate" else 1), config=config) as env:
            env.step([5])


@pytest.mark.parametrize("path,count", [("generic_lightweight_rov", 4), ("generic_auv", 1)])
def test_generic_packaged_configs(path, count):
    with pytest.warns(UserWarning):
        config = load_config(data={"profile": f"package:vehicles/{path}.yaml"})
    config["simulation"]["dt_s"] = 0.1
    with pytest.warns(UserWarning), EnergyAwareEnv(CustomBackend(count), config=config) as env:
        assert env.step([1] * count)["Energy"]["power_propulsion_W"] > 0


def test_force_only_has_no_invented_normalized_command():
    config = load_config(data=generic_config(1))
    config["propulsion"]["action_units"] = "normalized_command"
    with pytest.raises(ConfigurationError, match="Force-only"):
        PropulsionModel(config["propulsion"])
