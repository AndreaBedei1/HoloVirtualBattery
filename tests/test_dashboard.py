"""Local dashboard transport/lifecycle checks, including a high-rate publisher."""

import json
import socket
import time
import urllib.request

import pytest

from holoenergy.dashboard.server import DashboardServer, DashboardStore
from holoenergy.telemetry import TelemetryPublisher


def snapshot(server):
    with urllib.request.urlopen(server.url + "api/state", timeout=2) as response:
        return json.load(response)


def wait_for(server, status):
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        state = snapshot(server)
        if state["status"] == status:
            return state
        time.sleep(0.01)
    raise AssertionError(f"Dashboard did not reach {status}")


def test_start_live_reset_end_and_clean_shutdown():
    with DashboardServer(0, 0) as server:
        url, port = server.url, server.telemetry_port
        with urllib.request.urlopen(url, timeout=2) as response:
            assert b"Mission monitor" in response.read()
        assert snapshot(server)["status"] == "waiting"
        with TelemetryPublisher(port, 100) as publisher:
            publisher.publish(
                {
                    "run_id": "test",
                    "episode": 0,
                    "time_s": 1,
                    "component_power_W": {"custom_sensor": 7.2, "computer": 25},
                }
            )
            state = wait_for(server, "live")
            assert state["latest"]["component_power_W"]["custom_sensor"] == 7.2
            assert len(state["history"]) == 1
            publisher.event("reset", episode=1)
            assert wait_for(server, "reset")["latest"] is None
            publisher.event("end_mission", summary={"terminal_energy_Wh": 2})
            assert wait_for(server, "ended")["summary"]["terminal_energy_Wh"] == 2
        assert publisher.closed
    assert all(not t.is_alive() for t in server.threads)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", port))  # receiver socket was released


def test_disconnection_missing_optional_values_and_episode_history():
    store = DashboardStore(history_s=10, max_samples=5, stale_after_s=0.01)
    for i in range(100):
        store.accept(
            {
                "schema_version": 1,
                "event": "sample",
                "energy": {"time_s": i, "run_id": "a", "episode": 0},
            }
        )
    assert len(store.snapshot()["history"]) == 5
    store.last_received -= 1
    assert store.snapshot()["status"] == "disconnected"
    store.accept(
        {
            "schema_version": 1,
            "event": "sample",
            "energy": {"time_s": 0, "run_id": "a", "episode": 1},
        }
    )
    assert len(store.snapshot()["history"]) == 1
    store.accept({"schema_version": 2, "event": "reset"})
    assert store.snapshot()["status"] == "live"


def test_high_frequency_simulation_is_throttled_and_no_server_required():
    with TelemetryPublisher(8766, publish_hz=10) as publisher:
        start = time.monotonic()
        for i in range(10000):
            publisher.publish({"time_s": i * 0.001, "optional": None})
        elapsed = time.monotonic() - start
        assert publisher.sent <= 1 + int(elapsed * 10)
        assert publisher.dropped == 0
        publisher.event("end_mission")
    publisher.publish({"time_s": 0})  # closed publisher has no effect on simulation


def test_bad_packet_and_failed_startup_leave_no_receiver():
    with DashboardServer(0, 0) as server:
        port = server.telemetry_port
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.sendto(b"invalid JSON", ("127.0.0.1", port))
        with pytest.raises(OSError):
            DashboardServer(0, port)
        assert snapshot(server)["status"] == "waiting"


def test_oversized_telemetry_is_dropped_without_blocking():
    with TelemetryPublisher(8766) as publisher:
        publisher.publish({"time_s": 0, "data": "x" * 65000})
        assert publisher.dropped == 1 and publisher.sent == 0
