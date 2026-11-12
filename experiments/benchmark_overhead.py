"""Per-tick cost of the HoloEnergy layer, separated from the simulator (no HoloOcean launch).

The recorded body-wrench sequence of a native run (full per-tick trace in
logs/native_campaign) is replayed through EnergyAwareEnv on a null backend, so only the
energy layer is timed: allocation, electrical models, bus, battery, evidence, logging off.
Modes: thrusters (per-actuator forces, the applied native vector), wrench/direct (L8-HV),
wrench/wrench-equivalent (L6-STD, two allocations per tick), and wrench/direct with the
telemetry publisher and dashboard server running and being polled. The native step wall
time of the same run (HoloOcean + HoloEnergy) is reported for scale.
"""

from __future__ import annotations

import gzip
import json
import statistics
import sys
import threading
import time
import urllib.request
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_native_campaign import CONTRACT, layout_config  # noqa: E402

from holoenergy import EnergyAwareEnv  # noqa: E402
from holoenergy.dashboard.server import DashboardServer  # noqa: E402
from holoenergy.telemetry import TelemetryPublisher  # noqa: E402

RUN = "N4-L8-HV-transit-c0.2"


class NullBackend:
    def step(self, action):
        return {}

    def reset(self):
        return {}

    def close(self):
        pass


def ticks():
    path = ROOT / "logs/native_campaign" / f"{RUN}.trace.jsonl.gz"
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle]


def time_mode(mode, rows, repeats):
    layout, mapping = (
        ("L6-STD", "wrench_equivalent") if mode == "wrench_equivalent" else ("L8-HV", "direct")
    )
    results = []
    for _ in range(repeats):
        config, _ = layout_config(layout, mapping)
        if mode == "thrusters":
            config["actuation"]["action_mode"] = "thrusters"
        server = publisher = None
        stop, polls = threading.Event(), []
        if mode == "dashboard":
            server = DashboardServer(0, 0).start()
            publisher = TelemetryPublisher(server.telemetry_port, 10)

            def poll(server=server, stop=stop, polls=polls):
                while not stop.is_set():
                    try:
                        with urllib.request.urlopen(
                            server.url + "api/state", timeout=2
                        ) as response:
                            json.load(response)
                        polls.append(1)
                    except OSError:
                        pass
                    stop.wait(0.25)

            threading.Thread(target=poll, daemon=True).start()
        env = EnergyAwareEnv(
            NullBackend(), config=config, control_contract=CONTRACT, telemetry=publisher
        )
        actions = [r["applied_N"] if mode == "thrusters" else r["requested_wrench"] for r in rows]
        start = time.perf_counter()
        for action in actions:
            env.step(action)
        elapsed = time.perf_counter() - start
        env.close()
        stop.set()
        if publisher is not None:
            publisher.close()
        if server is not None:
            server.close()
        results.append({"us_per_tick": 1e6 * elapsed / len(actions), "dashboard_polls": len(polls)})
    return {
        "mode": mode,
        "ticks": len(rows),
        "repeats": repeats,
        "median_us_per_tick": statistics.median(r["us_per_tick"] for r in results),
        "min_us_per_tick": min(r["us_per_tick"] for r in results),
        "max_us_per_tick": max(r["us_per_tick"] for r in results),
        "dashboard_polls": sum(r["dashboard_polls"] for r in results),
    }


def main():
    warnings.simplefilter("ignore", UserWarning)
    rows = ticks()
    summary = json.loads(
        (ROOT / "experiments/results/native/N4_mission" / f"{RUN}.summary.json").read_text(
            encoding="utf-8"
        )
    )
    native_us = 1e6 * summary["timing"]["env_step_wall_s"] / summary["timing"]["ticks"]
    modes = [
        time_mode(m, rows, 3)
        for m in ("thrusters", "wrench_direct", "wrench_equivalent", "dashboard")
    ]
    for m in modes:
        m["share_of_native_step"] = m["median_us_per_tick"] / native_us
        m["max_real_time_factor_energy_only_at_100Hz"] = 1e4 / m["median_us_per_tick"]
    out = {
        "run": RUN,
        "native_step_us_per_tick_holoocean_plus_holoenergy": native_us,
        "native_real_time_factor": summary["timing"]["real_time_factor"],
        "machine_note": "measured while other HoloOcean instances were running (shared CPU/GPU)",
        "modes": modes,
        "timing_effect": "the dashboard is a client of the same telemetry; simulation time is "
        "fixed-step and is not affected by wall-clock overhead",
    }
    path = ROOT / "experiments/results/native/benchmark_overhead.json"
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
