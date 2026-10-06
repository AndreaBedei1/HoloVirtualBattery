"""Smoke-test installed resources from an isolated interpreter, outside source imports."""

import importlib.resources
import json
import sys
from pathlib import Path

import holoenergy
from holoenergy import EnergyAwareEnv
from holoenergy.analysis.replay import ReplayBackend
from holoenergy.config import load_config
from holoenergy.dashboard.server import DashboardServer


def main():
    source_root = Path(__file__).resolve().parents[1]
    installed = Path(holoenergy.__file__).resolve()
    assert not installed.is_relative_to(source_root / "holoenergy"), installed
    package = importlib.resources.files("holoenergy")
    assert json.loads(package.joinpath("profiles/registry.json").read_text())
    assert "<html" in package.joinpath("dashboard/index.html").read_text().lower()
    for name in ("bluerov2_heavy", "generic_lightweight_rov", "generic_auv"):
        config = load_config(data={"profile": f"package:vehicles/{name}.yaml"})
        with EnergyAwareEnv(ReplayBackend(config), config=config) as env:
            row = env.step([1.0] * env.propulsion.count)["Energy"]
            assert row["power_total_W"] > 0
            assert env.energy.summary()["duration_s"] > 0
    with DashboardServer(http_port=0, telemetry_port=0) as server:
        assert server.http.server_address[1] > 0 and server.telemetry_port > 0
    print(f"Installed wheel verified: Python {sys.version.split()[0]}, {installed}")


if __name__ == "__main__":
    main()
