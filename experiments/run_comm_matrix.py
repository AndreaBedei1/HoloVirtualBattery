"""Native DESERT communication-energy matrix (observe-only; existing holo_desert capabilities).

Every configuration runs on a real DESERT engine that the caller started on a NON-default
port (``--port``; the session never manages Docker). The same application traffic is
offered in every configuration: ``--messages`` unicast JSON messages from the first to
the last node, one every ``--interval-s`` seconds, then a drain period.

Configurations (bundled holo_desert scenarios, changed only where stated):

  A  direct acoustic                e01_chat (2 nodes, 30 m), CSMA-ALOHA, static routing
  A2 direct acoustic + MAC ACK      A with ``mac.ack = true`` (native ALOHA ACK/retries)
  B  multi-hop acoustic             e05_multihop (3 nodes, 500 m spacing, static via relay)
  B2 multi-hop acoustic + MAC ACK   B with ``mac.ack = true``
  C  multi-hop acoustic, flooding   B with ``routing = flooding`` (routes removed)
  C4S 4 nodes, static (direct)      e02_multi_node (40 m square, all in range), diagonal unicast
  C4F 4 nodes, flooding             C4S with ``routing = flooding``: neighbours rebroadcast
  E  direct optical                 2 nodes 8 m apart at 10 m depth, ``medium = optical``
  F  hybrid acoustic/optical        holo_desert's multi-PHY example (received-power switch)

EM is omitted: the only electrical evidence is a chip-level proxy (SX1276, grade C).

Electrical profiles: EvoLogics S2C M 18/34 at its 1000 m setting (acoustic) and Hydromea
LUMA 250LP (optical, TX at its published maximum -> upper bound). The DESERT source level
(dB re 1 uPa) and optical TX power are network parameters and are NOT converted to watts.
For every run E = sum_state P_state * t_state is recomputed independently from the raw
PHY event durations and compared with the adapter.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holoenergy.catalog import modem_profile  # noqa: E402
from holoenergy.evidence import default_registry  # noqa: E402
from holoenergy.integrations import ModemPowerProfile  # noqa: E402
from holoenergy.integrations.desert import DesertEnergyAdapter  # noqa: E402
from holoenergy.provenance import git_state  # noqa: E402

# DESERT optical PHY at the bitrate of the modem whose power is charged (hydromea_luma250lp.bitrate).
LUMA_BITRATE_BPS = 250_000
PROFILES = {
    "acoustic": "evologics-s2cm-18-34-1000m",
    "optical": "hydromea-luma250lp-max",
}
HYBRID = {
    "multiphy": {
        "interfaces": [
            {
                "id": "acoustic",
                "acoustic": {
                    "frequency_hz": 25000,
                    "bandwidth_hz": 5000,
                    "bitrate_bps": 4800,
                    "tx_power_db": 150,
                },
            },
            {"id": "optical", "medium": "optical", "optical": {"bitrate_bps": LUMA_BITRATE_BPS}},
        ],
        "initial_interface": "acoustic",
        "policy": "received_power",
        "master": "auv_01",
        "thresholds": [
            {"from_interface": "acoustic", "to_interface": "optical", "power_linear": 1e13},
            {"from_interface": "optical", "to_interface": "acoustic", "power_linear": 3e-8},
        ],
    }
}


def bounded_states(profile_key):
    """States whose electrical power is a published maximum/upper bound (not a typical value)."""
    registry = default_registry()
    result = {}
    for state, value in modem_profile(profile_key).get("states", {}).items():
        if isinstance(value, dict) and "evidence" in value:
            record = registry.get(value["evidence"])
            if value.get("use") == "value_max" or record.bound == "upper_bound":
                result[state] = record.id
    return result


def scenario_for(name):
    import holo_desert as h

    if name in ("A", "A2"):
        s = h.load_scenario("e01_chat")
        data = s.model_dump()
        data["network"]["mac"]["ack"] = name == "A2"
    elif name in ("B", "B2", "C"):
        s = h.load_scenario("e05_multihop")
        data = s.model_dump()
        data["network"]["mac"]["ack"] = name == "B2"
        if name == "C":
            data["network"]["routing"] = "flooding"
            data["network"]["routes"] = {}
    elif name in ("C4S", "C4F"):
        s = h.load_scenario("e02_multi_node")
        data = s.model_dump()
        if name == "C4F":
            data["network"]["routing"] = "flooding"
            data["network"]["routes"] = {}
    elif name == "E":
        s = h.load_scenario("e01_chat")
        data = s.model_dump()
        data["network"]["medium"] = "optical"
        data["network"]["optical"]["bitrate_bps"] = LUMA_BITRATE_BPS
        data["nodes"][0]["position"] = (0.0, 0.0, -10.0)
        data["nodes"][1]["position"] = (8.0, 0.0, -10.0)
    elif name == "F":
        s = h.load_scenario("e01_chat")
        data = s.model_dump()
        data["network"] = h.Network.model_validate(HYBRID).model_dump()
        data["nodes"][0]["position"] = (0.0, 0.0, -10.0)
        data["nodes"][1]["position"] = (8.0, 0.0, -10.0)
    else:
        raise ValueError(name)
    data["name"] = f"holoenergy_comm_{name}"
    return h.Scenario.model_validate(data)


def interface_media(scenario):
    """{node: {interface_index: medium}}; a single-PHY node uses index 0."""
    from holo_desert.resources.docker.multiphy_config import effective_interfaces

    effective = {n["id"]: n["interfaces"] for n in effective_interfaces(scenario.model_dump())}
    return {
        n.id: {p["index"]: p["medium"] for p in effective.get(n.id, [])}
        or {0: scenario.network.medium}
        for n in scenario.nodes
    }


def media_by_interface(scenario):
    return {node: list(m.values()) for node, m in interface_media(scenario).items()}


def union_length(intervals):
    total, end = 0.0, None
    start = None
    for a, b in sorted(intervals):
        if end is None or a > end:
            if end is not None:
                total += end - start
            start, end = a, b
        else:
            end = max(end, b)
    if end is not None:
        total += end - start
    return total


def recompute(events, scenario, powers, t_end):
    """Independent E = sum P*t from raw PHY events (half-duplex: TX > RX > LISTEN)."""
    inverse = {v: k for k, v in scenario.node_map.items()}
    media = media_by_interface(scenario)
    index_media = interface_media(scenario)
    tx, rx = {}, {}
    for e in events:
        name = e["event"]
        if not name.startswith("phy_") or not name.endswith("_start"):
            continue
        node = inverse.get(e.get("node"), e.get("node_id"))
        index = e.get("interface_index", 0)
        medium = e.get("medium") or index_media[node][index]
        key = (node, medium)
        # Charge only inside the observation horizon [0, t_end] (as the adapter does).
        interval = (min(e["time"], t_end), min(e["time"] + e["duration_s"], t_end))
        if "_tx_" in name:
            tx.setdefault(key, []).append(interval)
        elif e.get("outcome") == "synchronized":
            rx.setdefault(key, []).append(interval)
    result = {}
    for node, node_media in media.items():
        for medium in dict.fromkeys(node_media):
            key = (node, medium)
            t_tx = union_length(tx.get(key, []))
            t_busy = union_length(tx.get(key, []) + rx.get(key, []))
            t_rx = t_busy - t_tx
            t_listen = t_end - t_busy
            p = powers[medium]
            result[f"{node}/{medium}"] = {
                "TX_s": t_tx,
                "RX_s": t_rx,
                "LISTEN_s": t_listen,
                "energy_J": p["TX"] * t_tx + p["RX"] * t_rx + p["LISTEN"] * t_listen,
            }
    return result


def run(name, args):
    import holo_desert as h

    scenario = scenario_for(name)
    profiles = {m: ModemPowerProfile.from_mapping(modem_profile(k)) for m, k in PROFILES.items()}
    media = sorted({m for ms in media_by_interface(scenario).values() for m in ms})
    adapter = DesertEnergyAdapter(
        {m: profiles[m] for m in media}, node=None, node_map=scenario.node_map
    )
    # Every node's modems listen from t=0, including interfaces that never see an event.
    adapter.ensure_interfaces(media)
    names = [n.id for n in scenario.nodes]
    # Last node, except the 4-node square where the diagonal (auv_03) is the destination.
    source, destination = names[0], (names[2] if name in ("C4S", "C4F") else names[-1])
    session = h.NetworkSession(scenario, port=args.port, manage_engine=False)
    events = []
    with session:
        net = adapter.observed(session)
        for k in range(args.messages):
            net.node(source).send(destination, {"seq": k, "pad": "x" * args.payload})
            events += net.run_until(session.time + args.interval_s)
        events += net.run_until(session.time + args.drain_s)
        t_end = session.time
        summary = session.summary()
        packets = session.packets()
    metrics = adapter.network_metrics(t_end)
    recomputed = recompute(events, scenario, {m: profiles[m].powers_W for m in media}, t_end)
    adapter_J = {
        k: v["energy_Wh"] * 3600 for k, v in metrics["interfaces"].items() if "energy_Wh" in v
    }
    total_adapter_J = sum(adapter_J.values())
    total_recomputed_J = sum(v["energy_J"] for v in recomputed.values())
    delivered = [p for p in packets if p["status"] == "received"]
    payload_bytes = sum(p["size"] for p in delivered)
    counts = {}
    for e in events:
        counts[e["event"]] = counts.get(e["event"], 0) + 1
    by_packet = {p["id"]: p["source"] for p in packets}
    relay_forwards = sum(
        1
        for p in packets
        for e in p["events"]
        if e["event"] == "forward" and e.get("node_id") != by_packet.get(p["id"])
    )
    airtime = sum(v["TX_s"] for v in recomputed.values())
    bounded = {m: bounded_states(PROFILES[m]) for m in media}
    upper_J = sum(
        recomputed[k][f"{state}_s"] * profiles[k.split("/")[1]].powers_W[state]
        for k in recomputed
        for state in ("TX", "RX", "LISTEN")
        if state in bounded[k.split("/")[1]]
    )
    comm_Wh = total_adapter_J / 3600
    return {
        "configuration": name,
        "scenario": scenario.model_dump(mode="json"),
        "duration_s": t_end,
        "generated": summary["generated"],
        "delivered": summary["received"],
        "delivery_ratio": summary["pdr_generated"],
        "mean_latency_s": summary["mean_latency_s"],
        "tx_frames": counts.get("phy_tx_start", 0),
        "control_tx_frames": counts.get("phy_control_tx_start", 0),
        "rx_frames": counts.get("phy_rx_start", 0),
        "control_rx_frames": counts.get("phy_control_rx_start", 0),
        "relay_forwards": relay_forwards,
        "data_tx_frames_per_generated_message": counts.get("phy_tx_start", 0)
        / max(1, summary["generated"]),
        "airtime_s": airtime,
        "communication_Wh": comm_Wh,
        "upper_bound_states": bounded,
        "upper_bound_energy_share": upper_J / total_recomputed_J if total_recomputed_J else None,
        "energy_per_delivered_message_J": total_adapter_J / len(delivered) if delivered else None,
        "energy_per_delivered_payload_byte_J": total_adapter_J / payload_bytes
        if payload_bytes
        else None,
        "energy_check": {
            "adapter_J": total_adapter_J,
            "recomputed_J": total_recomputed_J,
            "relative_difference": total_adapter_J / total_recomputed_J - 1
            if total_recomputed_J
            else None,
            "per_interface_adapter_J": adapter_J,
            "per_interface_recomputed": recomputed,
        },
        "adapter_metrics": metrics,
        "mac_stats": summary.get("mac_stats"),
        "network_metrics": summary.get("network_metrics"),
        "event_counts": counts,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, required=True, help="own engine, non-default port")
    parser.add_argument(
        "--configs", nargs="+", default=["A", "A2", "B", "B2", "C", "C4S", "C4F", "E", "F"]
    )
    parser.add_argument("--messages", type=int, default=10)
    parser.add_argument("--payload", type=int, default=32)
    parser.add_argument("--interval-s", type=float, default=5.0)
    parser.add_argument("--drain-s", type=float, default=20.0)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/native/desert/comm_matrix.json"
    )
    args = parser.parse_args(argv)
    if args.port == 5555:
        raise SystemExit("Use a non-default DESERT port")
    import holo_desert

    results = {}
    for name in args.configs:
        print(f"== {name}", flush=True)
        try:
            results[name] = run(name, args)
        except Exception as exc:  # noqa: BLE001 - failures are recorded, not hidden
            results[name] = {"configuration": name, "error": repr(exc)}
            print(f"FAILED {name}: {exc!r}", flush=True)
            continue
        r = results[name]
        print(
            f"   delivered {r['delivered']}/{r['generated']} latency {r['mean_latency_s']} "
            f"tx {r['tx_frames']}+{r['control_tx_frames']} relays {r['relay_forwards']} "
            f"E {r['communication_Wh']:.5f} Wh, check {r['energy_check']['relative_difference']:.2e}",
            flush=True,
        )
    out = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "git": git_state(),
        "holo_desert_version": holo_desert.__version__,
        "port": args.port,
        "traffic": {
            "messages": args.messages,
            "payload_pad_chars": args.payload,
            "interval_s": args.interval_s,
            "drain_s": args.drain_s,
        },
        "profiles": PROFILES,
        "scope": "observe-only communication energy on the native DESERT engine",
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    return 0 if all("error" not in r for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
