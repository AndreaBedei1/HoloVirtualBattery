"""Communication energy from holo_desert-schema events (synthetic events, real field names)."""

import json
import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.integrations import CommunicationEnergyAdapter, ModemPowerProfile
from holoenergy.integrations.desert import DesertEnergyAdapter

PROFILE = ModemPowerProfile("test", {"TX": 10.0, "RX": 1.0, "LISTEN": 0.5}, grades={"TX": "B"})


def tx(t, d, node="auv0", **kw):
    return {
        "event": "phy_tx_start",
        "time": t,
        "node_id": node,
        "duration_s": d,
        "phy_bits": 800,
        **kw,
    }


def rx(t, d, node="auv0", outcome="synchronized", **kw):
    return {
        "event": "phy_rx_start",
        "time": t,
        "node_id": node,
        "duration_s": d,
        "outcome": outcome,
        **kw,
    }


def test_energy_is_integral_of_state_power():
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    adapter.observe([tx(1.0, 0.5), rx(3.0, 1.0), rx(3.5, 1.0)])  # overlapping RX merged
    energy = adapter.energy_J(10.0)["comms.acoustic"]
    assert energy["TX"] == pytest.approx(0.5 * 10)
    assert energy["RX"] == pytest.approx(1.5 * 1.0)
    assert energy["LISTEN"] == pytest.approx((10 - 0.5 - 1.5) * 0.5)


def test_tx_has_priority_over_rx_and_unlocked_receptions_are_listen():
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    adapter.observe(
        [rx(0.0, 2.0), tx(1.0, 0.5), rx(5.0, 1.0, outcome="below_acquisition_threshold")]
    )
    d = adapter.ledger("acoustic").durations(10.0)
    assert d["TX"] == pytest.approx(0.5)
    assert d["RX"] == pytest.approx(1.5)
    assert d["LISTEN"] == pytest.approx(8.0)


def test_other_nodes_media_and_control_frames():
    optical = ModemPowerProfile("opt", {"TX": 25.0, "RX": 10.0, "LISTEN": 10.0}, medium="optical")
    adapter = DesertEnergyAdapter({"acoustic": PROFILE, "optical": optical}, node="auv0")
    adapter.observe(
        [
            tx(0.0, 1.0, node="buoy"),
            tx(0.0, 0.1, medium="optical"),
            {**tx(2.0, 0.2), "event": "phy_control_tx_start"},
        ]
    )
    adapter.ensure_interfaces(["acoustic", "optical"])
    e = adapter.energy_J(1.0)
    assert e["comms.optical"]["TX"] == pytest.approx(2.5)
    assert adapter.ledger("acoustic").durations(3.0)["TX"] == pytest.approx(0.2)
    excluded = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0", include_control=False)
    excluded.observe([{**tx(2.0, 0.2), "event": "phy_control_tx_start"}])
    assert "acoustic" not in excluded.ledgers


def test_all_nodes_silent_interfaces_accrue_idle_energy():
    """A hybrid node's unused optical modem still listens; it must not be silently free."""
    optical = ModemPowerProfile("opt", {"TX": 25.0, "RX": 10.0, "LISTEN": 1.0}, medium="optical")
    adapter = DesertEnergyAdapter(
        {"acoustic": PROFILE, "optical": optical}, node=None, node_map={"auv0": 1, "buoy": 2}
    )
    adapter.ensure_interfaces(["acoustic", "optical"])
    adapter.observe([tx(0.0, 1.0, node="auv0")])
    e = adapter.energy_J(4.0)
    assert set(e) == {f"comms.{n}/{m}" for n in ("auv0", "buoy") for m in ("acoustic", "optical")}
    assert e["comms.buoy/optical"]["LISTEN"] == pytest.approx(4.0)
    assert e["comms.auv0/acoustic"]["TX"] == pytest.approx(10.0)
    with pytest.raises(ConfigurationError):
        DesertEnergyAdapter({"acoustic": PROFILE}, node=None).ensure_interfaces(["acoustic"])


def test_consume_charges_late_events_exactly():
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    adapter.ensure_interfaces(["acoustic"])
    first = adapter.consume(1.0)["comms.acoustic"]
    adapter.observe([tx(0.5, 0.2)])  # arrives after its window was consumed
    second = adapter.consume(2.0)["comms.acoustic"]
    total = {s: first.get(s, 0) + second.get(s, 0) for s in set(first) | set(second)}
    assert total["TX"] == pytest.approx(2.0)
    assert sum(total.values()) == pytest.approx(0.2 * 10 + 1.8 * 0.5)


def test_late_tx_reclassifying_listen_is_charged_on_the_bus():
    """A TX event reported one window late turns charged LISTEN time into TX: accepted,
    cumulative per-state energy on the bus equals the adapter's."""
    warnings.simplefilter("ignore", UserWarning)
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    adapter.ensure_interfaces(["acoustic"])
    contract = {
        "agent_type": "BlueROV2",
        "control_scheme": 0,
        "action_units": "force_N",
        "thruster_count": 8,
        "dt_s": 0.01,
    }

    class Backend:
        def step(self, action):
            return {}

        def close(self):
            pass

    env = EnergyAwareEnv(Backend(), vehicle_profile="bluerov2-heavy", control_contract=contract)
    env.attach(adapter)
    env.step([0] * 8)
    adapter.observe([tx(0.0, 0.05)])  # known only after its first window was charged
    for _ in range(9):
        env.step([0] * 8)
    on_bus = env.energy.summary()["device_state_energy_Wh"]["comms.acoustic"]
    expected = adapter.energy_J(0.1)["comms.acoustic"]
    for state, joules in expected.items():
        assert on_bus[state] * 3600 == pytest.approx(joules, abs=1e-9)
    env.close()


def test_metrics_from_host_events_and_file(tmp_path):
    events = [
        {
            "event": "generated",
            "time": 0.0,
            "packet_id": "p1",
            "source": "auv0",
            "destination": "buoy",
            "size": 32,
        },
        tx(0.0, 0.1, packet_id="p1"),
        tx(1.0, 0.1, packet_id="p1"),
        {
            "event": "delivered",
            "time": 1.3,
            "packet_id": "p1",
            "source": "auv0",
            "destination": "buoy",
            "size": 32,
            "delay": 1.3,
        },
    ]
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events), encoding="utf-8")
    adapter = DesertEnergyAdapter.from_events_file(path, {"acoustic": PROFILE}, node="auv0")
    m = adapter.network_metrics(t_end=2.0)
    assert m["delivery_ratio"] == 1.0
    assert m["retransmissions"] == 1
    assert m["energy_per_delivered_byte_J"] == pytest.approx(
        m["communication_energy_Wh"] * 3600 / 32
    )


def test_acoustic_power_events_do_not_become_electrical_power():
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    adapter.observe(
        [{"event": "power_applied", "time": 0, "node_id": "auv0", "tx_power_db": 180}, tx(0, 1)]
    )
    assert adapter.energy_J(1.0)["comms.acoustic"]["TX"] == pytest.approx(10.0)


def test_observing_proxy_forwards_unchanged():
    class Session:
        def __init__(self):
            self.calls = []

        def step(self, ticks=1):
            self.calls.append(ticks)
            return [tx(0.0, 0.1)]

        def send(self, *a):
            self.calls.append(("send", a))

    session = Session()
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    proxy = adapter.observed(session)
    result = proxy.step(3)
    proxy.send("x")
    assert result == [tx(0.0, 0.1)]
    assert session.calls == [3, ("send", ("x",))]
    assert adapter.events_seen == 1


def test_attach_to_energy_env_adds_communications_category():
    warnings.simplefilter("ignore", UserWarning)

    class Backend:
        def step(self, action):
            return {}

    env = EnergyAwareEnv(
        Backend(),
        vehicle_profile="bluerov2-heavy",
        control_contract={
            "action_units": "force_N",
            "thruster_count": 8,
            "dt_s": 0.01,
            "agent_type": "BlueROV2",
            "control_scheme": 0,
        },
        overrides={"logging": {"enabled": False}},
    )
    adapter = DesertEnergyAdapter({"acoustic": PROFILE}, node="auv0")
    adapter.ensure_interfaces(["acoustic"])
    adapter.observe([tx(0.0, 0.5)])
    env.attach(adapter)
    for _ in range(100):
        env.step([0] * 8)
    cats = env.energy.categories
    assert cats["communications"] == pytest.approx((0.5 * 10 + 0.5 * 0.5) / 3600, rel=1e-6)
    assert env.energy.summary()["device_state_energy_Wh"]["comms.acoustic"]["TX"] > 0
    with pytest.raises(ConfigurationError, match="already attached"):
        env.attach(adapter)


def test_generic_adapter_requires_profiles():
    with pytest.raises(ConfigurationError, match="At least one"):
        CommunicationEnergyAdapter({})
