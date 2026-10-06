"""Repeated mean step costs: bare backend, energy, energy with telemetry/dashboard service."""

import copy
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
from _common import backend, parser, settings, simulator_action  # noqa: E402

from holoenergy import EnergyAwareEnv  # noqa: E402
from holoenergy.analysis.replay import ReplayBackend  # noqa: E402
from holoenergy.dashboard.server import DashboardServer  # noqa: E402
from holoenergy.provenance import write_json  # noqa: E402
from holoenergy.telemetry import TelemetryPublisher  # noqa: E402


def run(args, baseline, mode):
    config = copy.deepcopy(baseline)
    config["logging"] = {"enabled": False}
    config["provenance"]["purpose"] = "step-overhead benchmark; physical accuracy not evaluated"
    server = None
    publisher = None
    stop = threading.Event()
    polling = None
    polls = []
    if mode == "dashboard":
        server = DashboardServer(0, 0).start()
        publisher = TelemetryPublisher(server.telemetry_port, 10)

        def poll():
            while not stop.is_set():
                try:
                    with urllib.request.urlopen(server.url + "api/state", timeout=2) as response:
                        json.load(response)
                    polls.append(1)
                except OSError:
                    pass
                stop.wait(0.25)

        polling = threading.Thread(target=poll, daemon=True)
        polling.start()
    base = None
    env = None
    try:
        if args.backend == "synthetic":
            base = ReplayBackend(config)
            contract = base.energy_action_contract
        else:
            base, contract = backend(args, config)
        env = (
            base
            if mode == "baseline"
            else EnergyAwareEnv(base, config=config, control_contract=contract, telemetry=publisher)
        )
        action = (
            [0.0] * 4 + [5.0] * 4
            if args.backend == "holoocean"
            else [5.0] * config["propulsion"]["thruster_count"]
        )
        action = simulator_action(args, action)
        start = time.perf_counter()
        for _ in range(args.steps):
            env.step(action)
        elapsed = time.perf_counter() - start
        return {
            "mode": mode,
            "mean_step_ms": 1000 * elapsed / args.steps,
            "wall_s": elapsed,
            "steps": args.steps,
            "telemetry_samples_sent": publisher.sent if publisher else 0,
            "dashboard_polls": len(polls),
            "terminal_energy_Wh": env.battery.energy_used_Wh if mode != "baseline" else None,
        }
    finally:
        if env is not None:
            if hasattr(env, "close"):
                env.close()
            else:
                env.__exit__(None, None, None)
        elif base is not None:
            if hasattr(base, "close"):
                base.close()
            else:
                base.__exit__(None, None, None)
        stop.set()
        if polling is not None:
            polling.join(timeout=3)
        if publisher is not None:
            publisher.close()
        if server is not None:
            server.close()


def main():
    p = parser(__doc__)
    p.add_argument("--trials", type=int, default=3)
    args = p.parse_args()
    if args.trials <= 0:
        p.error("--trials must be positive")
    config = settings(args)
    records = []
    for trial in range(args.trials):
        for mode in ("baseline", "energy", "dashboard"):
            result = {"trial": trial, **run(args, config, mode)}
            records.append(result)
            print(f"Trial {trial + 1}, {mode}: {result['mean_step_ms']:.4f} ms/step", flush=True)
    means = {
        mode: sum(r["mean_step_ms"] for r in records if r["mode"] == mode) / args.trials
        for mode in ("baseline", "energy", "dashboard")
    }
    write_json(
        args.output_dir / "performance.json",
        {
            "backend": args.backend,
            "means_ms_per_step": means,
            "energy_overhead_ms": means["energy"] - means["baseline"],
            "dashboard_increment_ms": means["dashboard"] - means["energy"],
            "records": records,
            "logging": "disabled equally in energy/dashboard modes",
            "dashboard_transport": "10 Hz maximum wall-clock publication, HTTP client polls at 4 Hz",
            "browser_render_cost": "separate browser process; not included in simulator step timer",
            "interpretation": "machine/load dependent repeated means; negative differences are timing noise, not speedup",
        },
    )


if __name__ == "__main__":
    main()
