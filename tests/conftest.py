import copy

import pytest


@pytest.fixture
def battery_config():
    return {
        "model": "rint",
        "capacity_Ah": 10,
        "nominal_voltage_V": 16,
        "initial_soc": 1,
        "internal_resistance_ohm": 0.1,
        "cutoff_voltage_V": 10,
        "max_current_A": 20,
        "ocv_curve": [[0, 10], [1, 16]],
    }


@pytest.fixture
def thermal_config():
    return {
        "water_temperature_C": 15,
        "initial_temperature_C": 20,
        "thermal_capacity_J_per_C": 1000,
        "cooling_coeff_W_per_C": 2,
        "derating_temperature_C": 40,
        "cutoff_temperature_C": 50,
    }


@pytest.fixture
def thruster_config():
    branch = [
        {"command": 0, "force_N": 0, "power_W": 0},
        {"command": 0.5, "force_N": 10, "power_W": 25},
        {"command": 1, "force_N": 40, "power_W": 100},
    ]
    return {
        "model": "synthetic_test_fixture",
        "voltage_tables": [
            {"voltage_V": 10, "forward": branch, "reverse": copy.deepcopy(branch)},
            {"voltage_V": 20, "forward": branch, "reverse": copy.deepcopy(branch)},
        ],
    }


@pytest.fixture
def config(battery_config, thermal_config, thruster_config):
    return {
        "schema_version": 1,
        "simulation": {"dt_s": 0.1, "expected_agent_type": "BlueROV2", "control_scheme": 0},
        "battery": battery_config,
        "thermal": thermal_config,
        "propulsion": {"thruster_count": 8, "action_units": "force_N", "thruster": thruster_config},
        "hotel_load": {"constant_W": 10},
        "sensors": {
            "Sonar": {
                "initial_state": "ACTIVE",
                "states": {
                    "off_W": 0,
                    "idle_W": 2,
                    "active_W": 5,
                    "startup_W": 20,
                    "startup_duration_s": 1,
                    "ping_W": 30,
                    "ping_duration_s": 0.1,
                },
            }
        },
        "converters": {
            "propulsion_efficiency": 1,
            "payload_efficiency": 0.8,
            "hotel_efficiency": 0.8,
        },
        "power_manager": {"apply_derating_to_actions": True},
        "logging": {"enabled": False},
    }


class FakeEnv:
    def __init__(self, dt=0.1):
        self.energy_action_contract = {
            "agent_type": "BlueROV2",
            "control_scheme": 0,
            "action_units": "force_N",
            "thruster_count": 8,
            "dt_s": dt,
        }
        self.actions = []
        self.state = {"Sensor": object()}
        self.fail_on = None
        self.closed = False

    def step(self, action, **kwargs):
        if len(self.actions) == self.fail_on:
            raise RuntimeError("backend failed")
        self.actions.append(list(action))
        return self.state

    def reset(self):
        self.actions.clear()
        return self.state

    def close(self):
        self.closed = True


@pytest.fixture
def fake():
    return FakeEnv()
