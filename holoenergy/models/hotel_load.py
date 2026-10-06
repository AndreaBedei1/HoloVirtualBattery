"""User-configured onboard electronics load; no implicit hardware consumption."""

from .._validation import keys, number, required


class HotelLoad:
    def __init__(self, config):
        keys(config, {"constant_W", "components_W"}, "hotel_load")
        self.constant_W = number(required(config, "constant_W"), "constant_W", minimum=0)
        self.initial_components = {
            name: number(value, f"hotel_load.{name}", minimum=0)
            for name, value in config.get("components_W", {}).items()
        }
        self.reset()

    def reset(self):
        self.components = dict(self.initial_components)

    @property
    def power_W(self):
        return self.constant_W + sum(self.components.values())

    def set_component_power(self, name, power_W):
        if name not in self.components:
            raise KeyError(f"Unknown configured hotel component: {name}")
        self.components[name] = number(power_W, name, minimum=0)
