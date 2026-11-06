"""HoloWithDesertCommunications (``holo_desert``) -> HoloEnergy communication energy.

The adapter consumes the events that ``holo_desert`` already produces (the return
values of ``NetworkSession.step``/``run_until``/``HoloOceanLink.sync``, or a persisted
``events.jsonl``).  It never calls a method that changes network state, so packet
scheduling, MAC, routing, PHY decisions, delivery and latency are untouched.
``holo_desert`` is optional: nothing here imports it.

Event schema used (holo_desert 1.1.0, DESERT observer extensions ``bridge.cc`` and
``optical-em.h``): ``phy_[control_]{tx,rx}_{start,end}`` with ``time`` (simulated s),
``node`` (numeric) or host-enriched ``node_id``, ``interface_index``, ``duration_s``,
``phy_bits``, ``outcome`` (receptions) and ``medium`` (``optical``/``em``; absent for
acoustic).  Acoustic ``pt``/``tx_power_db`` are source levels in dB re 1 uPa and are
never interpreted as electrical power.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from .._validation import ConfigurationError
from .communications import CommunicationEnergyAdapter, ModemPowerProfile

PHY_EVENTS = {
    "phy_tx_start": ("TX", False),
    "phy_control_tx_start": ("TX", True),
    "phy_rx_start": ("RX", False),
    "phy_control_rx_start": ("RX", True),
}
# Reception outcomes at rx_start for which the modem is locked and demodulating.
DEFAULT_RX_OUTCOMES = frozenset({"synchronized"})
MUTATING_METHODS = frozenset(
    {"send", "send_json", "set_tx_power", "select_interface", "restart", "set_power"}
)


def medium_of(event):
    return event.get("medium") or "acoustic"


class DesertEnergyAdapter(CommunicationEnergyAdapter):
    """Electrical energy of one or more DESERT nodes' modems from observed PHY events.

    Parameters
    ----------
    interfaces:
        ``{medium or "medium#interface_index": ModemPowerProfile | mapping}``.
    node:
        node name (``node_id``) or numeric DESERT node of the vehicle whose battery
        is charged; ``None`` tracks every node (fleet accounting, no battery coupling).
    rx_outcomes:
        reception outcomes counted as RX (demodulation) time; other receptions keep
        the idle/listen state.
    include_control:
        count MAC control frames (ACK/RTS/CTS...) - they are real transmissions.
    node_map:
        optional ``{numeric node: node_id}`` (``Scenario.node_map``) for raw events.
    """

    def __init__(
        self,
        interfaces,
        *,
        node=None,
        rx_outcomes=DEFAULT_RX_OUTCOMES,
        include_control=True,
        node_map=None,
        name="comms",
        start_time_s=0.0,
        time_offset_s=0.0,
        communication_backend=None,
    ):
        self.interface_profiles = {
            k: v if isinstance(v, ModemPowerProfile) else ModemPowerProfile.from_mapping(v)
            for k, v in interfaces.items()
        }
        self.node = node
        self.node_map = {int(k): v for k, v in (node_map or {}).items()}
        self.rx_outcomes = frozenset(rx_outcomes)
        self.include_control = bool(include_control)
        self.start_time_s = start_time_s
        super().__init__(
            {"_placeholder": next(iter(self.interface_profiles.values()))},
            name=name,
            start_time_s=start_time_s,
            time_offset_s=time_offset_s,
        )
        self.ledgers.clear()
        self._consumed.clear()
        self.events_seen = 0
        self.event_counts = Counter()
        self.outcomes = Counter()
        self.unknown_interfaces = Counter()
        self.deliveries = []
        self.generated = []
        self.forwards = Counter()
        self.packet_tx = defaultdict(int)
        self.last_stats = {}
        self.last_time = 0.0
        self.backend = communication_backend

    # -- identity ----------------------------------------------------------------------
    def _node_name(self, event):
        if "node_id" in event and event["node_id"] is not None:
            return str(event["node_id"])
        node = event.get("node")
        if node is None:
            return None
        return str(self.node_map.get(int(node), node))

    def _tracked(self, name):
        return self.node is None or name == str(self.node)

    def _profile_key(self, event):
        medium = medium_of(event)
        index = event.get("interface_index")
        specific = f"{medium}#{index}"
        if specific in self.interface_profiles:
            return specific
        if medium in self.interface_profiles:
            return medium
        return None

    def _ledger_key(self, node, profile_key):
        return profile_key if self.node is not None else f"{node}/{profile_key}"

    # -- observation -------------------------------------------------------------------
    def observe(self, events):
        """Record a batch of holo_desert events; returns the same list unchanged."""
        from .communications import InterfaceLedger

        for event in events or ():
            if not isinstance(event, dict):
                continue
            self.events_seen += 1
            kind = event.get("event")
            self.event_counts[kind] += 1
            time = event.get("time")
            if isinstance(time, (int, float)):
                self.last_time = max(self.last_time, float(time))
            node = self._node_name(event)
            if kind == "delivered":
                self.deliveries.append(
                    {
                        k: event.get(k)
                        for k in ("packet_id", "size", "delay", "source", "destination", "time")
                    }
                )
                continue
            if kind == "generated":
                self.generated.append(
                    {
                        k: event.get(k)
                        for k in ("packet_id", "size", "source", "destination", "time")
                    }
                )
                continue
            if kind == "forward" and node is not None:
                self.forwards[node] += 1
                continue
            if kind == "stats" and node is not None:
                self.last_stats[node] = {k: v for k, v in event.items() if k not in ("event",)}
                continue
            if kind not in PHY_EVENTS or node is None or not self._tracked(node):
                continue
            state, control = PHY_EVENTS[kind]
            if control and not self.include_control:
                continue
            key = self._profile_key(event)
            if key is None:
                self.unknown_interfaces[(medium_of(event), event.get("interface_index"))] += 1
                continue
            duration = event.get("duration_s")
            if not isinstance(duration, (int, float)) or duration < 0 or time is None:
                raise ConfigurationError(f"PHY event without valid time/duration_s: {event}")
            ledger_key = self._ledger_key(node, key)
            if ledger_key not in self.ledgers:
                self.ledgers[ledger_key] = InterfaceLedger(
                    self.interface_profiles[key], self.start_time_s
                )
                self._consumed[ledger_key] = {}
            ledger = self.ledgers[ledger_key]
            bits = event.get("phy_bits")
            if state == "TX":
                ledger.add_tx(time, duration, bits)
                if event.get("packet_id") is not None and not control:
                    self.packet_tx[(node, event["packet_id"])] += 1
            else:
                outcome = event.get("outcome")
                self.outcomes[(medium_of(event), outcome)] += 1
                if outcome in self.rx_outcomes:
                    ledger.add_rx(time, duration, bits)
        return events

    def ensure_interfaces(self, keys):
        """Create ledgers for interfaces that may stay silent (idle energy still accrues)."""
        from .communications import InterfaceLedger

        for key in keys:
            if key not in self.interface_profiles:
                raise ConfigurationError(f"Unknown interface profile {key}")
            ledger_key = key if self.node is not None else None
            if ledger_key is None:
                raise ConfigurationError("ensure_interfaces requires a single tracked node")
            if ledger_key not in self.ledgers:
                self.ledgers[ledger_key] = InterfaceLedger(
                    self.interface_profiles[key], self.start_time_s
                )
                self._consumed[ledger_key] = {}

    @classmethod
    def from_events_file(cls, path, interfaces, **kwargs):
        adapter = cls(interfaces, **kwargs)
        with Path(path).open(encoding="utf-8") as handle:
            adapter.observe(json.loads(line) for line in handle if line.strip())
        return adapter

    def observed(self, target):
        """Wrap a NetworkSession/HoloOceanLink so returned events are also observed."""
        return ObservingProxy(target, self)

    # -- metrics -----------------------------------------------------------------------
    def network_metrics(self, t_end=None):
        t_end = self.last_time if t_end is None else t_end
        energy = self.summary(t_end)
        total_Wh = sum(item["energy_Wh"] for item in energy.values())

        def involves(item):
            return self.node is None or str(self.node) in (
                str(item.get("source")),
                str(item.get("destination")),
            )

        delivered = [d for d in self.deliveries if involves(d)]
        generated = [g for g in self.generated if involves(g)]
        delivered_bytes = sum(int(d.get("size") or 0) for d in delivered)
        delays = [float(d["delay"]) for d in delivered if isinstance(d.get("delay"), (int, float))]
        retries = sum(n - 1 for n in self.packet_tx.values() if n > 1) if self.packet_tx else None
        return {
            "observed_events": self.events_seen,
            "event_counts": dict(self.event_counts),
            "rx_outcomes": {f"{m}:{o}": n for (m, o), n in self.outcomes.items()},
            "unmapped_interfaces": {f"{m}#{i}": n for (m, i), n in self.unknown_interfaces.items()},
            "generated_messages": len(generated),
            "deliveries": len(delivered),
            "delivery_ratio": len(delivered) / len(generated) if generated else None,
            "mean_latency_s": sum(delays) / len(delays) if delays else None,
            "delivered_bytes": delivered_bytes,
            "delivery_source": "host 'generated'/'delivered' events (events.jsonl); absent in raw step() events",
            "forwards": dict(self.forwards),
            "retransmissions": retries,
            "retransmissions_basis": None
            if retries is None
            else "repeated data phy_tx_start with the same host packet_id at one node",
            "communication_energy_Wh": total_Wh,
            "energy_per_delivered_byte_J": (total_Wh * 3600 / delivered_bytes)
            if delivered_bytes
            else None,
            "energy_per_delivered_message_J": (total_Wh * 3600 / len(delivered))
            if delivered
            else None,
            "scope": "tracked node" if self.node is not None else "all observed nodes",
            "interfaces": energy,
            "last_stats": self.last_stats,
        }


class ObservingProxy:
    """Transparent proxy: forwards every call unchanged and observes returned events."""

    _OBSERVED = ("step", "run_until", "sync")

    def __init__(self, target, adapter):
        object.__setattr__(self, "_target", target)
        object.__setattr__(self, "_adapter", adapter)

    def __getattr__(self, name):
        value = getattr(self._target, name)
        if name in self._OBSERVED and callable(value):

            def wrapper(*args, **kwargs):
                result = value(*args, **kwargs)
                if isinstance(result, list):
                    self._adapter.observe(result)
                return result

            return wrapper
        return value

    def __setattr__(self, name, value):
        setattr(self._target, name, value)
