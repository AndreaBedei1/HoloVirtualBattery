"""Typed builder for the energy profile of an arbitrary marine robot.

The builder only assembles the public configuration mapping (``to_config()``); every value is
validated by the same loader and model constructors as a YAML configuration, so there is no
second model path. Nothing here assumes a particular vehicle: actuators, geometry, battery,
loads, converters and the user's own evidence are all explicit.

    robot = RobotEnergyProfile(name="my-rov", battery=BatteryProfile(...),
                               thrusters=[ThrusterProfile(...), ...], components=[...],
                               sources=[EvidenceSourceSpec(...)], records=[EvidenceRecordSpec(...)])
    env = EnergyAwareEnv(holoocean_env=env, energy_profile=robot, control_contract=...)

A named component or thruster from the packaged library is selected with ``catalog=`` (for
example ``SensorProfile(name="sonar", catalog="tritech-gemini-720is")``); it carries its own
evidence and does not depend on any vehicle profile.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ._validation import ConfigurationError

SOURCE_KINDS = {
    "paper": "journal_article",
    "conference": "conference_paper",
    "thesis": "thesis",
    "datasheet": "manufacturer_datasheet",
    "manufacturer_dataset": "manufacturer_dataset",
    "dataset": "dataset",
    "measurement": "user",
    "assumption": "user",
    "simulator": "simulator_source",
    "standard": "standard",
}


@dataclass(frozen=True)
class EvidenceSourceSpec:
    """A paper, datasheet, dataset, own measurement or engineering assumption."""

    id: str
    kind: str
    title: str
    doi: str | None = None
    url: str | None = None
    authors: tuple = ()
    year: int | None = None
    local_file: str | None = None
    sha256: str | None = None
    notes: str | None = None

    def to_mapping(self):
        if self.kind not in SOURCE_KINDS:
            raise ConfigurationError(
                f"source {self.id}: kind must be one of {sorted(SOURCE_KINDS)}"
            )
        mapping = {"id": self.id, "type": SOURCE_KINDS[self.kind], "title": self.title}
        for key in ("doi", "url", "year", "local_file", "sha256"):
            if getattr(self, key) is not None:
                mapping[key] = getattr(self, key)
        if self.authors:
            mapping["authors"] = list(self.authors)
        notes = self.notes or (
            f"{self.kind} supplied by the user"
            if self.kind in ("measurement", "assumption")
            else None
        )
        if notes:
            mapping["notes"] = notes
        return mapping


@dataclass(frozen=True)
class EvidenceRecordSpec:
    """One parameter value (or range, or dataset) with its provenance; validated like a
    packaged record (grade capped by relation, units, cited sources)."""

    id: str
    component: str
    quantity: str
    unit: str | None
    value: float | None = None
    value_min: float | None = None
    value_max: float | None = None
    bound: str = "unknown"
    relation: str = "user"
    grade: str = "D"
    sources: tuple = ()
    location: dict = field(default_factory=dict)
    conditions: dict = field(default_factory=dict)
    derivation: str | None = None
    dataset: str | None = None
    notes: str | None = None

    def to_mapping(self):
        mapping = {
            "id": self.id,
            "component": self.component,
            "quantity": self.quantity,
            "unit": self.unit,
            "bound": self.bound,
            "relation": self.relation,
            "grade": self.grade,
            "sources": list(self.sources),
        }
        for key in ("value", "value_min", "value_max", "derivation", "notes"):
            if getattr(self, key) is not None:
                mapping[key] = getattr(self, key)
        for key in ("location", "conditions"):
            if getattr(self, key):
                mapping[key] = dict(getattr(self, key))
        if self.dataset is not None:
            mapping["dataset"] = {"path": str(Path(self.dataset).resolve())}
        return mapping


@dataclass(frozen=True)
class Ref:
    """Link to an evidence record; ``use`` selects value, value_min or value_max."""

    record: str
    use: str = "value"
    relation: str = "exact"


@dataclass(frozen=True)
class State:
    """A power state: a power, a current at a supply voltage, or an evidence reference."""

    name: str
    power_W: float | None = None
    current_A: float | None = None
    at_V: float | None = None
    evidence: Ref | None = None

    def to_entry(self):
        given = [self.power_W is not None, self.current_A is not None, self.evidence is not None]
        if sum(given) > 1:
            raise ConfigurationError(
                f"state {self.name}: give one of power_W, current_A or evidence"
            )
        if self.evidence is not None:
            return {"evidence": self.evidence.record, "use": self.evidence.use}
        if self.current_A is not None:
            if self.at_V is None:
                raise ConfigurationError(f"state {self.name}: current_A needs at_V")
            # A constant-power load at that supply voltage (user value, graded D).
            return {"power_W": float(self.current_A) * float(self.at_V)}
        if self.power_W is not None:
            return {"power_W": float(self.power_W)}
        return None  # unknown: the component must be declared unconfigured


@dataclass(frozen=True)
class ComponentProfile:
    name: str
    states: tuple = ()
    initial_state: str | None = None
    category: str = "sensors"
    catalog: str | None = None
    supply_V: tuple | None = None
    relation: str = "exact"
    device: str | None = None
    includes: tuple = ()
    simulation_sensor: str | None = None
    status: str = "configured"
    notes: str | None = None

    def to_entry(self):
        if self.catalog is not None:
            from .catalog import profile_reference

            if self.states:
                raise ConfigurationError(f"{self.name}: a catalog component brings its own states")
            entry = {"profile": profile_reference(self.catalog, "component"), "name": self.name}
            if self.initial_state:
                entry["initial_state"] = self.initial_state
            # Explicit overrides of the library profile (defaults are not written).
            if self.supply_V is not None:
                entry["supply_V"] = list(self.supply_V)
            if self.relation != "exact":
                entry["relation"] = self.relation
            return entry
        entry = {"name": self.name, "category": self.category, "relation": self.relation}
        states = {s.name: s.to_entry() for s in self.states}
        if states:
            entry["states"] = states
        for key in ("initial_state", "device", "simulation_sensor", "notes"):
            if getattr(self, key) is not None:
                entry[key] = getattr(self, key)
        if self.status != "configured" or any(v is None for v in states.values()):
            entry["status"] = "unconfigured"
        if self.supply_V is not None:
            entry["supply_V"] = list(self.supply_V)
        if self.includes:
            entry["includes"] = list(self.includes)
        return entry


@dataclass(frozen=True)
class SensorProfile(ComponentProfile):
    category: str = "sensors"


@dataclass(frozen=True)
class ComputeProfile(ComponentProfile):
    category: str = "compute"


@dataclass(frozen=True)
class CommunicationProfile(ComponentProfile):
    category: str = "communications"


@dataclass(frozen=True)
class AuxiliaryProfile(ComponentProfile):
    category: str = "auxiliaries"


@dataclass(frozen=True)
class ConverterProfile:
    """A DC/DC converter feeding ``serves`` from the bus. Its own consumption is a component
    state; an efficiency with evidence applies to the payload rail (one rail is modelled)."""

    name: str
    serves: tuple
    input_V: tuple
    quiescent: State | None = None
    efficiency: float | None = None
    efficiency_evidence: str | None = None

    def to_entry(self):
        entry = {
            "name": self.name,
            "category": "auxiliaries",
            "supply_V": list(self.input_V),
            "serves": list(self.serves),
        }
        if self.quiescent is not None and self.quiescent.to_entry() is not None:
            entry["states"] = {"ACTIVE": self.quiescent.to_entry()}
            entry["initial_state"] = "ACTIVE"
        else:
            entry["status"] = "unconfigured"
            entry["notes"] = "converter consumption not configured"
        return entry


@dataclass(frozen=True)
class ThrusterProfile:
    """One actuator: a packaged model (``catalog``) or the user's own voltage tables."""

    id: str
    position_m: tuple
    direction: tuple
    catalog: str | None = None
    model: str | None = None
    voltage_tables: tuple = ()
    voltage_policy: str = "measured"
    evidence: Ref | None = None

    def to_entry(self):
        entry = {
            "id": self.id,
            "position_m": list(self.position_m),
            "direction": list(self.direction),
        }
        if self.catalog is not None:
            from .catalog import profile_reference

            entry["profile"] = profile_reference(self.catalog, "actuator")
        else:
            if not self.model or not self.voltage_tables:
                raise ConfigurationError(f"thruster {self.id}: give catalog= or model= with tables")
            entry["model"] = self.model
            entry["voltage_tables"] = copy.deepcopy(list(self.voltage_tables))
        if self.voltage_policy != "measured":
            entry["voltage_policy"] = self.voltage_policy
        return entry


@dataclass(frozen=True)
class BatteryProfile:
    nominal_voltage_V: float
    capacity_Ah: float
    model: str = "rint"
    initial_soc: float = 1.0
    max_current_A: float | None = None
    internal_resistance_ohm: float | None = None
    cutoff_voltage_V: float | None = None
    ocv_curve: tuple | None = None
    losses: Ref | None = None
    evidence: dict = field(default_factory=dict)

    def to_section(self):
        section = {
            "model": self.model,
            "capacity_Ah": self.capacity_Ah,
            "nominal_voltage_V": self.nominal_voltage_V,
            "initial_soc": self.initial_soc,
        }
        for key in ("max_current_A", "internal_resistance_ohm", "cutoff_voltage_V"):
            if getattr(self, key) is not None:
                section[key] = getattr(self, key)
        if self.ocv_curve is not None:
            section["ocv_curve"] = [list(p) for p in self.ocv_curve]
        if self.evidence:
            section["metadata"] = {"evidence": dict(self.evidence)}
        return section


@dataclass(frozen=True)
class RobotEnergyProfile:
    """Everything HoloEnergy needs about a robot's energy system, independent of any
    built-in vehicle. ``thermal`` is a mapping of measured values or ``"isothermal"``."""

    name: str
    battery: BatteryProfile
    thrusters: tuple
    dt_s: float
    components: tuple = ()
    converters: tuple = ()
    sources: tuple = ()
    records: tuple = ()
    water_temperature_C: float | None = None
    thermal: object = "isothermal"
    action_mode: str = "wrench"
    allocation: str = "redistributed"
    backend: dict | None = None
    propulsion_evidence: Ref | None = None
    hotel_W: float = 0.0
    allow_placeholders: bool = False

    def _evidence(self):
        evidence = {}
        links = {t.id: t.evidence for t in self.thrusters if t.evidence is not None}
        if self.propulsion_evidence is not None:
            evidence["propulsion"] = {
                "record": self.propulsion_evidence.record,
                "relation": self.propulsion_evidence.relation,
            }
        if links:
            evidence["actuators"] = {
                k: {"record": v.record, "relation": v.relation} for k, v in links.items()
            }
        if self.battery.losses is not None:
            evidence["battery_losses"] = {
                "record": self.battery.losses.record,
                "relation": self.battery.losses.relation,
            }
        if self.sources:
            evidence["sources"] = [s.to_mapping() for s in self.sources]
        if self.records:
            evidence["records"] = [r.to_mapping() for r in self.records]
        return evidence

    def _converters(self):
        efficiencies = {c.efficiency for c in self.converters if c.efficiency is not None}
        if len(efficiencies) > 1:
            raise ConfigurationError(
                "one payload rail is modelled: converters must share an efficiency"
            )
        if not efficiencies:
            return {}
        conv = next(c for c in self.converters if c.efficiency is not None)
        section = {"payload_efficiency": conv.efficiency}
        if conv.efficiency_evidence:
            section["metadata"] = {"evidence": {"payload_efficiency": conv.efficiency_evidence}}
        return section

    def to_config(self):
        if self.water_temperature_C is None:
            raise ConfigurationError("water_temperature_C is required (measured or explicit)")
        thermal = (
            {"model": "isothermal", "initial_temperature_C": self.water_temperature_C}
            if self.thermal == "isothermal"
            else dict(self.thermal)
        )
        backend = self.backend or {
            "mapping": "direct",
            "backend_index": list(range(len(self.thrusters))),
        }
        config = {
            "allow_placeholders": self.allow_placeholders,
            "vehicle": {"name": self.name},
            "simulation": {"dt_s": self.dt_s},
            "environment": {"water_temperature_C": self.water_temperature_C},
            "battery": self.battery.to_section(),
            "thermal": thermal,
            "actuators": [t.to_entry() for t in self.thrusters],
            "actuation": {
                "action_mode": self.action_mode,
                "allocation": {"method": self.allocation},
                "backend": copy.deepcopy(backend),
            },
            "components": [c.to_entry() for c in self.components]
            + [c.to_entry() for c in self.converters],
            "hotel_load": {"constant_W": self.hotel_W},
        }
        converters = self._converters()
        if converters:
            config["converters"] = converters
        evidence = self._evidence()
        if evidence:
            config["evidence"] = evidence
        return config

    def to_yaml(self, path):
        path = Path(path)
        path.write_text(yaml.safe_dump(self.to_config(), sort_keys=False), encoding="utf-8")
        return path

    def validate(self):
        """Dry run with an energy-only backend: returns the scientific warnings."""
        from . import EnergyAwareEnv

        class _Null:
            def step(self, action):
                return {}

            def close(self):
                pass

        contract = {
            "agent_type": "builder_validation",
            "control_scheme": 0,
            "action_units": "force_N",
            "thruster_count": len(self.thrusters),
            "dt_s": self.dt_s,
        }
        with EnergyAwareEnv(_Null(), energy_profile=self, control_contract=contract) as env:
            env.step([0.0] * (6 if self.action_mode == "wrench" else len(self.thrusters)))
            return env.energy.summary()["evidence"]["scientific_warnings"]
