import json
import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.catalog import list_profiles, modem_profile, vehicle_config
from holoenergy.config import load_config
from holoenergy.report import EnergyReport, compare_runs

CONTRACT = {
    "action_units": "force_N",
    "thruster_count": 8,
    "dt_s": 0.01,
    "agent_type": "BlueROV2",
    "control_scheme": 0,
}


class Backend:
    def __init__(self):
        self.sent = []

    def step(self, action):
        self.sent.append([float(v) for v in action])
        return {}

    def reset(self):
        return {}

    def close(self):
        pass


def make(profile, **kwargs):
    warnings.simplefilter("ignore", UserWarning)
    backend = Backend()
    env = EnergyAwareEnv(
        backend,
        vehicle_profile=profile,
        control_contract=CONTRACT,
        overrides={"logging": {"enabled": False}, **kwargs.pop("overrides", {})},
        **kwargs,
    )
    return env, backend


def test_catalog_lists_exact_and_proxy_profiles():
    profiles = list_profiles()
    assert profiles["vehicles"]["bluerov2-heavy"]["relation"] == "representative"
    assert profiles["vehicles"]["bluerov2-standard"]["relation"] == "proxy"
    assert "waterlinked-dvl-a50" in profiles["components"]
    assert "evologics-s2cm-18-34-1000m" in profiles["modems"]
    with pytest.raises(ConfigurationError, match="Unknown vehicle"):
        vehicle_config("bluerov2-imaginary")


def test_heavy_and_standard_profiles_resolve_to_8_and_6_actuators():
    heavy = load_config(data=vehicle_config("bluerov2-heavy"))
    standard = load_config(data=vehicle_config("bluerov2-standard"))
    assert heavy["propulsion"]["thruster_count"] == 8
    assert standard["propulsion"]["thruster_count"] == 6
    assert standard["actuation"]["backend"]["mapping"] == "wrench_equivalent"
    assert [g["id"] for g in standard["actuation"]["geometry"]] == [
        "H1",
        "H2",
        "H3",
        "H4",
        "V1",
        "V2",
    ]


def test_standard_wrench_is_reproduced_on_native_agent():
    env, backend = make("bluerov2-standard")
    state = env.step([30, 5, 20, 0.5, 0, 1])
    act = state["Energy"]["actuation"]
    assert act["backend_residual_norm"] < 1e-9
    assert len(backend.sent[-1]) == 8
    assert all(abs(f) <= 28.75 + 1e-9 for f in backend.sent[-1])
    assert state["Energy"]["dynamics_energy_consistent"]
    env.close()


def test_pitch_moment_is_infeasible_for_standard_and_reported():
    env, _ = make("bluerov2-standard")
    state = env.step([0, 0, 0, 0, 3.0, 0])
    act = state["Energy"]["actuation"]
    # Two centreline vertical thrusters at x=0 cannot create pitch.
    assert act["allocation_residual_norm"] == pytest.approx(3.0, rel=1e-6)
    env.close()


def test_heavy_direct_mode_and_energy_api():
    env, backend = make("bluerov2-heavy")
    assert env.energy.power_w is None
    for _ in range(100):
        env.step([0, 0, 0, 0, 10, 10, 10, 10])
    assert backend.sent[-1] == [0, 0, 0, 0, 10, 10, 10, 10]
    assert env.energy.power_w > 0
    assert env.energy.energy_wh == pytest.approx(
        sum(v for k, v in env.energy.categories.items() if k != "battery_losses")
    )
    assert 0 < env.battery.soc < 1
    summary = env.energy.summary()
    ev = summary["evidence"]
    assert sum(ev["share_percent"].values()) == pytest.approx(100)
    assert ev["energy_Wh"]["A"] > 0
    assert {u["component"] for u in ev["unconfigured_components"]} == {
        "tether_interface",
        "esc_standby",
    }
    env.close()


def test_report_text_json_roundtrip_and_compare(tmp_path):
    reports = []
    for force in (5, 10):
        env, _ = make("bluerov2-heavy")
        for _ in range(200):
            env.step([0, 0, 0, 0, force, force, force, force])
        report = env.energy.report()
        path = report.write_json(tmp_path / f"r{force}.json")
        assert json.loads(path.read_text())["terminal_energy_Wh"] == pytest.approx(
            report.terminal_energy_Wh
        )
        assert "INCOMPLETE" in report.text()
        reports.append(path)
        env.close()
    result = compare_runs(*reports, labels=["5N", "10N"])
    second = result["runs"][1]
    assert second["terminal_energy_Wh"]["ratio"] > 1
    assert any("unconfigured" in c for c in result["caveats"])
    assert EnergyReport.load(reports[0]).duration_s == pytest.approx(2.0)


def test_interval_open_for_upper_bound_states():
    env, _ = make("bluerov2-heavy")
    for _ in range(100):
        env.step([0] * 8)
    report = env.energy.report()
    t = report.intervals["terminal_energy_Wh"]
    assert "camera.ACTIVE" in t["open_low"]
    assert t["high"] >= t["nominal"]
    env.close()


def test_double_counting_warning_for_overlapping_imu():
    env, _ = make("bluerov2-heavy", components=["vectornav-vn100-rugged"])
    assert any("double counting" in w and "imu" in w for w in env.warnings)
    env.close()


def test_unconfigured_component_cannot_be_used_silently():
    with pytest.raises(ConfigurationError, match="no value"):
        make(
            "bluerov2-heavy",
            components=[
                {
                    "name": "sss",
                    "category": "sensors",
                    "states": {"ACTIVE": {"evidence": "edgetech_2205.power"}},
                }
            ],
        )


def test_modem_profiles_load_with_grades():
    from holoenergy.integrations import ModemPowerProfile

    profile = ModemPowerProfile.from_mapping(modem_profile("evologics-s2cm-18-34-1000m"))
    assert profile.power("TX") == pytest.approx(2.8)
    assert profile.power("LISTEN") == pytest.approx(0.8)
    assert profile.grades["TX"] == "B"  # representative use caps the A datasheet grade
