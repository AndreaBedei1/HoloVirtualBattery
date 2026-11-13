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


def test_env_low_soc_operates_voltage_limited_instead_of_latching():
    """Review C-01/E-05: at SOC 0.03 the env must deliver reduced thrust, not latch off."""
    env = make(overrides={"battery": {"initial_soc": 0.03}})
    rows = [env.step([0, 0, 0, 0, 28.0, 28.0, 28.0, 28.0])["Energy"] for _ in range(200)]
    assert all(r["battery_state"] != "CUTOFF" for r in rows)
    assert min(r["voltage_V"] for r in rows) >= 12.0 - 1e-6
    assert sum(r["power_propulsion_W"] for r in rows[100:]) > 0
    env.close()


def test_virtual_layout_is_charged_only_for_thrust_the_native_body_applies():
    """Review E-06: a surge request beyond the native clamp capacity is re-allocated."""
    env = make("bluerov2-standard")
    row = env.step([150.0, 0, 0, 0, 0, 0])["Energy"]
    act = row["actuation"]
    assert act["native_limited"] is True
    assert act["backend_residual_norm"] < 1e-6
    env.close()


def test_multi_tick_step_with_device_appearing_mid_step():
    """Review E-08: a ledger created during a multi-tick step must not raise KeyError."""
    adapter = DesertEnergyAdapter({"acoustic": acoustic()}, node=None, node_map={"auv_01": 1})
    env = make()
    env.attach(adapter)

    class Late:
        def __init__(self):
            self.calls = 0

        def step(self, action):
            self.calls += 1
            if self.calls == 2:
                adapter.observe(
                    [
                        {
                            "event": "phy_tx_start",
                            "time": 0.0,
                            "node": 1,
                            "duration_s": 0.02,
                            "phy_bits": 8,
                        }
                    ]
                )
            return {}

        def close(self):
            pass

    env.env = Late()
    row = env.step([0] * 8, ticks=5)["Energy"]
    assert "comms.auv_01/acoustic" in row["component_power_W"]
    env.close()


def test_intervals_lower_bound_open_and_converter_scaling():
    """Review E-01/E-03: lower-bound records leave the upper side open; widths scale by 1/eta."""
    from holoenergy.uncertainty import _ratio_interval

    record = load_registry_record("bluerobotics_4s_18ah.dc_resistance_cell_derived")
    lo, hi = _ratio_interval(record, record.si("value"))
    assert hi is None and lo is not None and lo < 1

    def width(eta):
        env = make(
            components=["tritech-gemini-720is"],
            overrides={"converters": {"payload_efficiency": eta}},
        )
        for _ in range(50):
            env.step([0] * 8)
        t = env.energy.report().intervals["terminal_energy_Wh"]
        env.close()
        return t["nominal"] - t["low"]

    assert width(0.8) == pytest.approx(width(1.0) / 0.8, rel=1e-6)


def load_registry_record(record_id):
    from holoenergy.evidence import default_registry

    return default_registry().get(record_id)


def test_legacy_sensor_schema_obeys_the_sensor_policy():
    """Review D-07: the legacy `sensors:` schema cannot put power on ground truth."""
    from holoenergy.models.components import ComponentModel

    with pytest.raises(ConfigurationError, match="0 W"):
        ComponentModel({"VelocitySensor": {"states": {"active_W": 4}}})
    with pytest.raises(ConfigurationError, match="derived semantic"):
        ComponentModel(
            {"seg": {"simulation_sensor": "SemanticSegmentationCamera", "states": {"active_W": 12}}}
        )
    ComponentModel({"cam": {"simulation_sensor": "RGBCamera", "states": {"active_W": 1}}})


def test_lumen_peak_power_is_an_upper_bound():
    """Review D-05: the Lumen 15 W is a published peak, reported as an upper bound."""
    record = load_registry_record("bluerobotics_lumen.power_full")
    assert record.bound == "upper_bound"


def test_power_irls_allocation_runs_in_the_env():
    """Review E-09: allocation.method power_irls must step, using the T200 tables."""
    rows = {}
    for method in ("redistributed", "power_irls"):
        env = make(
            overrides={"actuation": {"action_mode": "wrench", "allocation": {"method": method}}}
        )
        rows[method] = env.step([30.0, 10.0, 15.0, 0.0, 0.0, 2.0])["Energy"]
        env.close()
    irls = rows["power_irls"]
    assert irls["actuation"]["allocation_residual_norm"] < 1e-6
    assert math.isfinite(irls["power_propulsion_W"]) and irls["power_propulsion_W"] > 0
    assert irls["power_propulsion_W"] <= rows["redistributed"]["power_propulsion_W"] * 1.001


def test_scientific_warnings_are_structured_and_non_blocking():
    """Brief section 51: unknown / grade D / proxy / upper-bound-only evidence is reported as
    structured data with the energy it carries; the run is not blocked."""
    env = make()
    for _ in range(50):
        env.step([0, 0, 0, 0, 10.0, 10.0, 10.0, 10.0])
    evidence = env.energy.summary()["evidence"]
    items = evidence["scientific_warnings"]
    assert items, "the default profile carries flagged evidence"
    kinds = {"unknown", "grade_D", "proxy", "upper_bound_only"}
    for w in items:
        assert w["kind"] in kinds
        assert set(w) >= {"kind", "subject", "states", "energy_Wh", "share_percent", "effect"}
    flagged_ub = sum(w["energy_Wh"] for w in items if w["kind"] == "upper_bound_only")
    assert flagged_ub == pytest.approx(evidence["upper_bound_energy_Wh"])
    env.close()
