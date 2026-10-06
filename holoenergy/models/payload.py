"""State-based electrical loads with exact startup and periodic ping accounting."""

from enum import Enum
from math import floor

from .._validation import ConfigurationError, keys, number, required, timestep


class PayloadState(str, Enum):
    OFF = "OFF"
    IDLE = "IDLE"
    ACTIVE = "ACTIVE"
    PINGING = "PINGING"
    STARTING = "STARTING"


class PayloadComponent:
    def __init__(self, name, config):
        keys(
            config,
            {
                "simulation_sensor",
                "initial_state",
                "states",
                "frequency_Hz",
                "active_is_upper_bound",
                "hardware_model",
            },
            f"sensor {name}",
        )
        self.name = name
        self.simulation_sensor = config.get("simulation_sensor")
        self.initial_state = PayloadState(config.get("initial_state", "OFF"))
        states = required(config, "states")
        keys(
            states,
            {
                "off_W",
                "idle_W",
                "active_W",
                "startup_W",
                "startup_duration_s",
                "ping_W",
                "ping_duration_s",
            },
            f"sensor {name} states",
        )
        self.states = {}
        for key, value in states.items():
            self.states[key] = None if value is None else number(value, f"{name}.{key}", minimum=0)
        # OFF means physical power gating. This does not mean standby is zero.
        self.states.setdefault("off_W", 0.0)
        freq = config.get("frequency_Hz")
        self.frequency = None if freq is None else number(freq, "frequency_Hz", positive=True)
        if self.frequency is not None:
            duration = self.parameter("ping_duration_s")
            if duration * self.frequency > 1:
                raise ConfigurationError(f"{name}: ping_duration_s * frequency_Hz must be <= 1")
        self.active_is_upper_bound = bool(config.get("active_is_upper_bound", False))
        self.reset()

    def parameter(self, key):
        if self.states.get(key) is None:
            raise ConfigurationError(
                f"{self.name}.{key} is undocumented/unconfigured; supply a measured or user value"
            )
        return self.states[key]

    def reset(self):
        self.state = self.initial_state
        self.elapsed_s = 0.0
        self._validate_state(self.state)

    def _validate_state(self, state):
        power_key = {
            PayloadState.OFF: "off_W",
            PayloadState.IDLE: "idle_W",
            PayloadState.ACTIVE: "active_W",
            PayloadState.STARTING: "startup_W",
            PayloadState.PINGING: "ping_W",
        }[state]
        self.parameter(power_key)
        if state == PayloadState.STARTING:
            self.parameter("startup_duration_s")
            self.parameter("active_W")
        if state == PayloadState.PINGING:
            self.parameter("ping_duration_s")
            self.parameter("active_W")

    def set_state(self, state):
        state = PayloadState(state)
        self._validate_state(state)
        self.state = state
        self.elapsed_s = 0.0

    def _ping_on_time(self, elapsed):
        period = 1 / self.frequency
        cycles = floor(elapsed / period)
        return cycles * self.parameter("ping_duration_s") + min(
            elapsed - cycles * period, self.parameter("ping_duration_s")
        )

    def preview(self, dt_s):
        """Return mean power without advancing the component."""
        dt = timestep(dt_s)
        if self.state == PayloadState.STARTING:
            remaining = max(0, self.parameter("startup_duration_s") - self.elapsed_s)
            startup = min(dt, remaining)
            return (
                startup * self.parameter("startup_W") + (dt - startup) * self.parameter("active_W")
            ) / dt
        if self.state == PayloadState.PINGING:
            if self.frequency is None:
                on_time = min(dt, max(0, self.parameter("ping_duration_s") - self.elapsed_s))
            else:
                on_time = self._ping_on_time(self.elapsed_s + dt) - self._ping_on_time(
                    self.elapsed_s
                )
            on_time = min(dt, max(0.0, on_time))
            return (
                on_time * self.parameter("ping_W") + (dt - on_time) * self.parameter("active_W")
            ) / dt
        key = {
            PayloadState.OFF: "off_W",
            PayloadState.IDLE: "idle_W",
            PayloadState.ACTIVE: "active_W",
        }[self.state]
        return self.parameter(key)

    def step(self, dt_s):
        power = self.preview(dt_s)
        self.elapsed_s += dt_s
        if self.state == PayloadState.STARTING:
            if self.elapsed_s >= self.parameter("startup_duration_s"):
                self.elapsed_s -= self.parameter("startup_duration_s")
                self.state = PayloadState.ACTIVE
        elif self.state == PayloadState.PINGING and self.frequency is None:
            if self.elapsed_s >= self.parameter("ping_duration_s"):
                self.elapsed_s -= self.parameter("ping_duration_s")
                self.state = PayloadState.ACTIVE
        return power


class PayloadModel:
    def __init__(self, config):
        self.components = {name: PayloadComponent(name, item) for name, item in config.items()}

    def set_state(self, name, state):
        self.components[name].set_state(state)

    def preview(self, dt_s):
        return {name: item.preview(dt_s) for name, item in self.components.items()}

    def step(self, dt_s):
        return {name: item.step(dt_s) for name, item in self.components.items()}

    def reset(self):
        for item in self.components.values():
            item.reset()
