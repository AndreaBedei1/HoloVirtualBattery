"""Named supply rails between the pack and the loads (review R3-02).

A rail is either ``direct`` (the load sits on the pack bus: no converter, so no conversion loss)
or ``converter`` (a DC/DC stage with an output voltage and an efficiency eta = Pout / Pin).
A converter efficiency is never assumed: when it is unknown the model charges the rail at
eta = 1, which is the lower bound of its bus-side energy, and the evidence layer reports the
rail as unverified (open upper side). Components choose a rail with ``rail: <name>``; components
without one stay on the legacy ``payload`` rail, whose efficiency is
``converters.payload_efficiency``.
"""

from __future__ import annotations

from dataclasses import dataclass

from .._validation import ConfigurationError, keys, number

LEGACY_RAIL = "payload"
RAIL_KEYS = {
    "name",
    "kind",
    "output_V",
    "efficiency",
    "efficiency_evidence",
    "relation",
    "notes",
}


@dataclass(frozen=True)
class Rail:
    name: str
    kind: str
    output_V: float | None = None
    efficiency: float | None = None
    efficiency_evidence: str | None = None
    relation: str = "exact"
    notes: str | None = None

    @property
    def model_efficiency(self):
        """Efficiency used by the model: exact 1 for a direct rail, 1 (lower bound) if unknown."""
        if self.kind == "direct" or self.efficiency is None:
            return 1.0
        return self.efficiency

    @classmethod
    def from_mapping(cls, item):
        if not isinstance(item, dict):
            raise ConfigurationError("each rails entry must be a mapping")
        keys(item, RAIL_KEYS, "rail")
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError("rail.name must be a nonempty string")
        if name in (LEGACY_RAIL, "hotel", "propulsion"):
            raise ConfigurationError(
                f"rail name {name!r} is reserved; the legacy payload rail is configured by "
                "converters.payload_efficiency"
            )
        kind = item.get("kind", "converter")
        if kind not in ("direct", "converter"):
            raise ConfigurationError(f"rail {name}: kind must be direct or converter")
        output = item.get("output_V")
        efficiency = item.get("efficiency")
        if kind == "direct":
            if output is not None or efficiency is not None:
                raise ConfigurationError(
                    f"rail {name}: a direct rail has the pack voltage and no converter; "
                    "remove output_V and efficiency"
                )
        else:
            if output is None:
                raise ConfigurationError(f"rail {name}: a converter rail needs output_V (V)")
            output = number(output, f"rail {name}.output_V", positive=True)
            if efficiency is not None:
                efficiency = number(efficiency, f"rail {name}.efficiency", positive=True, maximum=1)
        evidence = item.get("efficiency_evidence")
        if evidence is not None and (not isinstance(evidence, str) or not evidence):
            raise ConfigurationError(f"rail {name}.efficiency_evidence must be a record id")
        if evidence is not None and efficiency is None:
            raise ConfigurationError(
                f"rail {name}: efficiency_evidence given without the efficiency it supports"
            )
        relation = item.get("relation", "exact")
        from ..evidence import RELATION_MAX_GRADE

        if relation not in RELATION_MAX_GRADE:
            raise ConfigurationError(f"rail {name}: unknown relation {relation}")
        return cls(name, kind, output, efficiency, evidence, relation, item.get("notes"))

    def to_mapping(self):
        out = {"name": self.name, "kind": self.kind}
        if self.kind == "converter":
            out["output_V"] = self.output_V
            out["efficiency"] = self.efficiency
            if self.efficiency_evidence:
                out["efficiency_evidence"] = self.efficiency_evidence
        if self.relation != "exact":
            out["relation"] = self.relation
        if self.notes:
            out["notes"] = self.notes
        return out


class RailSet:
    """The configured rails plus the legacy payload rail; maps components to rails."""

    def __init__(self, rails_config, legacy_efficiency, components):
        if rails_config is None:
            rails_config = []
        if not isinstance(rails_config, list):
            raise ConfigurationError("rails must be a list of rail mappings")
        self.legacy_efficiency = float(legacy_efficiency)
        self.rails = {}
        for item in rails_config:
            rail = Rail.from_mapping(item)
            if rail.name in self.rails:
                raise ConfigurationError(f"duplicate rail {rail.name!r}")
            self.rails[rail.name] = rail
        self.assignment = {}
        for name, component in components.items():
            rail = getattr(component, "rail", None)
            if rail is None:
                self.assignment[name] = LEGACY_RAIL
                continue
            if rail not in self.rails:
                raise ConfigurationError(
                    f"component {name} is on rail {rail!r}, which is not configured; "
                    f"configured rails: {sorted(self.rails) or 'none'}"
                )
            self.assignment[name] = rail

    def rail_of(self, component):
        return self.assignment.get(component, LEGACY_RAIL)

    def efficiency(self, rail):
        if rail == LEGACY_RAIL:
            return self.legacy_efficiency
        return self.rails[rail].model_efficiency

    def bus_power_W(self, powers_W, external_W=0.0):
        """Bus-side power of component loads; external loads stay on the legacy rail."""
        total = sum(power / self.efficiency(self.rail_of(name)) for name, power in powers_W.items())
        return total + external_W / self.legacy_efficiency

    def mix_efficiency(self, powers_W, external_W=0.0):
        """Single efficiency with sum(P) / eta_mix == sum(P_i / eta_rail(i)) for this tick."""
        load = sum(powers_W.values()) + external_W
        if load <= 0:
            return self.legacy_efficiency
        return load / self.bus_power_W(powers_W, external_W)

    @property
    def is_trivial(self):
        """True when no component uses a named rail (legacy single payload rail)."""
        return all(rail == LEGACY_RAIL for rail in self.assignment.values())
