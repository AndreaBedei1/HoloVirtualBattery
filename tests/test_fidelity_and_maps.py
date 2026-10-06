"""Synthetic mathematical fixtures; no measured BlueROV2 data."""

import copy

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.config import load_config, with_fidelity
from holoenergy.models.battery import RintBattery


def test_l0_is_explicit_constant_voltage_temperature_baseline(config, fake):
    c = with_fidelity(config, "L0", capacity_Wh=100)
    c["thermal"]["initial_temperature_C"] = 60
    with pytest.warns(UserWarning), EnergyAwareEnv(fake, config=c) as env:
        e = env.step([5] * 8)["Energy"]
    assert e["fidelity_level"] == "L0"
    assert e["voltage_V"] == 16 and e["temperature_C"] == 60
    assert e["power_battery_loss_W"] == 0
    assert e["soc"] == pytest.approx(1 - e["energy_used_Wh"] / 100)
    assert config["battery"]["model"] == "rint"


def test_level_mismatch_and_l2_rejected(config):
    for level in ("L0", "L2"):
        config["fidelity_level"] = level
        with pytest.raises(ConfigurationError, match="fidelity"):
            load_config(data=config)


def test_resistance_map_bilinear_and_fallback(battery_config):
    original = RintBattery(battery_config)
    assert original.resistance(7) == 0.1
    c = copy.deepcopy(battery_config)
    del c["internal_resistance_ohm"]
    c["resistance_soc_temperature_curves"] = [
        {"temperature_C": 0, "curve": [[0, 0.4], [0.5, 0.3], [1, 0.2]]},
        {"temperature_C": 20, "curve": [[0, 0.2], [0.5, 0.1], [1, 0.0]]},
    ]
    b = RintBattery(c)
    b.soc = 0.25
    assert b.resistance(10) == pytest.approx(0.25)
    assert b.resistance(-5) == pytest.approx(0.35)
    assert b.resistance(25) == pytest.approx(0.15)
    assert b.temperature_outside_calibration(-5)
    assert not b.temperature_outside_calibration(10)
    b.soc = 1
    assert b.resistance(20) == 0


@pytest.mark.parametrize(
    "tables",
    [
        [{"temperature_C": 0, "curve": [[0.1, 0.1], [1, 0.2]]}],
        [{"temperature_C": 0, "curve": [[0, -1], [1, 0.2]]}],
        [
            {"temperature_C": 0, "curve": [[0, 0.1], [1, 0.2]]},
            {"temperature_C": 0, "curve": [[0, 0.1], [1, 0.2]]},
        ],
        [
            {"temperature_C": 0, "curve": [[0, 0.1], [1, 0.2]]},
            {"temperature_C": 20, "curve": [[0, 0.1], [0.5, 0.1], [1, 0.2]]},
        ],
    ],
)
def test_invalid_resistance_maps_rejected(battery_config, tables):
    battery_config["resistance_soc_temperature_curves"] = tables
    with pytest.raises(ConfigurationError):
        RintBattery(battery_config)


def test_infeasible_rint_root_rejected(battery_config):
    with pytest.raises(ValueError, match="no real"):
        RintBattery(battery_config).current_for_power(1e9, 25)


@pytest.mark.parametrize("soc", [0, 1])
@pytest.mark.parametrize("load", [0, 1e9])
def test_soc_extremes_bounded_and_energy_balanced(battery_config, soc, load):
    battery_config["initial_soc"] = soc
    b = RintBattery(battery_config)
    p = b.step(load, 0.1)
    assert 0 <= b.soc <= 1
    assert p.power_W == pytest.approx(p.current_A * p.voltage_V)
    assert b.chemical_energy_Wh == pytest.approx(b.energy_used_Wh + b.internal_loss_Wh)
