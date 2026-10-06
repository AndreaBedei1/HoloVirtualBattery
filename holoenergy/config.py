"""YAML/JSON configuration and reusable packaged/local profiles."""

import copy
import json
import warnings
from importlib.resources import files
from pathlib import Path

import yaml

from ._validation import ConfigurationError, keys, number


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
        value = json.loads(text) if str(path).endswith(".json") else yaml.safe_load(text)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"Cannot load configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"{path} must contain a mapping")
    return value


def _resolve(data, base_dir, stack=()):
    if isinstance(data, list):
        return [_resolve(item, base_dir, stack) for item in data]
    if not isinstance(data, dict):
        return data
    data = copy.deepcopy(data)
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
    return result


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
        },
        "configuration",
    )
    if config.get("schema_version") != 1:
        raise ConfigurationError("schema_version must be 1")
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
