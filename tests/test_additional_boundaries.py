"""Additional synthetic boundaries for calibrated domains and conservation."""

import copy

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy.models.propulsion import ThrusterModel
from holoenergy.models.thermal import ThermalModel


def test_inverse_force_interpolation_requires_both_voltage_domains(thruster_config):
    c = copy.deepcopy(thruster_config)
    c["voltage_tables"][1]["forward"] = copy.deepcopy(c["voltage_tables"][1]["forward"])
    c["voltage_tables"][0]["forward"][-1]["force_N"] = 20
    t = ThrusterModel(c)
    assert t.max_force(15, "forward") == 20
    assert t.max_force(20, "forward") == 40
    with pytest.raises(ValueError, match="measured force"):
        t.power(30, 15)


def test_out_of_domain_demand_is_flagged_while_sent_action_is_supported(fake, config):
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([1e6] * 8)["Energy"]
        assert e["requested_power_is_capped"]
        assert e["dynamics_energy_consistent"]
        assert e["applied_action"] == fake.actions[-1]


@pytest.mark.parametrize("temperature", [-5, 60])
def test_temperature_domain_flag_and_operation_limits(fake, config, temperature):
    config["thermal"]["initial_temperature_C"] = temperature
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([0] * 8)["Energy"]
        assert e["temperature_outside_calibration"]
        if temperature == 60:
            assert e["battery_state"] == "CUTOFF" and e["power_total_W"] == 0


def test_near_cutoff_sensor_only_and_zero_hotel(fake, config):
    config["battery"]["ocv_curve"] = [[0, 10.0001], [1, 10.0001]]
    config["hotel_load"]["constant_W"] = 0
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([0] * 8)["Energy"]
        assert 0 <= e["power_total_W"] <= e["available_power_W"] + 1e-8
        assert e["power_propulsion_W"] == 0
        assert e["voltage_V"] >= 10 - 1e-9


def test_thermal_root_stable_for_small_r_and_entropic_heating(thermal_config):
    thermal_config["cooling_coeff_W_per_C"] = 0
    t = ThermalModel(thermal_config)
    current = t.current_limit(1e-20, -0.01, 1)
    assert current == pytest.approx(1000 * 30 / (293.15 * 0.01))


def test_multi_tick_extrema_not_lost_in_interval_means(fake, config):
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([5] * 8, ticks=10)["Energy"]
        assert e["minimum_voltage_V"] <= e["voltage_V"]
        assert e["peak_current_A"] >= e["current_A"]
        assert e["peak_temperature_C"] >= e["temperature_C"]
