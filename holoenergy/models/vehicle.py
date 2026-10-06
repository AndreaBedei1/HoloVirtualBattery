"""Descriptive dynamics contract: no mass-to-power or hydrodynamics in this layer."""

from copy import deepcopy

from .._validation import ConfigurationError, keys, number


def vector3(value, name, *, nonnegative=False):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ConfigurationError(f"{name} must contain three values in documented SI units")
    return [number(x, name, minimum=0 if nonnegative else None) for x in value]


class VehicleProfile:
    """Carry configuration to an explicit dynamics adapter, never infer simulator physics.

    ``dynamics_mode: descriptive`` records parameters without applying them.
    ``dynamics_mode: adapter`` requires configure_vehicle(profile) on the adapter.
    Mass, volume, centers and drag remain owned by that dynamics backend.
    """

    def __init__(self, config):
        keys(
            config,
            {
                "name",
                "kind",
                "dynamics_source",
                "dynamics_mode",
                "mass_kg",
                "volume_m3",
                "center_of_mass_m",
                "center_of_buoyancy_m",
                "dimensions_m",
                "drag",
                "payload",
                "actuator_layout",
            },
            "vehicle",
        )
        self.config = deepcopy(config)
        self.name = config.get("name", "user_vehicle")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ConfigurationError("vehicle.name must be a nonempty string")
        self.mode = config.get("dynamics_mode", "descriptive")
        if self.mode not in ("descriptive", "adapter"):
            raise ConfigurationError("vehicle.dynamics_mode must be descriptive or adapter")
        for field in ("mass_kg", "volume_m3"):
            if field in config:
                number(config[field], f"vehicle.{field}", positive=True)
        for field in ("center_of_mass_m", "center_of_buoyancy_m", "dimensions_m"):
            if field in config:
                vector3(config[field], field, nonnegative=field == "dimensions_m")
        self._drag(config.get("drag", {}))
        payloads = config.get("payload", [])
        if isinstance(payloads, dict):
            payloads = [payloads]
        if not isinstance(payloads, list):
            raise ConfigurationError("vehicle.payload must be a mapping or list")
        for payload in payloads:
            keys(
                payload,
                {"name", "mass_kg", "displaced_volume_m3", "position_m", "drag"},
                "physical payload",
            )
            for field in ("mass_kg", "displaced_volume_m3"):
                if field not in payload:
                    raise ConfigurationError(f"Physical payload requires {field}")
                number(payload[field], f"payload.{field}", minimum=0)
            if "position_m" not in payload:
                raise ConfigurationError("Physical payload requires position_m in the body frame")
            vector3(payload["position_m"], "payload.position_m")
            self._drag(payload.get("drag", {}))
        layout = config.get("actuator_layout", [])
        if not isinstance(layout, list):
            raise ConfigurationError("actuator_layout must be a list")
        ids = set()
        for item in layout:
            keys(item, {"id", "position_m", "direction"}, "actuator layout")
            identity = item.get("id")
            if not isinstance(identity, str) or not identity or identity in ids:
                raise ConfigurationError("actuator layout IDs must be unique nonempty strings")
            ids.add(identity)
            vector3(item.get("position_m"), "actuator.position_m")
            direction = vector3(item.get("direction"), "actuator.direction")
            if abs(sum(x * x for x in direction) - 1) > 1e-6:
                raise ConfigurationError("actuator.direction must be a unit vector")

    @staticmethod
    def _drag(config):
        keys(config, {"coefficient", "reference_area_m2"}, "descriptive drag")
        for field in config:
            if field != "metadata":
                number(config[field], f"drag.{field}", minimum=0)

    @property
    def has_physical_description(self):
        return bool(set(self.config) & {"mass_kg", "volume_m3", "payload", "drag"})
