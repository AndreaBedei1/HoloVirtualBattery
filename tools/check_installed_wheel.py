"""Smoke-test installed resources from an isolated interpreter, outside source imports."""

import importlib.resources
import json
import sys
import warnings
from pathlib import Path

import holoenergy
from holoenergy import EnergyAwareEnv
from holoenergy.allocation import ActuatorGeometry, ThrustAllocator
from holoenergy.analysis.replay import ReplayBackend
from holoenergy.catalog import BATTERIES, VEHICLES, list_profiles, vehicle_config
from holoenergy.config import load_config
from holoenergy.dashboard.server import DashboardServer
from holoenergy.evidence import default_registry


def main():
    # Demo profiles intentionally carry uncalibrated parameters; their warnings are tested elsewhere.
    warnings.simplefilter("ignore", UserWarning)
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
    registry = default_registry()
    assert len(registry.records) > 0 and len(registry.sources) > 0
    profiles = list_profiles()
    assert profiles and VEHICLES and BATTERIES
    # Data added in v0.2 must ship with the wheel (registry records with packaged datasets).
    for record_id in (
        "bluerov2_standard.restrained_inline_load_head_on",
        "holoocean_bluerov2.drag_area",
        "bluerobotics_t200.static_force_power_curve",
    ):
        record = registry.get(record_id)
        if record.dataset:
            assert package.joinpath(record.dataset["path"]).is_file(), record.dataset["path"]
    assert "torpedo-remus-like" in VEHICLES and "bluerov2-standard" in VEHICLES
    for name in VEHICLES:
        config = load_config(data=vehicle_config(name))
        assert config["propulsion"]["thruster_count"] > 0, name
    geometry = [
        ActuatorGeometry(f"t{i}", position, direction)
        for i, (position, direction) in enumerate(
            [
                ((0.2, 0.1, 0), (1, 0, 0)),
                ((0.2, -0.1, 0), (1, 0, 0)),
                ((0, 0, 0), (0, 1, 0)),
                ((0, 0, 0), (0, 0, 1)),
            ]
        )
    ]
    result = ThrustAllocator(geometry, method="pseudoinverse").allocate(
        [1.0, 0, 0, 0, 0, 0], lower=[-10] * 4, upper=[10] * 4
    )
    assert result.residual_norm < 1e-9, result
    with DashboardServer(http_port=0, telemetry_port=0) as server:
        assert server.http.server_address[1] > 0 and server.telemetry_port > 0
    print(f"Installed wheel verified: Python {sys.version.split()[0]}, {installed}")


if __name__ == "__main__":
    main()
