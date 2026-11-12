"""Regression tests for the independent software review of the v0.2 phase."""

import math
import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.catalog import modem_profile, vehicle_config
from holoenergy.config import load_config
from holoenergy.integrations import ModemPowerProfile
from holoenergy.integrations.desert import DesertEnergyAdapter

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


class Source:
    """Minimal load source returning scripted per-state energies (J) per window."""

    category = "communications"

    def __init__(self, windows, device="src.dev", caps=()):
        self.windows, self.device, self.caps = list(windows), device, caps

    def consume(self, t_end):
        return {self.device: self.windows.pop(0) if self.windows else {}}

    def grades(self):
        return {self.device: {"A": "B", "B": "D"}}

    def capabilities(self):
        return list(self.caps)


def make(profile="bluerov2-heavy", **kwargs):
    warnings.simplefilter("ignore", UserWarning)
    contract = kwargs.pop("contract", CONTRACT)
    return EnergyAwareEnv(Backend(), vehicle_profile=profile, control_contract=contract, **kwargs)


def acoustic():
    return ModemPowerProfile.from_mapping(modem_profile("evologics-s2cm-18-34-1000m"))


def test_rejected_attach_leaves_no_state():
    env = make(overrides={"evidence": {"double_counting": "error"}})
    env.attach(Source([], device="a.dev", caps=["x"]))
    with pytest.raises(ConfigurationError, match="double counting rejected"):
        env.attach(Source([], device="b.dev", caps=["x"]))
    assert env.evidence_map.double_counting == {}
    assert "b.dev" not in env.evidence_map.devices
    env.attach(Source([], device="c.dev", caps=["y"]))  # unrelated source still accepted
    env.close()


def test_scaled_proxy_propulsor_table_is_a_stale_link():
    data = vehicle_config("torpedo-remus-like")
    base = load_config(data=data)
    spec = dict(base["propulsion"]["thruster"])
    spec["force_power_tables"] = [
        {**t, "forward": [[f, p / 2] for f, p in t["forward"]]} for t in spec["force_power_tables"]
    ]
    actuators = [
        {"id": "P1", **spec, "position_m": [-1.2, 0, 0], "direction": [1, 0, 0], "backend_index": 0}
    ]
    contract = {**CONTRACT, "agent_type": "TorpedoAUV", "thruster_count": 1}
    env = make("torpedo-remus-like", contract=contract, overrides={"actuators": actuators})
    assert env.evidence_map.propulsion_grade == "D"
    assert env.evidence_map.propulsion_relation == "user"
    assert any("stale evidence link: propulsion" in w for w in env.warnings)
    env.close()
    untouched = make("torpedo-remus-like", contract=contract)
    assert untouched.evidence_map.propulsion_grade == "C"
    untouched.close()


def test_load_source_values_must_be_finite_and_cumulatively_nonnegative():
    env = make()
    env.attach(Source([{"A": float("nan")}]))
    with pytest.raises(ConfigurationError, match="non-finite"):
        env.step([0] * 8)
    env.close()
    env = make()
    env.attach(Source([{"A": 1.0, "B": 0.0}, {"A": -5.0, "B": 5.0}]))
    env.step([0] * 8)
    with pytest.raises(ConfigurationError, match="cumulative energy"):
        env.step([0] * 8)
    env.close()
    env = make()  # a correction within the state's cumulative energy is accepted
    env.attach(Source([{"A": 1.0, "B": 0.0}, {"A": -0.5, "B": 2.0}]))
    env.step([0] * 8)
    env.step([0] * 8)
    summary = env.energy.summary()
    assert summary["device_state_energy_Wh"]["src.dev"]["A"] == pytest.approx(0.5 / 3600)
    assert all(v >= 0 for v in summary["evidence"]["energy_Wh"].values())
    env.close()


def test_constant_hotel_load_is_part_of_the_evidence_total():
    env = make("bluerov2-heavy-v0.1", contract={**CONTRACT, "dt_s": 0.05})
    for _ in range(20):
        env.step([0] * 8)
    summary = env.energy.summary()
    hotel_Wh = summary["device_state_energy_Wh"].get("hotel_constant", {}).get("ACTIVE", 0.0)
    assert hotel_Wh > 0
    assert summary["evidence"]["total_Wh"] == pytest.approx(
        summary["terminal_energy_Wh"] + summary["category_energy_Wh"]["battery_losses"], rel=1e-9
    )
    env.close()


def test_reverse_null_normalized_command_derates_instead_of_crashing():
    from holoenergy.models.propulsion import PropulsionModel

    table = {
        "voltage_V": 24.0,
        "forward": [
            {"command": 0, "force_N": 0, "power_W": 0},
            {"command": 1, "force_N": 10, "power_W": 50},
        ],
        "reverse": None,
    }
    model = PropulsionModel(
        {
            "thruster_count": 1,
            "action_units": "normalized_command",
            "thruster": {"model": "forward_only_test", "voltage_tables": [table]},
        }
    )
    assert model.max_action_factor([-0.5], 24.0) == 0.0
    assert model.max_action_factor([0.5], 24.0) == 1.0


def test_external_devices_cannot_take_reserved_names():
    env = make()
    env.attach(Source([{"A": 1.0}], device="V1"))
    with pytest.raises(ConfigurationError, match="reserved"):
        env.step([0] * 8)
    env.close()


def test_proxy_and_upper_bound_shares_include_attached_modems():
    profile = ModemPowerProfile.from_mapping(modem_profile("semtech-sx1276-14dbm-upper"))
    assert profile.relation == "proxy" and "TX" in profile.upper_bound_states
    adapter = DesertEnergyAdapter({"em": profile}, node="auv_01", node_map={"auv_01": 1})
    adapter.ensure_interfaces(["em"])
    env = make()
    env.attach(adapter)
    adapter.observe(
        [
            {
                "event": "phy_tx_start",
                "time": 0.0,
                "node": 1,
                "medium": "em",
                "duration_s": 0.05,
                "phy_bits": 100,
            }
        ]
    )
    for _ in range(10):
        env.step([0] * 8)
    evidence = env.energy.summary()["evidence"]
    assert evidence["proxy_energy_Wh"] > 0
    assert evidence["upper_bound_energy_Wh"] > 0
    env.close()
    listen = acoustic()
    assert "LISTEN" in listen.upper_bound_states  # EvoLogics RX/listen is a published maximum


def test_numeric_desert_node_is_tracked_by_name():
    adapter = DesertEnergyAdapter({"acoustic": acoustic()}, node=1, node_map={"auv_01": 1})
    adapter.observe(
        [{"event": "phy_tx_start", "time": 0.0, "node": 1, "duration_s": 0.4, "phy_bits": 100}]
    )
    assert adapter.ledger("acoustic").durations(1.0)["TX"] == pytest.approx(0.4)


def test_ledgers_created_after_attach_keep_their_grade():
    adapter = DesertEnergyAdapter({"acoustic": acoustic()}, node=None, node_map={"auv_01": 1})
    env = make()
    env.attach(adapter)  # no ledger yet: it appears with the first event
    adapter.observe(
        [{"event": "phy_tx_start", "time": 0.0, "node": 1, "duration_s": 0.05, "phy_bits": 100}]
    )
    for _ in range(10):
        env.step([0] * 8)
    devices = env.evidence_map.devices
    assert "comms.auv_01/acoustic" in devices
    assert devices["comms.auv_01/acoustic"]["TX"] != "D"
    assert not math.isnan(env.energy.summary()["evidence"]["total_Wh"])
    env.close()
