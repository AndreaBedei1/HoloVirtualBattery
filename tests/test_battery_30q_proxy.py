"""30Q cell-level OCV proxy for the Blue Robotics 4S 18 Ah pack (review C-02).

The proxy curve is 4 x the Samsung INR18650-30Q cell OCV of Song and Lee 2023 (Table A1),
graded C because the pack's cell identity is implied, not proven. An overridden curve that keeps
the link is stale and graded D.
"""

import copy

from holoenergy import EnergyAwareEnv
from holoenergy.analysis.replay import ReplayBackend
from holoenergy.catalog import vehicle_config
from holoenergy.config import load_config
from holoenergy.evidence import default_registry

SONG_TABLE_A1_CELL = [
    (0.0, 2.8277),
    (0.1, 3.2019),
    (0.2, 3.3513),
    (0.3, 3.5200),
    (0.4, 3.6322),
    (0.5, 3.7336),
    (0.6, 3.8204),
    (0.7, 3.9168),
    (0.8, 4.0157),
    (0.9, 4.0765),
    (1.0, 4.1682),
]


def _env(config):
    base = ReplayBackend(config)
    return EnergyAwareEnv(base, config=config, control_contract=base.energy_action_contract)


def _config(battery):
    return load_config(data=vehicle_config("bluerov2-heavy", battery_profile=battery))


def test_proxy_curve_is_four_times_the_published_cell_table():
    record = default_registry().get("bluerobotics_4s_18ah.ocv_curve_30q_cell_proxy")
    assert record.relation == "proxy" and record.grade == "C"
    points = record.dataset["points"]
    assert [p[0] for p in points] == [s for s, _ in SONG_TABLE_A1_CELL]
    for (_, pack), (_, cell) in zip(points, SONG_TABLE_A1_CELL, strict=True):
        assert abs(pack - 4 * cell) < 1e-9
    config = _config("bluerobotics-4s-18ah-30q-proxy")
    assert [list(map(float, p)) for p in config["battery"]["ocv_curve"]] == [
        [float(a), float(b)] for a, b in points
    ]


def test_ocv_grade_is_c_with_the_proxy_and_d_with_the_placeholder():
    with _env(_config("bluerobotics-4s-18ah-30q-proxy")) as env:
        assert env.evidence_map.ocv_grade == "C"
        assert not [s for s in env.evidence_map.stale_links if "ocv_curve" in s]
    with _env(_config("bluerobotics-4s-18ah")) as env:
        assert env.evidence_map.ocv_grade == "D"


def test_overriding_the_curve_but_keeping_the_link_is_stale_and_graded_d():
    config = copy.deepcopy(_config("bluerobotics-4s-18ah-30q-proxy"))
    config["battery"]["ocv_curve"][5] = [0.5, 15.2]
    with _env(config) as env:
        assert env.evidence_map.ocv_grade == "D"
        assert any("battery.ocv_curve" in s for s in env.evidence_map.stale_links)


def test_vehicle_config_replaces_the_vehicle_battery_with_the_selected_profile():
    # Regression: the vehicle's resolved battery fields used to override the selected profile.
    from holoenergy.catalog import _profiles_root
    from holoenergy.config import _read

    demo = _read(_profiles_root().joinpath("batteries", "demo_24v30ah.yaml"))
    config = _config("demo-24v30ah")
    for key in ("nominal_voltage_V", "capacity_Ah"):
        if key in demo:
            assert config["battery"][key] == demo[key]
    assert config["battery"].get("ocv_curve") == demo.get("ocv_curve")
