"""Cross-layer experiment: network strategy -> network activity -> communication energy
-> battery state -> mission energy, on native HoloOcean (verified patched backend, 100 Hz)
coupled to a native DESERT engine through holo_desert.HoloOceanLink.

Same vehicle (BlueROV2 Heavy, simulator-exact layout, default avionics), same mission
(transit: accelerate, transit, stop, yaw 180 deg, return), same world-X current and the
same application traffic (one telemetry message every ``--period-s`` from the vehicle to a
sink); only the network configuration differs:

  none        no communication (baseline)
  direct      acoustic, sink 30 m away, CSMA-ALOHA, static routing
  ack         as direct with the native ALOHA MAC ACK
  multihop    acoustic, sink 1000 m away through a static relay at 500 m
  flooding    multihop geometry with flooding routing
  optical     optical, sink 8 m away (inside the pinned optical noise-table depth range)

Observe-only: DESERT advances one physics tick after HoloOcean on the same timeline; its
events are only read. The vehicle's own modem energy enters the HoloEnergy bus through
``EnergyAwareEnv.attach`` (category ``communications``) and therefore the battery; nothing
from the battery or the energy model is fed back to DESERT (scheduling, MAC or routing).
Requires an engine on a non-default port that the caller started (``--port``).
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_native_campaign import (  # noqa: E402
    CONTRACT,
    DT,
    PLANS,
    SCENARIO,
    WrenchController,
    layout_config,
    metrics,
    tick_row,
)

from holoenergy import EnergyAwareEnv, __version__  # noqa: E402
from holoenergy.catalog import modem_profile  # noqa: E402
from holoenergy.integrations import ModemPowerProfile  # noqa: E402
from holoenergy.integrations.desert import DesertEnergyAdapter  # noqa: E402
from holoenergy.provenance import git_state  # noqa: E402
from tools.holoocean_backend import make_env, package_identity  # noqa: E402

VEHICLE_NODE = "auv_01"
SINK = "auv_02"  # holo_desert node ids must match auv_NN
RELAY = "auv_03"
# Relay experiment: a source and a sink 500 m either side of the vehicle (the spacing of
# holo_desert's bundled e05_multihop scenario) and a fixed relay 30 m beside the vehicle's
# mid-span position. Traffic originates at the source; the vehicle sends nothing itself.
SOURCE, FAR_SINK, FIXED_RELAY = "auv_02", "auv_03", "auv_04"
RELAY_STRATEGIES = ("relay-vehicle", "relay-fixed")
PROFILES = {"acoustic": "evologics-s2cm-18-34-1000m", "optical": "hydromea-luma250lp-max"}
START = (0.0, 0.0, -5.0)  # SCENARIO agent location


def network_scenario(strategy):
    import holo_desert as h

    nodes = [{"id": VEHICLE_NODE, "position": START}]
    network = {"mac": {"protocol": "csma_aloha", "ack": strategy == "ack"}}
    if strategy in ("direct", "ack"):
        nodes.append({"id": SINK, "position": (30.0, 0.0, -5.0)})
    elif strategy in ("multihop", "flooding"):
        nodes += [
            {"id": RELAY, "position": (500.0, 0.0, -5.0)},
            {"id": SINK, "position": (1000.0, 0.0, -5.0)},
        ]
        if strategy == "multihop":
            network["routes"] = {VEHICLE_NODE: {SINK: RELAY}, SINK: {VEHICLE_NODE: RELAY}}
        else:
            network["routing"] = "flooding"
    elif strategy == "optical":
        nodes.append({"id": SINK, "position": (8.0, 0.0, -5.0)})
        network["medium"] = "optical"
        network["optical"] = {"bitrate_bps": 250_000}  # hydromea_luma250lp.bitrate
    elif strategy in RELAY_STRATEGIES:
        nodes += [
            {"id": SOURCE, "position": (-500.0, 0.0, -5.0)},
            {"id": FAR_SINK, "position": (500.0, 0.0, -5.0)},
            {"id": FIXED_RELAY, "position": (0.0, 30.0, -5.0)},
        ]
        via = VEHICLE_NODE if strategy == "relay-vehicle" else FIXED_RELAY
        network["routes"] = {SOURCE: {FAR_SINK: via}, FAR_SINK: {SOURCE: via}}
    else:
        raise ValueError(strategy)
    return h.Scenario.model_validate(
        {
            "name": f"holoenergy_crosslayer_{strategy}",
            "description": "HoloEnergy cross-layer experiment",
            "physics_hz": round(1 / DT),
            "nodes": nodes,
            "network": network,
        }
    )


def run(strategy, args):
    import holo_desert as h
    import numpy as np

    config, meta = layout_config("L8-HV", "direct")
    current = [args.current, 0.0, 0.0]
    plan = PLANS["transit"]()
    session = vehicle = everyone = link = None
    medium = None
    if strategy != "none":
        scenario = network_scenario(strategy)
        medium = scenario.network.medium
        profile = ModemPowerProfile.from_mapping(modem_profile(PROFILES[medium]))
        vehicle = DesertEnergyAdapter(
            {medium: profile}, node=VEHICLE_NODE, node_map=scenario.node_map, name="comms"
        )
        vehicle.ensure_interfaces([medium])
        everyone = DesertEnergyAdapter({medium: profile}, node=None, node_map=scenario.node_map)
        everyone.ensure_interfaces([medium])
        session = h.NetworkSession(scenario, port=args.port, manage_engine=False)
    base = make_env(copy.deepcopy(SCENARIO), round(1 / DT), args.binary)
    ticks, events_seen, wall0 = [], 0, time.perf_counter()
    try:
        with EnergyAwareEnv(base, config=config, control_contract=CONTRACT) as env:
            state = base.reset()
            env.energy.set_environment(current_velocity_m_s=current, current_mode="native")
            if session is not None:
                session.start()
                env.attach(vehicle)
                link = h.HoloOceanLink(session, {"rov0": VEHICLE_NODE}, ticks_per_sec=round(1 / DT))
                link.attach(state)
            controller = WrenchController()
            target = np.asarray(state["PoseSensor"])[:3, 3].copy()
            phase, next_send = None, 0.0
            for item in plan:
                if item["phase"] != phase:
                    phase = item["phase"]
                    env.energy.mark_phase(phase)
                if session is not None and session.time >= next_send - 1e-9:
                    sender, receiver = (
                        (SOURCE, FAR_SINK) if strategy in RELAY_STRATEGIES else (VEHICLE_NODE, SINK)
                    )
                    session.node(sender).send(
                        receiver, {"t": round(session.time, 2), "pad": "x" * args.payload}
                    )
                    next_send += args.period_s
                velocity_ref = np.array(item["velocity"])
                target = target + velocity_ref * DT
                wrench = controller(state, target, velocity_ref, item["yaw"], item["yaw_rate"])
                if link is not None:
                    # DESERT advances over [t, t+dt] with the poses applied at t (the
                    # HoloOceanLink.sync semantics, split so that the energy step of the same
                    # tick already knows its PHY events), then the measured poses are stored.
                    events = session.step(1)
                    events_seen += len(events)
                    vehicle.observe(events)
                    everyone.observe(events)
                state = env.step(wrench)
                if link is not None:
                    session.update_poses(link.read_poses(state))
                ticks.append(tick_row(state, phase, target, wrench, current))
            summary = env.energy.summary()
            report = env.energy.report().to_dict()
    finally:
        if session is not None:
            network_summary = session.summary()
            session.close()
        else:
            network_summary = {}
        close = getattr(base, "close", None)
        if close is not None:
            close()
    t_end = len(ticks) * DT
    m = metrics(ticks, summary)
    result = {
        "strategy": strategy,
        "medium": medium,
        "layout": meta,
        "current_m_s": current,
        "mission": m,
        "evidence": summary.get("evidence"),
        "energy_report": report,
        "final_position_m": ticks[-1]["position_m"],
        "wall_s": time.perf_counter() - wall0,
    }
    if session is not None:
        vehicle_J = sum(sum(s.values()) for s in vehicle.energy_J(t_end).values())
        network_J = sum(sum(s.values()) for s in everyone.energy_J(t_end).values())
        result["network"] = {
            "generated": network_summary.get("generated"),
            "delivered": network_summary.get("received"),
            "delivery_ratio": network_summary.get("pdr_generated"),
            "mean_latency_s": network_summary.get("mean_latency_s"),
            "events_observed": events_seen,
            "vehicle_metrics": vehicle.network_metrics(t_end),
            "network_wide_metrics": everyone.network_metrics(t_end),
            "vehicle_modem_Wh_adapter": vehicle_J / 3600,
            "network_wide_modem_Wh": network_J / 3600,
            "vehicle_modem_Wh_on_bus": m["communications_Wh"],
            "bus_minus_adapter_Wh": m["communications_Wh"] - vehicle_J / 3600,
        }
        result["communication_share_of_terminal_energy"] = (
            m["communications_Wh"] / m["terminal_Wh"] if m["terminal_Wh"] else None
        )
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--binary", type=Path, required=True)
    parser.add_argument("--port", type=int, required=True, help="own DESERT engine, not 5555")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=["none", "direct", "ack", "multihop", "flooding", "optical", *RELAY_STRATEGIES],
    )
    parser.add_argument("--current", type=float, default=0.2)
    parser.add_argument("--period-s", type=float, default=2.0)
    parser.add_argument("--payload", type=int, default=32)
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/native/crosslayer.json"
    )
    args = parser.parse_args(argv)
    if args.port == 5555:
        raise SystemExit("Use a non-default DESERT port")
    import holo_desert

    out = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "holoenergy_version": __version__,
        "git": git_state(),
        "backend": package_identity(args.binary),
        "holo_desert_version": holo_desert.__version__,
        "desert_port": args.port,
        "traffic": {"period_s": args.period_s, "payload_pad_chars": args.payload},
        "profiles": PROFILES,
        "results": {},
    }
    if args.output.exists():
        out["results"] = json.loads(args.output.read_text(encoding="utf-8")).get("results", {})
    for strategy in args.strategies:
        print(f"== {strategy}", flush=True)
        try:
            r = run(strategy, args)
        except Exception as exc:  # noqa: BLE001 - failures are recorded, not hidden
            out["results"][strategy] = {"strategy": strategy, "error": repr(exc)}
            print(f"FAILED {strategy}: {exc!r}", flush=True)
            continue
        out["results"][strategy] = r
        m, n = r["mission"], r.get("network", {})
        print(
            f"   total {m['terminal_Wh']:.4f} Wh, comm {m['communications_Wh']:.5f} Wh, "
            f"SOC loss {m['soc_loss']:.6f}, delivered {n.get('delivered')}/{n.get('generated')}",
            flush=True,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
