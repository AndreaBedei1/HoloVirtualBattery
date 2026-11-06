"""Event-driven communication energy: E_comm = integral of P_state(t) dt.

The communication simulator owns communication behaviour; this module only observes
its events.  For each modem interface it reconstructs half-duplex state intervals:

* ``TX``  - transmissions (data, ACK/control, forwarded frames), from start time and
  duration reported by the network simulator;
* ``RX``  - receptions/demodulation intervals that the policy counts as receive time;
* idle   - every remaining instant, charged at the profile's idle state (``LISTEN`` by
  default, or ``SLEEP`` when the user declares a sleeping modem).

TX has priority over RX in overlaps (a half-duplex modem cannot receive while it
transmits).  Overlapping receptions are merged, so overhearing several frames at once
is not double counted.  Payload size, bitrate, retries, routing, MAC overhead and PHY
selection affect energy only through the intervals the simulator actually produced.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field

from .._validation import ConfigurationError, number

STATES = ("TX", "RX", "LISTEN", "IDLE", "SLEEP", "OFF")


@dataclass
class ModemPowerProfile:
    """Electrical input power (W) per state of one communication interface."""

    name: str
    powers_W: dict
    idle_state: str = "LISTEN"
    evidence: dict = field(default_factory=dict)
    grades: dict = field(default_factory=dict)
    medium: str | None = None
    notes: str | None = None

    def __post_init__(self):
        clean = {}
        for state, value in self.powers_W.items():
            if state not in STATES:
                raise ConfigurationError(f"{self.name}: unknown modem state {state}")
            clean[state] = (
                None if value is None else number(value, f"{self.name}.{state}", minimum=0)
            )
        self.powers_W = clean
        if self.idle_state not in clean:
            raise ConfigurationError(
                f"{self.name}: idle state {self.idle_state} has no power entry"
            )

    def power(self, state):
        value = self.powers_W.get(state)
        if value is None:
            raise ConfigurationError(
                f"{self.name}: state {state} is unconfigured (no defensible electrical power)"
            )
        return value

    @property
    def configured(self):
        needed = {"TX", "RX", self.idle_state}
        return all(self.powers_W.get(s) is not None for s in needed)

    @classmethod
    def from_mapping(cls, data, registry=None):
        """Mapping with ``states: {TX: {evidence: id} | number | null, ...}``."""
        from ..evidence import RELATION_MAX_GRADE, cap_grade

        relation = data.get("relation", "exact")
        if relation not in RELATION_MAX_GRADE:
            raise ConfigurationError(f"Unknown modem profile relation {relation}")
        states = data.get("states", {})
        powers, evidence, grades = {}, {}, {}
        for state, value in states.items():
            if isinstance(value, dict) and "evidence" in value:
                if registry is None:
                    from ..evidence import default_registry

                    registry = default_registry()
                record = registry.get(value["evidence"])
                evidence[state] = record.id
                grades[state] = cap_grade(record.grade, relation) if record.configured else "D"
                use = value.get("use", "value")
                if use not in ("value", "value_min", "value_max"):
                    raise ConfigurationError(f"{record.id}: use must be value/value_min/value_max")
                if not record.configured:
                    powers[state] = None
                elif getattr(record, use) is not None:
                    powers[state] = record.si(use)
                else:
                    raise ConfigurationError(f"{record.id}: no {use}; set 'use' explicitly")
            else:
                powers[state] = value
                grades[state] = "D"
        return cls(
            data.get("name", "modem"),
            powers,
            data.get("idle_state", "LISTEN"),
            evidence,
            grades,
            data.get("medium"),
            data.get("notes"),
        )


def _merge(intervals):
    result = []
    for a, b in sorted(intervals):
        if b <= a:
            continue
        if result and a <= result[-1][1]:
            result[-1][1] = max(result[-1][1], b)
        else:
            result.append([a, b])
    return [tuple(x) for x in result]


def _subtract(intervals, cut):
    """intervals minus cut (both merged, sorted)."""
    out, j = [], 0
    for a, b in intervals:
        start = a
        while j < len(cut) and cut[j][1] <= start:
            j += 1
        k = j
        while k < len(cut) and cut[k][0] < b:
            if cut[k][0] > start:
                out.append((start, cut[k][0]))
            start = max(start, cut[k][1])
            k += 1
        if start < b:
            out.append((start, b))
    return out


class _Timeline:
    """Merged intervals with prefix sums for O(log n) occupancy queries."""

    def __init__(self, intervals):
        self.intervals = intervals
        self.starts = [a for a, _ in intervals]
        self.prefix = [0.0]
        for a, b in intervals:
            self.prefix.append(self.prefix[-1] + (b - a))

    def occupied(self, t):
        """Total occupied time in [-inf, t]."""
        i = bisect_right(self.starts, t)
        if i == 0:
            return 0.0
        a, b = self.intervals[i - 1]
        return self.prefix[i - 1] + (min(t, b) - a)


class InterfaceLedger:
    """TX/RX intervals of one interface and their energy integral."""

    def __init__(self, profile, start_time_s=0.0):
        self.profile = profile
        self.start = float(start_time_s)
        self.tx, self.rx = [], []
        self.counts = {"tx_frames": 0, "tx_bits": 0, "rx_frames": 0, "rx_bits": 0}
        self._dirty = True
        self._tx_tl = self._rx_tl = None

    def add_tx(self, t0, duration, bits=None):
        self.tx.append((float(t0), float(t0) + float(duration)))
        self.counts["tx_frames"] += 1
        self.counts["tx_bits"] += int(bits or 0)
        self._dirty = True

    def add_rx(self, t0, duration, bits=None):
        self.rx.append((float(t0), float(t0) + float(duration)))
        self.counts["rx_frames"] += 1
        self.counts["rx_bits"] += int(bits or 0)
        self._dirty = True

    def _refresh(self):
        if self._dirty:
            tx = _merge(self.tx)
            rx = _subtract(_merge(self.rx), tx)
            self._tx_tl, self._rx_tl = _Timeline(tx), _Timeline(rx)
            self._dirty = False

    def durations(self, t):
        """State durations (s) in [start, t]."""
        self._refresh()
        span = max(0.0, t - self.start)
        tx = self._tx_tl.occupied(t) - self._tx_tl.occupied(self.start)
        rx = self._rx_tl.occupied(t) - self._rx_tl.occupied(self.start)
        return {"TX": tx, "RX": rx, self.profile.idle_state: max(0.0, span - tx - rx)}

    def energy_J(self, t):
        return {s: d * self.profile.power(s) for s, d in self.durations(t).items()}


class CommunicationEnergyAdapter:
    """Generic observer: feed normalized activity, query energy for time windows.

    It implements the HoloEnergy *load source* protocol used by
    :meth:`holoenergy.EnergyAwareEnv.attach`: ``consume(t_end)`` returns the energy
    (J) per device and state accrued since the previous call, including late-arriving
    activity (late events are charged in the window in which they become known; the
    cumulative energy is exact).
    """

    category = "communications"

    def __init__(self, interfaces, *, name="communications", start_time_s=0.0, time_offset_s=0.0):
        if not interfaces:
            raise ConfigurationError("At least one communication interface profile is required")
        self.name = name
        self.time_offset_s = number(time_offset_s, "time_offset_s")
        self.ledgers = {}
        for key, profile in interfaces.items():
            if not isinstance(profile, ModemPowerProfile):
                profile = ModemPowerProfile.from_mapping(profile)
            self.ledgers[str(key)] = InterfaceLedger(profile, start_time_s)
        self._consumed = {k: {} for k in self.ledgers}
        self.unmatched = 0

    def device_name(self, key):
        return f"{self.name}.{key}"

    def ledger(self, key):
        try:
            return self.ledgers[str(key)]
        except KeyError as exc:
            raise ConfigurationError(f"No modem profile for interface {key}") from exc

    def energy_J(self, t_end):
        """Cumulative energy per device and state up to simulator time t_end."""
        t = t_end + self.time_offset_s
        return {self.device_name(k): led.energy_J(t) for k, led in self.ledgers.items()}

    def consume(self, t_end):
        total = self.energy_J(t_end)
        delta = {}
        for k in self.ledgers:
            device = self.device_name(k)
            prev = self._consumed[k]
            delta[device] = {s: e - prev.get(s, 0.0) for s, e in total[device].items()}
            self._consumed[k] = total[device]
        return delta

    def reset(self):
        self._consumed = {k: {} for k in self.ledgers}

    def grades(self):
        return {self.device_name(k): dict(led.profile.grades) for k, led in self.ledgers.items()}

    def summary(self, t_end):
        t = t_end + self.time_offset_s
        result = {}
        for key, led in self.ledgers.items():
            durations = led.durations(t)
            energy = led.energy_J(t)
            result[self.device_name(key)] = {
                "profile": led.profile.name,
                "medium": led.profile.medium,
                "state_duration_s": durations,
                "state_energy_Wh": {s: e / 3600 for s, e in energy.items()},
                "energy_Wh": sum(energy.values()) / 3600,
                **led.counts,
                "evidence": dict(led.profile.evidence),
                "grades": dict(led.profile.grades),
            }
        return result
