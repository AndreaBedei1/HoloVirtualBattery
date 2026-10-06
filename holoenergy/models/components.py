"""First-class user loads: named states and explicitly supplied operating curves."""

from .._validation import ConfigurationError, curve, interpolate, keys, number, required, timestep
from .payload import PayloadComponent, PayloadModel


class ComponentState(str):
    @property
    def value(self):
        return str(self)


class ElectricalComponent(PayloadComponent):
    """Reuse established rail/brownout policy; arbitrary states need no core changes."""

    def __init__(self, name, config):
        keys(
            config,
            {
                "name",
                "model",
                "type",
                "category",
                "states",
                "initial_state",
                "active_W",
                "power_model",
                "startup_duration_s",
                "brownout",
                "load_kind",
                "active_is_upper_bound",
                "simulation_sensor",
                "hardware_model",
            },
            f"component {name}",
        )
        kind = config.get("model", config.get("type", "generic_load"))
        if kind != "generic_load":
            raise ConfigurationError(f"{name}: supported component model is generic_load")
        self.category = config.get("category", "sensors")
        if self.category not in ("sensors", "compute", "auxiliaries"):
            raise ConfigurationError("component.category must be sensors, compute or auxiliaries")
        states = config.get("states", {})
        if not isinstance(states, dict):
            raise ConfigurationError("component.states must be a mapping")
        self.state_powers = {}
        for state, value in states.items():
            if not isinstance(state, str) or not state or state != state.upper():
                raise ConfigurationError("Component states must be nonempty uppercase strings")
            if isinstance(value, dict):
                keys(value, {"power_W"}, f"{name}.{state}")
                value = required(value, "power_W")
            self.state_powers[state] = number(value, f"{name}.{state}.power_W", minimum=0)
        if "active_W" in config:
            if "ACTIVE" in self.state_powers:
                raise ConfigurationError("Supply active_W or states.ACTIVE, not both")
            self.state_powers["ACTIVE"] = number(config["active_W"], "active_W", minimum=0)
        # Derived OFF is physical rail gating, explicitly documented, not standby.
        self.state_powers.setdefault("OFF", 0.0)
        self.variable = None
        model = config.get("power_model")
        if model is not None:
            keys(model, {"type", "input", "points", "initial_value", "states"}, "power_model")
            if model.get("type") != "lookup":
                raise ConfigurationError(
                    "power_model.type must be lookup with user-supplied points"
                )
            self.input_name = required(model, "input")
            if not isinstance(self.input_name, str) or not self.input_name:
                raise ConfigurationError(
                    "power_model.input must be a nonempty string with documented units"
                )
            self.input_curve = curve(
                required(model, "points"), "component operating curve", y_min=0
            )
            self.variable_states = model.get("states", ["ACTIVE"])
            if not isinstance(self.variable_states, list) or not self.variable_states:
                raise ConfigurationError("power_model.states must be a nonempty list")
            if any(
                not isinstance(s, str) or s != s.upper() or s == "OFF" for s in self.variable_states
            ):
                raise ConfigurationError(
                    "Variable-power states must be uppercase and cannot be OFF"
                )
            for state in self.variable_states:
                self.state_powers.setdefault(state, self.input_curve[0][1])
            self.initial_input = required(model, "initial_value")
            self.set_input(self.input_name, self.initial_input)
        self.start_duration = config.get("startup_duration_s")
        if self.start_duration is not None:
            self.start_duration = number(self.start_duration, "startup_duration_s", minimum=0)
            if not {"STARTING", "ACTIVE"} <= self.state_powers.keys():
                raise ConfigurationError("Timed startup requires STARTING and ACTIVE powers")
        self.generic_initial = ComponentState(
            config.get("initial_state", "ACTIVE" if "ACTIVE" in self.state_powers else "OFF")
        )
        legacy = {
            k: v
            for k, v in config.items()
            if k
            in {
                "brownout",
                "load_kind",
                "active_is_upper_bound",
                "simulation_sensor",
                "hardware_model",
            }
        }
        legacy.update(initial_state="OFF", states={"off_W": self.state_powers["OFF"]})
        super().__init__(name, legacy)

    def reset(self):
        self.state = self.generic_initial
        self.elapsed_s = 0.0
        self.brownout_latched = False
        self.brownout_elapsed_s = 0.0
        if self.variable is not None:
            self.set_input(self.input_name, self.initial_input)
        self._validate_state(self.state)

    def _validate_state(self, state):
        if state not in self.state_powers:
            raise ConfigurationError(f"{self.name}: unconfigured component state {state}")

    def set_state(self, state):
        self._validate_state(state)
        self.state = ComponentState(state)
        self.elapsed_s = self.brownout_elapsed_s = 0.0
        self.brownout_latched = False

    def set_input(self, name, value):
        if name != self.input_name:
            raise ConfigurationError(f"Unknown operating input {name}; expected {self.input_name}")
        value = number(value, name, minimum=self.input_curve[0][0], maximum=self.input_curve[-1][0])
        self.variable = value

    def _power(self, state):
        if self.variable is not None and state in self.variable_states:
            return interpolate(self.input_curve, self.variable)
        return self.state_powers[state]

    def preview(self, dt_s):
        dt = timestep(dt_s)
        if self.state == "STARTING" and self.start_duration is not None:
            startup = min(dt, max(0, self.start_duration - self.elapsed_s))
            return (startup * self._power("STARTING") + (dt - startup) * self._power("ACTIVE")) / dt
        return self._power(self.state)

    def step(self, dt_s):
        power = self.preview(dt_s)
        self.elapsed_s += dt_s
        if (
            self.state == "STARTING"
            and self.start_duration is not None
            and self.elapsed_s >= self.start_duration
        ):
            self.elapsed_s -= self.start_duration
            self.state = ComponentState("ACTIVE")
        return power


class ComponentModel(PayloadModel):
    def __init__(self, legacy=None, components=None):
        super().__init__(legacy or {})
        for item in self.components.values():
            item.category = "sensors"
        if components is not None and not isinstance(components, list):
            raise ConfigurationError("components must be a list of named loads")
        for config in components or []:
            name = required(config, "name")
            if not isinstance(name, str) or not name or name in self.components:
                raise ConfigurationError(
                    "Component names must be unique nonempty strings, including legacy sensors"
                )
            self.components[name] = ElectricalComponent(name, config)

    def set_input(self, name, input_name=None, value=None, **inputs):
        item = self.components[name]
        if not isinstance(item, ElectricalComponent) or item.variable is None:
            raise ConfigurationError(f"{name} has no configured variable power model")
        if input_name is not None:
            if inputs:
                raise ConfigurationError("Use one operating input syntax")
            inputs = {input_name: value}
        if len(inputs) != 1:
            raise ConfigurationError("Supply exactly one configured operating input")
        item.set_input(*next(iter(inputs.items())))
