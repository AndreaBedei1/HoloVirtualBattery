"""Mission (scenario) model and the scientific pre-flight check."""

import pytest

from holoenergy._validation import ConfigurationError
from holoenergy.catalog import vehicle_config
from holoenergy.config import load_config
from holoenergy.mission import Mission, run_scenario
from holoenergy.preflight import preflight


def _bluerov(*components, rails=None):
    data = vehicle_config("bluerov2-heavy", components=list(components) or None)
    if rails is not None:
        data["rails"] = rails
    return load_config(data=data)


MISSION = {
    "name": "inspection",
    "phases": [
        {
            "name": "transit",
            "duration_s": 6,
            "propulsion": {"thrust_N": [0, 0, 0, 0, 10, 10, 10, 10]},
            "water_temperature_C": 12,
        },
        {
            "name": "inspect",
            "duration_s": 4,
            "component_states": {"camera": "OFF"},
            "current_m_s": [0.2, 0, 0],
            "water_density_kg_m3": 1025,
        },
    ],
}


def test_mission_round_trips_and_compiles_to_whole_steps(tmp_path):
    mission = Mission.from_mapping(MISSION)
    path = mission.to_yaml(tmp_path / "m.yaml")
    assert Mission.load(path) == mission
    config = _bluerov()
    commands = mission.commands(config)
    dt = config["simulation"]["dt_s"]
    assert len(commands) == round(10 / dt)
    assert commands[0]["water_temperature_C"] == 12
    assert commands[round(6 / dt)]["sensor_states"] == {"camera": "OFF"}


def test_energy_only_run_reports_each_phase_for_its_duration(tmp_path):
    report = run_scenario(_bluerov(), Mission.from_mapping(MISSION), tmp_path)
    assert report.phases["transit"]["duration_s"] == pytest.approx(6.0)
    assert report.phases["inspect"]["duration_s"] == pytest.approx(4.0)
    # Propulsion only in transit; switching the camera OFF lowers sensor power afterwards.
    assert report.category_energy_Wh["propulsion"] > 0


def test_schedule_errors_are_stated_in_robot_terms():
    config = _bluerov()
    bad = {
        **MISSION,
        "phases": [{"name": "x", "duration_s": 1, "propulsion": {"thrust_N": [1, 2]}}],
    }
    with pytest.raises(ConfigurationError, match="has 2 values; the robot has 8 actuators"):
        Mission.from_mapping(bad).commands(config)
    bad = {
        **MISSION,
        "phases": [
            {
                "name": "x",
                "duration_s": 1,
                "component_states": {"sonar_that_is_not_there": "ACTIVE"},
            }
        ],
    }
    with pytest.raises(ConfigurationError, match="does not have"):
        Mission.from_mapping(bad).commands(config)


def test_environment_effects_never_claim_an_unapplied_quantity():
    mission = Mission.from_mapping(MISSION)
    energy_only = {r["quantity"]: r["status"] for r in mission.environment_effects("energy-only")}
    assert energy_only["current_m_s"].startswith("descriptive only")
    assert energy_only["water_density_kg_m3"].startswith("descriptive only")
    assert energy_only["water_temperature_C"].startswith("applied by HoloEnergy")
    holo = {r["quantity"]: r["status"] for r in mission.environment_effects("holoocean")}
    assert "HoloOcean" in holo["current_m_s"]
    assert holo["water_density_kg_m3"].startswith("descriptive only")


def test_preflight_flags_a_device_outside_the_pack_voltage_and_suggests_a_fix():
    result = preflight(_bluerov("tritech-gemini-720is"))
    assert result["ok"]
    supply = [i for i in result["issues"] if i["kind"] == "supply_voltage"]
    assert supply and "requires 19-74 V" in supply[0]["message"]
    assert "12-16.8 V" in supply[0]["message"] and "converter rail" in supply[0]["message"]
    kinds = {i["kind"] for i in result["issues"]}
    assert {"battery", "upper_bound", "unknown", "dynamics"} <= kinds


def test_preflight_moves_the_issue_to_the_converter_when_a_rail_supplies_the_device():
    config = _bluerov(rails=[{"name": "24V", "output_V": 24}])
    for item in config["components"]:
        if item.get("name") == "imaging_sonar":
            item["rail"] = "24V"
    config["components"].append(
        {
            "profile": "package:components/tritech_gemini_720is.yaml",
            "name": "imaging_sonar",
            "rail": "24V",
        }
    )
    result = preflight(config)
    assert result["ok"], result["errors"]
    assert not [i for i in result["issues"] if i["kind"] == "supply_voltage"]
    assert any(i["kind"] == "converter" and i["subject"] == "24V rail" for i in result["issues"])


def test_preflight_errors_are_plain_language_with_the_technical_text_kept():
    config = _bluerov()
    config["components"].append({"name": "x", "active_W": 1.0, "rail": "48V"})
    result = preflight(config)
    assert not result["ok"]
    error = result["errors"][0]
    assert error["summary"].startswith("A component is assigned to a supply rail")
    assert "48V" in error["technical"] and error["fix"]
