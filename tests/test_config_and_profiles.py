import hashlib
import json
from importlib.resources import files
from pathlib import Path

import pytest

from holoenergy._validation import ConfigurationError
from holoenergy.config import load_config
from holoenergy.models.propulsion import PropulsionModel, ThrusterModel

ROOT = Path(__file__).resolve().parents[1]


def test_pack_and_sensor_ratings_and_bundled_thruster_data():
    with pytest.warns(UserWarning, match="Uncalibrated"):
        c = load_config(ROOT / "configs/bluerov2_energy.yaml")
    assert c["battery"]["capacity_Ah"] == 18
    assert c["battery"]["max_current_A"] == 60
    assert c["battery"]["cutoff_voltage_V"] == 12
    assert c["sensors"]["Camera"]["states"]["active_W"] == 1.1
    assert c["sensors"]["ImagingSonar"]["states"]["active_W"] == 5
    p = PropulsionModel(c["propulsion"])
    assert sum(p.powers([10] * 8, 14)) > sum(p.powers([5] * 8, 14))
    forward, reverse = p.powers([15] * 8, 16), p.powers([-15] * 8, 16)
    assert forward != reverse


def test_thruster_source_hash_and_discrepancy_are_preserved():
    path = files("holoenergy").joinpath("profiles/thrusters/bluerobotics_t200.json")
    data = json.loads(path.read_text(encoding="utf-8"))
    source = ROOT / "sources/T200-Public-Performance-Data-10-20V-September-2019.xlsx"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == data["metadata"]["sha256"]
    anomalies = data["metadata"]["source_discrepancies"]
    assert len(anomalies) == 1
    assert anomalies[0]["published_power_W"] == 1.4
    assert anomalies[0]["current_times_voltage_W"] == pytest.approx(0.14)


def test_voltage_interpolation_and_normalized_vs_force(thruster_config):
    p = ThrusterModel(thruster_config)
    assert p.power(10, 15) == pytest.approx(25)
    assert p.power(0.5, 15, "normalized_command") == pytest.approx(25)
    assert p.force(0.5, 15) == pytest.approx(10)
    with pytest.raises(ValueError, match="outside measured"):
        p.power(5, 9)


def test_explicit_placeholder_opt_in(config):
    config["battery"]["metadata"] = {"placeholders": ["internal_resistance_ohm"]}
    with pytest.raises(ConfigurationError, match="allow_placeholders"):
        load_config(data=config)
    config["allow_placeholders"] = True
    with pytest.warns(UserWarning, match="internal_resistance"):
        load_config(data=config)


def test_json_and_relative_profile_overrides(config, tmp_path):
    battery = tmp_path / "battery.json"
    battery.write_text(json.dumps(config["battery"]))
    config["battery"] = {"profile": "battery.json", "initial_soc": 0.5}
    p = tmp_path / "config.json"
    p.write_text(json.dumps(config))
    c = load_config(p)
    assert c["battery"]["initial_soc"] == 0.5
    assert c["battery"]["capacity_Ah"] == 10
    assert config["battery"]["profile"] == "battery.json"


def test_cyclic_profile_rejected(tmp_path):
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("profile: b.yaml\n")
    b.write_text("profile: a.yaml\n")
    with pytest.raises(ConfigurationError, match="Cyclic"):
        load_config(a)


def test_unknown_field_rejected(config):
    config["batttery"] = {}
    with pytest.raises(ConfigurationError, match="Unknown"):
        load_config(data=config)


@pytest.mark.parametrize(
    "field,value",
    [
        ("capacity_Ah", 0),
        ("initial_soc", 2),
        ("internal_resistance_ohm", -1),
        ("max_current_A", float("nan")),
        ("ocv_curve", [[0, 16], [1, 12]]),
    ],
)
def test_invalid_physical_parameters_rejected(battery_config, field, value):
    from holoenergy.models.battery import RintBattery

    battery_config[field] = value
    with pytest.raises(ConfigurationError):
        RintBattery(battery_config)
