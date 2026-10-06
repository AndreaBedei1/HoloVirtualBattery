import pytest

from holoenergy.models.battery import EnergyBucketBattery, RintBattery


def test_ideal_constant_power_soc_and_energy():
    b = EnergyBucketBattery(
        {
            "model": "energy_bucket",
            "capacity_Wh": 100,
            "nominal_voltage_V": 10,
            "initial_soc": 1,
            "max_current_A": 20,
        }
    )
    for _ in range(100):
        point = b.step(36, 1)
        assert point.heat_W == 0
    assert b.energy_used_Wh == pytest.approx(1)
    assert b.soc == pytest.approx(0.99)


def test_coulomb_counting_and_energy_balance(battery_config):
    b = RintBattery(battery_config)
    point = b.step(100, 60)
    assert b.soc == pytest.approx(1 - point.current_A * 60 / 36000)
    assert point.power_W == pytest.approx(point.current_A * point.voltage_V)
    assert b.energy_used_Wh == pytest.approx(100 / 60)
    assert b.chemical_energy_Wh == pytest.approx(b.energy_used_Wh + b.internal_loss_Wh)


def test_voltage_sag_grows_with_load(battery_config):
    a, b = RintBattery(battery_config), RintBattery(battery_config)
    low, high = a.step(30, 1), b.step(150, 1)
    assert high.current_A > low.current_A
    assert high.voltage_V < low.voltage_V


@pytest.mark.parametrize("r", [0.0, 1e-12, 0.1])
def test_zero_and_small_resistance_root(battery_config, r):
    battery_config["internal_resistance_ohm"] = r
    b = RintBattery(battery_config)
    p = b.step(50, 0.1)
    assert p.power_W == pytest.approx(p.current_A * p.voltage_V, rel=1e-9)


def test_current_and_voltage_power_limits(battery_config):
    b = RintBattery(battery_config)
    p = b.step(1e6, 1)
    assert p.current_A == pytest.approx(20)
    assert p.voltage_V >= 10
    assert p.power_W < p.requested_power_W
    battery_config["internal_resistance_ohm"] = 1
    b = RintBattery(battery_config)
    p = b.step(1e6, 0.1)
    assert p.current_A == pytest.approx(6)
    assert p.voltage_V == pytest.approx(10)


def test_explicit_power_limit(battery_config):
    battery_config["max_power_W"] = 50
    b = RintBattery(battery_config)
    assert b.step(100, 1).power_W == pytest.approx(50)


def test_voltage_cutoff_is_latched(battery_config):
    battery_config["cutoff_voltage_V"] = 17
    b = RintBattery(battery_config)
    assert b.step(20, 1).power_W == 0
    assert b.cutoff and b.cutoff_reason == "voltage"
    assert b.step(20, 1).power_W == 0


def test_depletion_cannot_overdraw_last_charge(battery_config):
    battery_config["initial_soc"] = 1e-4
    battery_config["ocv_curve"] = [[0, 14], [1, 16]]
    b = RintBattery(battery_config)
    p = b.step(200, 3600)
    assert b.soc == pytest.approx(0, abs=1e-12)
    assert p.current_A == pytest.approx(0.001)
    assert b.cutoff


def test_temperature_tables_affect_sag_capacity_and_current(battery_config):
    battery_config.update(
        {
            "capacity_temperature_curve": [[0, 0.7], [25, 1]],
            "resistance_temperature_curve": [[0, 3], [25, 1]],
            "max_current_temperature_curve": [[0, 0.5], [25, 1]],
            "ocv_temperature_curves": [
                {"temperature_C": 0, "curve": [[0, 10], [1, 15.8]]},
                {"temperature_C": 25, "curve": [[0, 10], [1, 16]]},
            ],
        }
    )
    cold, warm = RintBattery(battery_config), RintBattery(battery_config)
    assert cold.available_charge_Ah(0) == pytest.approx(7)
    assert cold.current_limit(0, 1) <= 10
    assert cold.step(100, 1, 0).voltage_V < warm.step(100, 1, 25).voltage_V


def test_temperature_change_does_not_create_charge(battery_config):
    battery_config["capacity_temperature_curve"] = [[0, 0.7], [25, 1]]
    b = RintBattery(battery_config)
    b.step(100, 60, 25)
    soc = b.soc
    q_warm, q_cold = b.available_charge_Ah(25), b.available_charge_Ah(0)
    assert q_cold < q_warm and b.soc == soc
    assert b.available_charge_Ah(25) == q_warm


def test_entropic_heat_sign(battery_config):
    battery_config["entropy_curve_V_per_K"] = [[0, 0.001], [1, 0.001]]
    b = RintBattery(battery_config)
    p = b.step(10, 1)
    assert p.heat_W == pytest.approx(p.resistive_loss_W - p.current_A * 298.15 * 0.001)
