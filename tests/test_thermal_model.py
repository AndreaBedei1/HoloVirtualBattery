from math import exp

import pytest

from holoenergy.models.thermal import ThermalModel


def test_exact_cooling_toward_water(thermal_config):
    t = ThermalModel(thermal_config)
    assert t.step(0, 10) == pytest.approx(15 + 5 * exp(-0.02))
    for _ in range(100):
        t.step(0, 60)
    assert t.temperature_C == pytest.approx(15, abs=1e-4)


def test_current_heating(thermal_config):
    t = ThermalModel(thermal_config)
    assert t.step(50**2 * 0.04, 10) > 20


def test_adiabatic_and_thermal_derating(thermal_config):
    thermal_config["cooling_coeff_W_per_C"] = 0
    t = ThermalModel(thermal_config)
    assert t.step(250, 100) == pytest.approx(45)
    assert t.derating_factor == pytest.approx(0.5)
    t.step(250, 20)
    assert t.critical and t.derating_factor == 0


@pytest.mark.parametrize("entropy", [0, 0.001, -0.001])
def test_predictive_heat_limit_avoids_large_step_overshoot(thermal_config, entropy):
    t = ThermalModel(thermal_config)
    t.temperature_C = 49
    current = t.current_limit(0.1, entropy, 100)
    heat = current**2 * 0.1 - current * 322.15 * entropy
    assert t.step(heat, 100) == pytest.approx(50)


def test_minimum_operating_temperature(thermal_config):
    thermal_config["minimum_temperature_C"] = 0
    thermal_config["initial_temperature_C"] = -1
    assert ThermalModel(thermal_config).critical
