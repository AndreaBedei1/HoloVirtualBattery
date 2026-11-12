"""Verify that HoloEnergy communication accounting does not perturb holo_desert.

The same scenario and traffic run twice through ``holo_desert.NetworkSession``: once plain
and once through :meth:`DesertEnergyAdapter.observed`.  The backend command logs (poses,
SEND, STATS, STEP, power), the returned event streams (wall-clock fields removed), the
deliveries and the session summaries must be identical.  The adapter's energy is reported
alongside.

Modes
  --mode scripted  deterministic scripted backend emitting PHY events with durations
                   (no Docker); checks the integration seam itself.
  --mode native    real DESERT engine (holo_desert manages its Docker container) on a
                   NON-default port; checks scheduling/MAC/routing/PHY under accounting.
                   Requires Docker and the pinned DESERT image; run only deliberately.

Run with the Python environment that has ``holo_desert`` installed, e.g.
  <holo_desert venv>/python tools/check_desert_noninterference.py --mode scripted
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holoenergy.integrations import ModemPowerProfile  # noqa: E402
from holoenergy.integrations.desert import DesertEnergyAdapter  # noqa: E402

WALL_FIELDS = {"wall_time", "observed_wall_time"}


class ScriptedPhyBackend:
    """Deterministic transport: each SEND produces TX at the source and RX at the target."""

    pause_supported = True

    def __init__(self, bitrate=4800.0, delay=0.25):
        self.bitrate, self.delay = bitrate, delay
        self.time, self.log, self.inflight = 0.0, [], []
        self.versions, self.initial_events = {"engine_fingerprint": "scripted"}, []

    def start(self, scenario):
        self.nodes = scenario.node_map
        self.time = 0.0

    def update_node_position(self, node, pose, timestamp):
        self.log.append(("POSITION", node, (pose.x, pose.y, pose.z), timestamp))

    def send(self, message):
        self.log.append(("SEND", message.source, message.destination, self.time))
        self.inflight.append((self.time, message))

    def request_stats(self):
        self.log.append(("STATS", self.time))

    def advance(self, target):
        events = [
            {"event": "position_applied", "node": n, "time": self.time} for n in self.nodes.values()
        ]
        keep = []
        for t0, m in self.inflight:
            duration = len(m.encode()) * 8 / self.bitrate
            if t0 + self.delay <= target + 1e-9:
                src, dst = self.nodes[m.source], self.nodes[m.destination]
                events += [
                    {
                        "event": "phy_tx_start",
                        "time": t0,
                        "node": src,
                        "duration_s": duration,
                        "phy_bits": len(m.encode()) * 8,
                        "interface_index": 0,
                    },
                    {
                        "event": "phy_rx_start",
                        "time": t0 + self.delay - duration,
                        "node": dst,
                        "duration_s": duration,
                        "outcome": "synchronized",
                        "interface_index": 0,
                    },
                    {
                        "event": "rx",
                        "time": t0 + self.delay,
                        "node": dst,
                        "wire_hex": m.encode().hex(),
                        "observed_wall_time": 0,
                    },
                ]
            else:
                keep.append((t0, m))
        self.inflight = keep
        self.time = target
        self.log.append(("STEP", target))
        return events

    def set_power(self, node, value, interface=None):
        self.log.append(("POWER", node, value, interface))

    def stop(self):
        pass


def strip(events):
    """Remove wall-clock fields and the random per-message id that holo_desert draws
    (uuid4) for every Message; two plain runs differ in that id alone."""
    result = []
    for e in events:
        item = {k: v for k, v in e.items() if k not in WALL_FIELDS}
        if "wire_hex" in item:
            try:
                decoded = json.loads(bytes.fromhex(item["wire_hex"]))
                decoded.pop("id", None)
                item["wire_hex"] = decoded
            except (ValueError, TypeError):
                pass
        result.append(item)
    return result


def drop_wall_clock(value):
    """Remove wall-clock metadata at any depth (e.g. mac_stats.<node>.observed_wall_time)."""
    if isinstance(value, dict):
        return {k: drop_wall_clock(v) for k, v in value.items() if "wall" not in k}
    if isinstance(value, list):
        return [drop_wall_clock(v) for v in value]
    return value


def run(observe, args, profile):
    import holo_desert

    scenario = holo_desert.load_scenario(args.scenario)
    names = [n.id for n in scenario.nodes]
    backend = None
    if args.mode == "scripted":
        backend = ScriptedPhyBackend()
        session = holo_desert.NetworkSession(scenario, backend=backend)
    else:
        # The caller starts its own engine on --port; never let holo_desert manage Docker
        # (its Compose project could otherwise recreate another user's service).
        session = holo_desert.NetworkSession(scenario, port=args.port, manage_engine=False)
    adapter = DesertEnergyAdapter({"acoustic": profile}, node=None, node_map=scenario.node_map)
    target = adapter.observed(session) if observe else session
    events = []
    with session:
        for k in range(args.messages):
            src, dst = names[k % len(names)], names[(k + 1) % len(names)]
            target.node(src).send(dst, {"seq": k, "pad": "x" * args.payload})
            events += target.run_until(session.time + args.interval_s)
        events += target.run_until(session.time + 5.0)
        deliveries = {n: [d.message.payload for d in target.node(n).receive()] for n in names}
        summary = drop_wall_clock(session.summary())
    return {
        "backend_log": None if backend is None else backend.log,
        "events": strip(events),
        "deliveries": {k: [p.hex() for p in v] for k, v in deliveries.items()},
        "summary": summary,
        "energy": adapter.network_metrics() if observe else None,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--mode", choices=("scripted", "native"), default="scripted")
    parser.add_argument("--scenario", default="e01_chat")
    parser.add_argument("--messages", type=int, default=6)
    parser.add_argument("--payload", type=int, default=32)
    parser.add_argument("--interval-s", type=float, default=2.0)
    parser.add_argument("--port", type=int, default=5571, help="non-default DESERT port (native)")
    parser.add_argument(
        "--output", default=str(ROOT / "experiments" / "results" / "desert_noninterference.json")
    )
    args = parser.parse_args(argv)
    from holoenergy.catalog import modem_profile

    profile = ModemPowerProfile.from_mapping(modem_profile("evologics-s2cm-18-34-1000m"))
    plain = run(False, args, profile)
    observed = run(True, args, profile)
    checks = {
        key: plain[key] == observed[key]
        for key in ("backend_log", "events", "deliveries", "summary")
        if plain[key] is not None
    }
    result = {
        "mode": args.mode,
        "scenario": args.scenario,
        "messages": args.messages,
        "identical": checks,
        "verdict": "PASS" if all(checks.values()) else "FAIL",
        "observed_energy": observed["energy"],
        "scope": (
            "scripted backend: verifies the observation seam only"
            if args.mode == "scripted"
            else "native DESERT engine"
        ),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {checks} -> {out}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
