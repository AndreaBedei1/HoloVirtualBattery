import pytest

from holoenergy._validation import ConfigurationError
from holoenergy.models.payload import PayloadComponent


def component(**kwargs):
    c = {
        "initial_state": "ACTIVE",
        "states": {
            "off_W": 0,
            "idle_W": 2,
            "active_W": 5,
            "startup_W": 20,
            "startup_duration_s": 1,
            "ping_W": 30,
            "ping_duration_s": 0.1,
        },
    }
    c.update(kwargs)
    return PayloadComponent("Sonar", c)


def test_off_idle_active_order():
    p = component()
    active = p.step(1)
    p.set_state("IDLE")
    idle = p.step(1)
    p.set_state("OFF")
    assert p.step(1) < idle < active


def test_startup_exact_across_interval():
    p = component(initial_state="STARTING")
    assert p.step(2) == pytest.approx(12.5)
    assert p.state.value == "ACTIVE"
    assert p.step(1) == 5


def test_manual_ping_finishes_in_active():
    p = component(initial_state="PINGING")
    assert p.step(0.2) == pytest.approx(17.5)
    assert p.state.value == "ACTIVE"


def test_periodic_ping_partition_invariance():
    p, q = (
        component(initial_state="PINGING", frequency_Hz=2),
        component(initial_state="PINGING", frequency_Hz=2),
    )
    whole = p.step(100) * 100
    pieces = sum(q.step(0.07) * 0.07 for _ in range(1000)) + q.step(30) * 30
    assert pieces == pytest.approx(whole)
    assert whole / 100 == pytest.approx(10)


def test_undocumented_state_power_raises():
    p = PayloadComponent("Unknown", {"initial_state": "OFF", "states": {"active_W": None}})
    with pytest.raises(ConfigurationError, match="supply a measured"):
        p.set_state("ACTIVE")


def test_overlapping_pings_rejected():
    with pytest.raises(ConfigurationError, match="must be <= 1"):
        component(frequency_Hz=20)
