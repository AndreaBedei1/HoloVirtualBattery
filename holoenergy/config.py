"""YAML/JSON configuration and reusable packaged/local profiles."""

import copy
import json
import re
import warnings
from functools import lru_cache
from importlib.resources import files
from pathlib import Path

import yaml

from ._validation import ConfigurationError, keys, number


class _ConfigLoader(yaml.SafeLoader):
    """YAML 1.2 boolean spelling: OFF/ON are component labels, not booleans."""


_ConfigLoader.yaml_implicit_resolvers = {
    k: [(tag, pattern) for tag, pattern in values if tag != "tag:yaml.org,2002:bool"]
    for k, values in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_ConfigLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF")
)


def _merge(base, overlay):
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _read(path):
    try:
        text = path.read_text(encoding="utf-8")
        value = (
            json.loads(text)
            if str(path).endswith(".json")
            else yaml.load(text, Loader=_ConfigLoader)
        )
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path} must contain a mapping")
    return value


@lru_cache(maxsize=1)
def _builtin_models():
    return _read(files("holoenergy").joinpath("profiles", "registry.json"))


def _resolve(data, base_dir, stack=()):
    if isinstance(data, list):
        return [_resolve(item, base_dir, stack) for item in data]
    if not isinstance(data, dict):
        return data
    data = copy.deepcopy(data)
    if isinstance(data.get("model"), str) and not (
        {"voltage_tables", "force_power_tables", "profile"} & data.keys()
    ):
        profile = _builtin_models().get(data["model"])
        if profile is not None:
            data["profile"] = "package:" + profile
    if "profile" in data:
        name = data.pop("profile")
        if not isinstance(name, str):
            raise ConfigurationError("profile must be a path string")
        if name.startswith("package:"):
            relative = name.removeprefix("package:")
            if Path(relative).is_absolute() or ".." in Path(relative).parts or "\\" in relative:
                raise ConfigurationError("Invalid packaged profile path")
            path = files("holoenergy").joinpath("profiles", *relative.split("/"))
            next_base = base_dir
        else:
            path = (base_dir / name).resolve()
            next_base = path.parent
        identity = str(path)
        if identity in stack:
            raise ConfigurationError(f"Cyclic profile inclusion: {identity}")
        inherited = _resolve(_read(path), next_base, (*stack, identity))
        data = _merge(inherited, data)
    return {k: _resolve(v, base_dir, stack) for k, v in data.items()}


def _placeholders(data, prefix=""):
    result = []
    if isinstance(data, dict):
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            result.extend(f"{prefix}{p}" for p in metadata.get("placeholders", []))
        for key, value in data.items():
            if key != "metadata":
                result.extend(_placeholders(value, f"{prefix}{key}."))
    elif isinstance(data, list):
        for index, item in enumerate(data):
            result.extend(_placeholders(item, f"{prefix}{index}."))
    return result


def _normalize_generic(config):
    """Resolve the public vehicle schema to the existing numerical model inputs."""
    telemetry = config.get("telemetry", {})
    keys(telemetry, {"enabled", "port", "publish_hz"}, "telemetry")
    if "enabled" in telemetry and not isinstance(telemetry["enabled"], bool):
        raise ConfigurationError("telemetry.enabled must be a boolean")
    if "actuators" in config:
        if "propulsion" in config:
            raise ConfigurationError("Supply actuators or legacy propulsion, not both")
        raw = config.pop("actuators")
        if not isinstance(raw, list) or not raw:
            raise ConfigurationError("actuators must be a nonempty list")
        models, identities, units = [], [], set()
        for item in raw:
            if not isinstance(item, dict):
                raise ConfigurationError("Each actuator must be a model/profile mapping")
            count = item.pop("count", 1)
            if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
                raise ConfigurationError("actuator.count must be a positive integer")
            identity = item.pop("id", None)
            unit = item.pop("action_units", "force_N")
            units.add(unit)
            for i in range(count):
                identities.append(
                    f"{identity}_{i + 1}"
                    if identity and count > 1
                    else identity or f"T{len(identities) + 1}"
                )
                models.append(copy.deepcopy(item))
        if len(units) != 1:
            raise ConfigurationError("Direct action vectors require common actuator action_units")
        config["propulsion"] = {
            "thruster_count": len(models),
            "action_units": units.pop(),
            "actuator_ids": identities,
        }
        if all(model == models[0] for model in models):
            config["propulsion"]["thruster"] = models[0]
        else:
            config["propulsion"]["thrusters"] = models
        config.setdefault("hotel_load", {"constant_W": 0})
    if "payload" in config:
        vehicle = config.setdefault("vehicle", {})
        if "payload" in vehicle:
            raise ConfigurationError("Specify physical payload in one location")
        vehicle["payload"] = config.pop("payload")
    environment = config.setdefault("environment", {})
    keys(
        environment,
        {"water_temperature_C", "water_density_kg_m3", "current_velocity_m_s", "current_mode"},
        "environment",
    )
    thermal = config.setdefault("thermal", {})
    if "water_temperature_C" in environment:
        water = number(environment["water_temperature_C"], "water_temperature_C", minimum=-273.14)
        if "water_temperature_C" in thermal and thermal["water_temperature_C"] != water:
            raise ConfigurationError("Conflicting thermal/environment water_temperature_C")
        thermal["water_temperature_C"] = water
    elif "water_temperature_C" in thermal:
        environment["water_temperature_C"] = thermal["water_temperature_C"]
    if "components" in config:
        config.setdefault("hotel_load", {"constant_W": 0})
    if config.get("battery", {}).get("model") == "energy_bucket":
        thermal.setdefault("initial_temperature_C", thermal.get("water_temperature_C"))


def load_config(path=None, *, data=None):
    """Return a resolved independent mapping, validating top-level fields.

    Physical model constructors validate their own sections. Packaged profiles
    work after wheel installation; relative profiles resolve against the file.
    """
    if (path is None) == (data is None):
        raise ConfigurationError("Supply exactly one of config_path or config")
    base = Path(path).resolve().parent if path is not None else Path.cwd()
    raw = _read(Path(path)) if path is not None else data
    config = _resolve(raw, base)
    keys(
        config,
        {
            "schema_version",
            "battery",
            "thermal",
            "propulsion",
            "sensors",
            "hotel_load",
            "converters",
            "logging",
            "simulation",
            "power_manager",
            "allow_placeholders",
            "fidelity_level",
            "provenance",
            "vehicle",
            "actuators",
            "components",
            "environment",
            "payload",
            "telemetry",
        },
        "configuration",
    )
    config.setdefault("schema_version", 1)
    if config.get("schema_version") != 1:
        raise ConfigurationError("schema_version must be 1")
    _normalize_generic(config)
    for section in ("battery", "thermal", "propulsion"):
        if section not in config:
            raise ConfigurationError(f"Missing {section} section")
    level = {"energy_bucket": "L0", "rint": "L1"}.get(config["battery"].get("model"))
    if level is None:
        raise ConfigurationError("Supported fidelity levels are L0 (energy_bucket) and L1 (rint)")
    if config.get("fidelity_level", level) != level:
        raise ConfigurationError("fidelity_level must match battery.model; L2 is deferred")
    config["fidelity_level"] = level
    simulation = config.setdefault("simulation", {})
    keys(simulation, {"dt_s", "agent_name", "expected_agent_type", "control_scheme"}, "simulation")
    simulation["dt_s"] = number(simulation.get("dt_s"), "simulation.dt_s", positive=True)
    for flag in ("allow_placeholders",):
        if flag in config and not isinstance(config[flag], bool):
            raise ConfigurationError(f"{flag} must be a boolean")
    uncalibrated = sorted(set(_placeholders(config)))
    if uncalibrated and not config.get("allow_placeholders", False):
        raise ConfigurationError(
            "Uncalibrated placeholders require allow_placeholders: true: " + ", ".join(uncalibrated)
        )
    if uncalibrated:
        warnings.warn(
            "Uncalibrated demo parameters: " + ", ".join(uncalibrated), UserWarning, stacklevel=2
        )
    return config


def model_warnings(config):
    result = ["placeholder: " + key for key in sorted(set(_placeholders(config)))]
    metadata = config.get("battery", {}).get("metadata", {})
    if config.get("fidelity_level") == "L0":
        result.append("L0 temperature is a fixed reference, not a thermal prediction")
    elif not metadata.get("temperature_characterized", False):
        result.append("Battery temperature tables are not characterized for this pack")
    return result


def with_fidelity(config, level, *, capacity_Wh=None):
    """Select a baseline without inventing L1 parameters; retain all other inputs."""
    result = copy.deepcopy(config)
    battery = result["battery"]
    if level == "L0" and battery["model"] == "rint":
        capacity = (
            number(capacity_Wh, "capacity_Wh", positive=True)
            if capacity_Wh is not None
            else battery["capacity_Ah"] * battery["nominal_voltage_V"]
        )
        result["battery"] = {
            "model": "energy_bucket",
            "capacity_Wh": capacity,
            **{
                k: battery[k]
                for k in (
                    "nominal_voltage_V",
                    "initial_soc",
                    "max_current_A",
                    "max_power_W",
                    "low_soc_threshold",
                )
                if k in battery
            },
            "metadata": {
                "value_kind": "ideal_baseline",
                "capacity_derivation": "user supplied Wh"
                if capacity_Wh is not None
                else "nominal capacity_Ah * nominal_voltage_V; not measured usable energy",
                "source_battery_profile": battery,
                "calibration_status": "uncalibrated",
                "placeholders": ["capacity_Wh"],
            },
        }
        result["allow_placeholders"] = True
    elif (
        level not in ("L0", "L1")
        or battery["model"] != {"L0": "energy_bucket", "L1": "rint"}[level]
    ):
        raise ConfigurationError("L1 requires an explicit Rint profile; L2 is deferred")
    result["fidelity_level"] = level
    return result
