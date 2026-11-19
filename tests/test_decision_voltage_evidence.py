"""Bus-voltage evidence in decisions (R5-02 follow-up).

Actuator power is read from tables at the bus voltage, which follows the battery OCV model. A
propulsion difference between two runs with different battery models therefore rests on their
OCV evidence: a placeholder (grade D) curve cannot support a ranking. With the same battery
model the difference is conditional on it, and the comparison says so.
"""

from holoenergy.catalog import vehicle_config
from holoenergy.config import load_config
from holoenergy.decision import compare_energy
from holoenergy.mission import Mission, run_scenario

MISSION = Mission.from_mapping(
    {
        "name": "transit",
        "phases": [
            {
                "name": "transit",
                "duration_s": 20,
                "propulsion": {"thrust_N": [5, 5, 5, 5, 20, 20, 20, 20]},
            }
        ],
    }
)


def _run(tmp_path, name, battery=None, components=None):
    config = load_config(
        data=vehicle_config("bluerov2-heavy", battery_profile=battery, components=components)
    )
    return run_scenario(config, MISSION, tmp_path / name).to_dict()


def test_battery_choice_ranking_is_not_supported_by_a_placeholder_ocv(tmp_path):
    proxy = _run(tmp_path, "proxy", "bluerobotics-4s-18ah-30q-proxy")
    placeholder = _run(tmp_path, "placeholder", "bluerobotics-4s-18ah")
    assert proxy["terminal_energy_Wh"] != placeholder["terminal_energy_Wh"]
    result = compare_energy(proxy, placeholder)
    assert result.verdict == "RANKING_NOT_SUPPORTED"
    assert result.difference_high_Wh is None  # the propulsion difference is open


def test_same_battery_model_keeps_the_payload_comparison_and_states_the_assumption(tmp_path):
    # A robot without unconfigured loads (an unknown load never cancels; adversarial C3).
    import copy

    from holoenergy.dashboard.api import TEMPLATES

    robot = TEMPLATES["four-thruster-rov"]["robot"]
    without_dvl = copy.deepcopy(robot)
    without_dvl["components"] = [c for c in robot["components"] if c["name"] != "dvl"]
    mission = Mission.from_mapping(
        {
            "name": "t",
            "phases": [{"name": "t", "duration_s": 20, "propulsion": {"thrust_N": [10, 10, 5, 5]}}],
        }
    )
    base = run_scenario(load_config(data=without_dvl), mission, tmp_path / "base").to_dict()
    heavier = run_scenario(load_config(data=robot), mission, tmp_path / "dvl").to_dict()
    result = compare_energy(base, heavier)
    # Same battery model: propulsion differences stay point values (a finite upper side) and the
    # dependence on the common OCV model is stated.
    assert result.difference_high_Wh is not None
    assert any("same battery voltage model" in a for a in result.assumptions)
    # The DVL record has no published lower bound and the extra load lowers actuator power
    # through the bus voltage, so even this ranking is not supported (an honest negative).
    assert result.verdict == "RANKING_NOT_SUPPORTED"
    # Strict evidence (grade B or better): the propulsion difference rests on a grade-C OCV and
    # is opened, so the upper side is unknown.
    strict = compare_energy(base, heavier, min_grade="B")
    assert strict.difference_high_Wh is None
