"""Evidence links inherited from a profile must not survive a change of the linked value."""

import warnings

from holoenergy import EnergyAwareEnv

CONTRACT = {
    "agent_type": "BlueROV2",
    "control_scheme": 0,
    "action_units": "force_N",
    "thruster_count": 8,
    "dt_s": 0.01,
}


class Backend:
    def step(self, action):
        return {}

    def reset(self):
        return {}

    def close(self):
        pass


def make(**kwargs):
    warnings.simplefilter("ignore", UserWarning)
    return EnergyAwareEnv(
        Backend(), vehicle_profile="bluerov2-heavy", control_contract=CONTRACT, **kwargs
    )


def stale(env):
    return [w for w in env.warnings if w.startswith("stale evidence link")]


def test_unmodified_profile_keeps_its_links():
    env = make()
    assert stale(env) == []
    assert env.evidence_map.battery_loss_grade == "C"
    assert env.evidence_map.propulsion_grade == "B"  # static curves, installed in flow
    env.close()


def test_overridden_battery_resistance_is_graded_user():
    env = make(overrides={"battery": {"internal_resistance_ohm": 0.03}})
    assert env.evidence_map.battery_loss_grade == "D"
    assert env.evidence_map.battery_loss_record is None
    assert any("battery_loss" in w for w in stale(env))
    for _ in range(10):
        env.step([0, 0, 0, 0, 10, 10, 10, 10])
    summary = env.energy.summary()["evidence"]
    assert summary["energy_Wh"]["D"] > 0
    env.close()


def test_replaced_actuator_tables_drop_the_t200_link():
    table = {"forward": [[0, 0], [30, 300]], "reverse": [[0, 0], [25, 300]]}
    user_thruster = {
        "model": "user_lookup",
        "force_power_tables": [{"voltage_V": 12, **table}, {"voltage_V": 17, **table}],
    }
    actuators = [{"id": f"T{i}", **user_thruster, "backend_index": i} for i in range(8)]
    env = make(overrides={"actuators": actuators})
    assert env.evidence_map.propulsion_grade == "D"
    assert any("propulsion" in w for w in stale(env))
    env.close()


def test_resistance_temperature_factors_make_the_battery_loss_link_stale():
    """Review C-03: a resistance curve not in the record must not keep its grade."""
    env = make(overrides={"battery": {"resistance_temperature_curve": [[0.0, 3.0], [40.0, 1.0]]}})
    assert env.evidence_map.battery_loss_grade == "D"
    assert any("resistance temperature factors" in w for w in stale(env))
    env.close()


def test_placeholder_ocv_dependence_is_reported():
    """Review C-04: energy that depends on the bus voltage inherits the placeholder OCV."""
    env = make()
    for _ in range(20):
        env.step([0, 0, 0, 0, 10, 10, 10, 10])
    dep = env.energy.summary()["evidence"]["voltage_dependence"]
    assert dep["ocv_grade"] == "D"
    assert dep["voltage_dependent_energy_Wh"] > 0
    env.close()
