"""Named, packaged profiles: vehicles, batteries, components and communication modems.

``vehicle_config("bluerov2-heavy")`` returns a configuration mapping that
:class:`holoenergy.EnergyAwareEnv` accepts.  Names are stable identifiers; files stay
the single source of each profile.  Exact profiles and proxies keep their labels.
"""

from __future__ import annotations

import copy
from importlib.resources import files
from pathlib import Path

from ._validation import ConfigurationError
from .config import _read, load_config

VEHICLES = {
    "bluerov2-heavy": {
        "file": "vehicles/bluerov2_heavy_holoocean.yaml",
        "relation": "representative",
        "summary": "HoloOcean 2.3.0 BlueROV2 (8 x T200), simulator-exact geometry",
    },
    "bluerov2-standard": {
        "file": "vehicles/bluerov2_standard_6t.yaml",
        "relation": "proxy",
        "summary": "BlueROV2 Standard 6 x T200 (role-exact, proxy vertical positions), "
        "wrench-equivalent on the HoloOcean BlueROV2 body",
    },
    "bluerov2-heavy-v0.1": {
        "file": "vehicles/bluerov2_heavy.yaml",
        "relation": "representative",
        "summary": "v0.1 reference profile (aggregate 15 W hotel placeholder), kept for regression",
    },
    "generic-lightweight-rov": {
        "file": "vehicles/generic_lightweight_rov.yaml",
        "relation": "user",
        "summary": "demonstration configuration (user-supplied numbers)",
    },
    "generic-auv": {
        "file": "vehicles/generic_auv.yaml",
        "relation": "user",
        "summary": "demonstration configuration (user-supplied numbers)",
    },
    # Literature proxies: a real vehicle's electrical data on a generic HoloOcean dynamic class.
    "hovering-mares-like": {
        "file": "vehicles/hovering_mares_like.yaml",
        "relation": "proxy",
        "summary": "MARES-derived energy profile on the generic HoloOcean HoveringAUV "
        "(literature proxy, grade C)",
    },
    "torpedo-remus-like": {
        "file": "vehicles/torpedo_remus_like.yaml",
        "relation": "proxy",
        "summary": "REMUS-derived energy profile on the generic HoloOcean TorpedoAUV "
        "(literature proxy, grade C)",
    },
    "torpedo-tethys-like": {
        "file": "vehicles/torpedo_tethys_like.yaml",
        "relation": "proxy",
        "summary": "Tethys-derived energy profile on the generic HoloOcean TorpedoAUV "
        "(literature proxy, grade C)",
    },
    "torpedo-autosub-like": {
        "file": "vehicles/torpedo_autosub_like.yaml",
        "relation": "proxy",
        "summary": "Autosub Long Range 6000-derived energy profile on the generic HoloOcean "
        "TorpedoAUV (literature proxy, grade C)",
    },
}
BATTERIES = {
    "bluerobotics-4s-18ah": "batteries/bluerobotics_4s18ah_v2.yaml",
    "bluerobotics-4s-18ah-v0.1": "batteries/bluerobotics_4s18ah.yaml",
    "demo-24v30ah": "batteries/demo_24v30ah.yaml",
}


def _profiles_root():
    return files("holoenergy").joinpath("profiles")


def _discover(folder):
    root = _profiles_root().joinpath(folder)
    return {
        item.name.removesuffix(".yaml").replace("_", "-"): f"{folder}/{item.name}"
        for item in sorted(root.iterdir(), key=lambda p: p.name)
        if item.name.endswith(".yaml")
    }


def components():
    return _discover("components")


def modems():
    return _discover("communications")


def list_profiles():
    return {
        "vehicles": {k: {kk: v[kk] for kk in ("relation", "summary")} for k, v in VEHICLES.items()},
        "batteries": sorted(BATTERIES),
        "components": sorted(components()),
        "modems": sorted(modems()),
    }


def _lookup(table, name, kind):
    if name in table:
        entry = table[name]
        return entry["file"] if isinstance(entry, dict) else entry
    raise ConfigurationError(f"Unknown {kind} profile {name!r}; available: {sorted(table)}")


def profile_reference(name, kind):
    """``package:...`` reference for a named profile, or an existing file path."""
    if isinstance(name, (str, Path)) and Path(name).suffix in (".yaml", ".yml", ".json"):
        return str(Path(name).resolve())
    table = {
        "vehicle": VEHICLES,
        "battery": BATTERIES,
        "component": components(),
        "modem": modems(),
    }[kind]
    return "package:" + _lookup(table, name, kind)


def vehicle_config(vehicle_profile, *, battery_profile=None, components=None, overrides=None):
    """Compose a configuration mapping from named profiles (no numbers are added here)."""
    data = {"profile": profile_reference(vehicle_profile, "vehicle")}
    if battery_profile is not None:
        data["battery"] = {"profile": profile_reference(battery_profile, "battery")}
    if components is not None:
        resolved = load_config(data=copy.deepcopy(data))
        existing = list(resolved.get("components", []))
        for item in components:
            if isinstance(item, str):
                item = {"profile": profile_reference(item, "component")}
            existing.append(copy.deepcopy(item))
        data["components"] = existing
    if overrides:
        data = _deep_merge(data, overrides)
    return data


def modem_profile(name):
    """Mapping for :class:`holoenergy.integrations.ModemPowerProfile.from_mapping`."""
    path = _profiles_root().joinpath(*_lookup(modems(), name, "modem").split("/"))
    return _read(path)


def _deep_merge(base, overlay):
    result = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result
