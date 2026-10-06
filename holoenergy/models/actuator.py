"""Actuator energy interface and user-supplied force-only tables.

No universal force/power law is assumed. A pump or manipulator can implement the
same interface when its command, load domain and dynamics adapter are defined.
"""

from typing import Protocol, runtime_checkable

from .._validation import ConfigurationError


@runtime_checkable
class ActuatorEnergyModel(Protocol):
    min_voltage: float
    max_voltage: float
    tables: list

    def power(self, action, voltage, units="force_N"): ...

    def max_force(self, voltage, direction): ...

    def force(self, command, voltage): ...


_CUSTOM_MODELS = {}


def register_actuator_model(name, factory):
    """Register a trusted Python factory before loading config; no YAML code imports."""
    if not isinstance(name, str) or not name or not callable(factory) or name in _CUSTOM_MODELS:
        raise ConfigurationError(
            "Custom actuator requires a unique model name and callable factory"
        )
    _CUSTOM_MODELS[name] = factory


def make_actuator(config):
    """Existing measured command tables or explicitly supplied force->power data."""
    from .propulsion import ThrusterModel

    if config.get("model") in _CUSTOM_MODELS:
        result = _CUSTOM_MODELS[config["model"]](config)
        if not isinstance(result, ActuatorEnergyModel):
            raise ConfigurationError(
                "Custom direct-effort actuator must implement ActuatorEnergyModel"
            )
        return result

    if "force_power_tables" not in config:
        return ThrusterModel(config)
    from copy import deepcopy

    from .._validation import curve, keys, number, required

    keys(config, {"model", "force_power_tables"}, "force-power actuator")
    normalized = {
        "model": required(config, "model"),
        "metadata": config.get("metadata", {}),
        "voltage_tables": [],
    }
    for table in required(config, "force_power_tables"):
        keys(table, {"voltage_V", "forward", "reverse"}, "force-power voltage table")
        branches = {}
        for direction in ("forward", "reverse"):
            points = curve(required(table, direction), "force-power curve", y_min=0)
            if points[0] != (0, 0) or points[-1][0] <= 0:
                raise ConfigurationError(
                    "Force-power data must start at zero and have positive force"
                )
            branches[direction] = [
                {"command": f / points[-1][0], "force_N": f, "power_W": p} for f, p in points
            ]
        normalized["voltage_tables"].append(
            {
                "voltage_V": number(required(table, "voltage_V"), "voltage_V", positive=True),
                **branches,
            }
        )
    result = ThrusterModel(deepcopy(normalized))
    result.force_only = True
    return result
