"""Mission (scenario) model: phases with durations, component states, prescribed propulsion and
environment, compiled to the per-tick commands of :func:`holoenergy.analysis.replay.run_mission`.

The same mapping is written by the Python API, read from YAML/JSON and produced by the web UI;
there is no second scenario model. A phase states what HoloEnergy *does* with each quantity:

* ``water_temperature_C`` - applied by HoloEnergy (battery thermal ambient) in every mode.
* ``current_m_s`` - descriptive only in energy-only mode (no vehicle dynamics); applied by
  HoloOcean (``set_ocean_currents``) only when a HoloOcean runner passes it to the simulator.
* ``water_density_kg_m3`` - descriptive only: no public HoloOcean setting is used for it.
* ``propulsion`` - energy-only mode only: a prescribed wrench or per-actuator thrust (N), not a
  dynamics result. In HoloOcean modes the controller and the simulator produce the thrust.
"""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from ._validation import ConfigurationError, number

MODES = ("energy-only", "holoocean", "holoocean+desert")
PHASE_KEYS = {
    "name",
    "duration_s",
    "component_states",
    "propulsion",
    "water_temperature_C",
    "current_m_s",
    "water_density_kg_m3",
    "action",
    "notes",
}

ENVIRONMENT_STATUS = {
    "water_temperature_C": {
        "energy-only": "applied by HoloEnergy (battery thermal ambient)",
        "holoocean": "applied by HoloEnergy (battery thermal ambient)",
        "holoocean+desert": "applied by HoloEnergy (battery thermal ambient)",
    },
    "current_m_s": {
        "energy-only": "descriptive only (no vehicle dynamics in this mode)",
        "holoocean": "applied by HoloOcean when the runner passes it (set_ocean_currents)",
        "holoocean+desert": "applied by HoloOcean when the runner passes it (set_ocean_currents)",
    },
    "water_density_kg_m3": {
        "energy-only": "descriptive only",
        "holoocean": "descriptive only (no public HoloOcean setting is used)",
        "holoocean+desert": "descriptive only (no public HoloOcean setting is used)",
    },
}

MODE_SCOPE = {
    "energy-only": {
        "establishes": [
            "electrical energy of the configured loads for the stated schedule",
            "hardware, payload and battery comparisons under the same prescribed thrust",
        ],
        "cannot_establish": [
            "propulsion energy of a real manoeuvre (thrust is prescribed, not simulated)",
            "any effect of currents, drag or vehicle layout on thrust demand",
        ],
    },
    "holoocean": {
        "establishes": [
            "simulator-conditional propulsion energy from HoloOcean dynamics",
            "effect of layout, currents and controller on thrust demand in the simulator",
        ],
        "cannot_establish": [
            "physical-vehicle accuracy (HoloOcean drag is not validated for any vehicle)",
            "network effects on modem energy (no DESERT session)",
        ],
    },
    "holoocean+desert": {
        "establishes": [
            "simulator-conditional propulsion energy plus modem energy from observed "
            "DESERT TX/RX events",
        ],
        "cannot_establish": [
            "physical-vehicle accuracy",
            "acoustic source level in dB as electrical power (never converted)",
        ],
    },
}


def actuator_count(config):
    """Number of actuators of a resolved configuration (actuators list or propulsion)."""
    if config.get("actuators"):
        return len(config["actuators"])
    propulsion = config.get("propulsion") or {}
    if isinstance(propulsion.get("thruster_count"), int):
        return propulsion["thruster_count"]
    return len(propulsion.get("actuator_ids") or [])


def _vector(value, name, length):
    if not isinstance(value, (list, tuple)) or len(value) != length:
        raise ConfigurationError(f"{name} must be a list of {length} numbers")
    return tuple(number(v, name) for v in value)


@dataclass(frozen=True)
class MissionPhase:
    name: str
    duration_s: float
    component_states: dict = field(default_factory=dict)
    propulsion: dict | None = None
    water_temperature_C: float | None = None
    current_m_s: tuple | None = None
    water_density_kg_m3: float | None = None
    action: str | None = None
    notes: str | None = None

    @classmethod
    def from_mapping(cls, data):
        if not isinstance(data, dict):
            raise ConfigurationError("each mission phase must be a mapping")
        unknown = set(data) - PHASE_KEYS
        if unknown:
            raise ConfigurationError(f"unknown mission phase fields {sorted(unknown)}")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError("phase.name must be a nonempty string")
        duration = number(data.get("duration_s"), f"phase {name}.duration_s", positive=True)
        states = data.get("component_states") or {}
        if not isinstance(states, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v == v.upper() and v
            for k, v in states.items()
        ):
            raise ConfigurationError(
                f"phase {name}.component_states maps component names to uppercase states"
            )
        propulsion = data.get("propulsion")
        if propulsion is not None:
            if not isinstance(propulsion, dict) or len(propulsion) != 1:
                raise ConfigurationError(
                    f"phase {name}.propulsion is {{wrench_N: [6]}} or {{thrust_N: [n]}}"
                )
            ((kind, values),) = propulsion.items()
            if kind == "wrench_N":
                propulsion = {"wrench_N": list(_vector(values, f"phase {name}.wrench_N", 6))}
            elif kind == "thrust_N":
                if not isinstance(values, (list, tuple)) or not values:
                    raise ConfigurationError(f"phase {name}.thrust_N must be a nonempty list")
                propulsion = {"thrust_N": [number(v, f"phase {name}.thrust_N") for v in values]}
            else:
                raise ConfigurationError(f"phase {name}.propulsion must be wrench_N or thrust_N")
        temperature = data.get("water_temperature_C")
        if temperature is not None:
            temperature = number(
                temperature, f"phase {name}.water_temperature_C", minimum=-5, maximum=40
            )
        current = data.get("current_m_s")
        if current is not None:
            current = _vector(current, f"phase {name}.current_m_s", 3)
        density = data.get("water_density_kg_m3")
        if density is not None:
            density = number(
                density, f"phase {name}.water_density_kg_m3", minimum=900, maximum=1100
            )
        return cls(
            name.strip(),
            duration,
            dict(states),
            propulsion,
            temperature,
            current,
            density,
            data.get("action"),
            data.get("notes"),
        )

    def to_mapping(self):
        out = {"name": self.name, "duration_s": self.duration_s}
        if self.component_states:
            out["component_states"] = dict(self.component_states)
        for key in ("propulsion", "water_temperature_C", "water_density_kg_m3", "action", "notes"):
            value = getattr(self, key)
            if value is not None:
                out[key] = copy.deepcopy(value)
        if self.current_m_s is not None:
            out["current_m_s"] = list(self.current_m_s)
        return out


@dataclass(frozen=True)
class Mission:
    name: str
    phases: tuple
    description: str | None = None

    @classmethod
    def from_mapping(cls, data):
        if not isinstance(data, dict):
            raise ConfigurationError("mission must be a mapping")
        unknown = set(data) - {"name", "phases", "description", "schema_version"}
        if unknown:
            raise ConfigurationError(f"unknown mission fields {sorted(unknown)}")
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigurationError("mission.name must be a nonempty string")
        phases = data.get("phases")
        if not isinstance(phases, list) or not phases:
            raise ConfigurationError("mission.phases must be a nonempty list")
        parsed = tuple(MissionPhase.from_mapping(p) for p in phases)
        names = [p.name for p in parsed]
        if len(set(names)) != len(names):
            raise ConfigurationError("mission phase names must be unique")
        return cls(name.strip(), parsed, data.get("description"))

    @classmethod
    def load(cls, path):
        path = Path(path)
        text = path.read_text(encoding="utf-8")
        data = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
        return cls.from_mapping(data)

    def to_mapping(self):
        out = {
            "schema_version": 1,
            "name": self.name,
            "phases": [p.to_mapping() for p in self.phases],
        }
        if self.description:
            out["description"] = self.description
        return out

    def to_yaml(self, path):
        path = Path(path)
        path.write_text(yaml.safe_dump(self.to_mapping(), sort_keys=False), encoding="utf-8")
        return path

    @property
    def duration_s(self):
        return sum(p.duration_s for p in self.phases)

    def environment_effects(self, mode):
        """Per phase and quantity: the value and whether HoloEnergy or HoloOcean applies it."""
        if mode not in MODES:
            raise ConfigurationError(f"mode must be one of {MODES}")
        rows = []
        for phase in self.phases:
            for key in ENVIRONMENT_STATUS:
                value = getattr(phase, key)
                if value is not None:
                    rows.append(
                        {
                            "phase": phase.name,
                            "quantity": key,
                            "value": list(value) if isinstance(value, tuple) else value,
                            "status": ENVIRONMENT_STATUS[key][mode],
                        }
                    )
        return rows

    def commands(self, config, dt_s=None):
        """Per-tick commands for an energy-only run of the resolved configuration ``config``."""
        dt = number(
            dt_s if dt_s is not None else config["simulation"]["dt_s"], "dt_s", positive=True
        )
        mode = (config.get("actuation") or {}).get("action_mode", "thrusters")
        count = actuator_count(config)
        components = {c.get("name") for c in config.get("components") or []}
        commands = []
        for phase in self.phases:
            unknown = set(phase.component_states) - components
            if unknown:
                raise ConfigurationError(
                    f"phase {phase.name} sets states of {sorted(unknown)}, which the robot "
                    "does not have"
                )
            action = self._action(phase, mode, count)
            ticks = max(1, round(phase.duration_s / dt))
            if abs(ticks * dt - phase.duration_s) > 1e-6 * max(1.0, phase.duration_s):
                raise ConfigurationError(
                    f"phase {phase.name}: duration {phase.duration_s:g} s is not a whole "
                    f"number of {dt:g} s steps"
                )
            for i in range(ticks):
                item = {"action": list(action), "phase": phase.name}
                if i == 0:
                    if phase.component_states:
                        item["sensor_states"] = dict(phase.component_states)
                    if phase.water_temperature_C is not None:
                        item["water_temperature_C"] = phase.water_temperature_C
                commands.append(item)
        return commands

    @staticmethod
    def _action(phase, mode, count):
        if phase.propulsion is None:
            return [0.0] * (6 if mode == "wrench" else count)
        kind, values = next(iter(phase.propulsion.items()))
        if mode == "wrench" and kind == "wrench_N":
            return list(values)
        if mode != "wrench" and kind == "thrust_N":
            if len(values) != count:
                raise ConfigurationError(
                    f"phase {phase.name}: thrust_N has {len(values)} values; the robot has "
                    f"{count} actuators"
                )
            return list(values)
        expected = "wrench_N (6 values)" if mode == "wrench" else f"thrust_N ({count} values)"
        raise ConfigurationError(
            f"phase {phase.name}: the robot takes {expected}; the phase gives {kind}"
        )


def run_scenario(config, mission, output_dir, *, mode="energy-only"):
    """Energy-only run of ``mission`` on ``config``; returns the :class:`EnergyReport`.

    HoloOcean modes need a simulator process and a robot-to-agent mapping; they are started by
    the runners in ``examples/`` and ``experiments/`` and stream to the same dashboard.
    """
    if mode != "energy-only":
        raise ConfigurationError(
            f"run_scenario runs energy-only missions; '{mode}' runs are started with the "
            "HoloOcean runners (see docs/ui_quickstart.md)"
        )
    from .analysis.replay import run_mission
    from .config import load_config
    from .report import EnergyReport

    resolved = load_config(data=copy.deepcopy(config))
    resolved.setdefault("provenance", {})["scenario"] = f"energy-only mission {mission.name}"
    output_dir = Path(output_dir)
    result = run_mission(resolved, mission.commands(resolved), output_dir)
    return EnergyReport.load(result["report"])
