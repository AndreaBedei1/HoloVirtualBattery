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


RELATION_ORDER = ("exact", "representative", "proxy", "user", "unsupported")


def _strictest(relations):
    return max(relations, key=lambda r: RELATION_ORDER.index(r) if r in RELATION_ORDER else 0)


def _plain(value):
    """Plain Python scalars and containers (numpy values are not YAML-safe; M7)."""
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if hasattr(value, "item") and callable(value.item):
        return value.item()
    return value


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
    rail: str | None = None

    def to_entry(self):
        entry = self._entry()
        if self.rail is not None:
            entry["rail"] = self.rail
        return entry

    def _entry(self):
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
        # The strictest relation among the component and its evidence references (H8).
        refs = [s.evidence.relation for s in self.states if s.evidence is not None]
        entry = {
            "name": self.name,
            "category": self.category,
            "relation": _strictest([self.relation, *refs]),
        }
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
class RailProfile:
    """A named supply rail: ``direct`` (pack bus, no converter) or ``converter`` with an
    output voltage and, only when evidence exists, an efficiency (``holoenergy.models.rails``)."""

    name: str
    kind: str = "converter"
    output_V: float | None = None
    efficiency: float | None = None
    efficiency_evidence: str | None = None
    relation: str = "exact"
    notes: str | None = None

    def to_mapping(self):
        out = {"name": self.name, "kind": self.kind}
        for key in ("output_V", "efficiency", "efficiency_evidence", "notes"):
            if getattr(self, key) is not None:
                out[key] = getattr(self, key)
        if self.relation != "exact":
            out["relation"] = self.relation
        return out


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
        if self.name in self.serves:
            raise ConfigurationError(f"converter {self.name} cannot serve itself")
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
            "nominal_voltage_V": self.nominal_voltage_V,
            "initial_soc": self.initial_soc,
        }
        if self.model == "energy_bucket":
            # L0 takes energy; capacity_Ah x nominal voltage is the rated energy (M5).
            section["capacity_Wh"] = self.capacity_Ah * self.nominal_voltage_V
        else:
            section["capacity_Ah"] = self.capacity_Ah
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
    rails: tuple = ()
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
        if isinstance(self.thermal, str):
            if self.thermal != "isothermal":
                raise ConfigurationError(
                    'thermal must be "isothermal" or a mapping of measured values'
                )
            thermal = {"model": "isothermal", "initial_temperature_C": self.water_temperature_C}
        else:
            thermal = dict(self.thermal)
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
        if self.rails:
            config["rails"] = [r.to_mapping() for r in self.rails]
        evidence = self._evidence()
        if evidence:
            config["evidence"] = evidence
        return config

    def to_yaml(self, path):
        path = Path(path)
        path.write_text(yaml.safe_dump(_plain(self.to_config()), sort_keys=False), encoding="utf-8")
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
            # Every actuator must be evaluable at full thrust over the whole bus voltage range
            # (a zero action alone would not reach the voltage domain; M4).
            low, high = env.evidence_map.bus_voltage_range
            for aid, model in zip(env.propulsion.ids, env.propulsion.thrusters, strict=True):
                for v in {low, high} - {None}:
                    try:
                        model.power(model.max_force(v, "forward"), v)
                    except ValueError as exc:
                        raise ConfigurationError(f"actuator {aid} at {v:g} V: {exc}") from exc
            env.step([0.0] * (6 if self.action_mode == "wrench" else len(self.thrusters)))
            return env.energy.summary()["evidence"]["scientific_warnings"]


# Grade a user-supplied value from its source type (brief: user evidence must propagate).
# A manufacturer datasheet or the user's own measurement of the same device is first-hand
# evidence (A); a peer-reviewed paper or an experimental dataset about it is B; an engineering
# assumption is D; an unknown source gives no value (the component is unconfigured).
USER_SOURCE_GRADES = {
    "datasheet": "A",
    "measurement": "A",
    "paper": "B",
    "dataset": "B",
    "assumption": "D",
    "unknown": None,
}


def user_component(
    name,
    category,
    states,
    *,
    source_type,
    citation=None,
    locator=None,
    relation="exact",
    rail=None,
    supply_V=None,
    simulation_sensor=None,
):
    """Component entry plus the evidence source and records for user-supplied state powers.

    ``states`` maps uppercase state names to watts (``None`` = unknown). Returns
    ``{"component", "sources", "records", "grade"}`` ready for the configuration's
    ``components`` and ``evidence.sources/records``.
    """
    if source_type not in USER_SOURCE_GRADES:
        raise ConfigurationError(f"source_type must be one of {sorted(USER_SOURCE_GRADES)}")
    if not isinstance(name, str) or not name.strip() or not name.replace("_", "").isalnum():
        raise ConfigurationError("component name: letters, digits and underscores only")
    grade = USER_SOURCE_GRADES[source_type]
    if grade in ("A", "B") and not (isinstance(citation, str) and citation.strip()):
        raise ConfigurationError(
            f"a {source_type} source needs a citation (title, document or notebook reference)"
        )
    entry = {"name": name, "category": category, "relation": relation}
    if rail:
        entry["rail"] = rail
    if supply_V:
        entry["supply_V"] = list(supply_V)
    if simulation_sensor:
        entry["simulation_sensor"] = simulation_sensor
    known = {s: w for s, w in states.items() if w is not None}
    if grade is None or not known:
        entry["status"] = "unconfigured"
        entry["notes"] = "no defensible power value supplied"
        return {"component": entry, "sources": [], "records": [], "grade": None}
    source_id = f"USER-{name}"
    source = EvidenceSourceSpec(source_id, source_type, citation or f"{source_type} for {name}")
    records, entry_states = [], {}
    for state, watts in known.items():
        record = EvidenceRecordSpec(
            f"user.{name}.{state.lower()}",
            name,
            "electrical_power",
            "W",
            value=float(watts),
            bound="measured_mean" if source_type == "measurement" else "nominal",
            relation=relation,
            grade=grade,
            sources=(source_id,) if grade != "D" else (),
            location={"note": locator} if locator else {},
        )
        records.append(record.to_mapping())
        entry_states[state] = {"evidence": record.id}
    entry["states"] = entry_states
    entry["initial_state"] = next(iter(entry_states))
    return {
        "component": entry,
        "sources": [source.to_mapping()] if grade != "D" else [],
        "records": records,
        "grade": grade,
    }
