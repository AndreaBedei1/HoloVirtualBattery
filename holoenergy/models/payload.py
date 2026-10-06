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
                "power_policy",
                "load_kind",
                "brownout",
            },
            f"sensor {name}",
        )
        self.name = name
        self.simulation_sensor = config.get("simulation_sensor")
        self.power_policy = config.get("power_policy", "manual")
        if self.power_policy != "manual":
            raise ConfigurationError(
                f"{name}: sensor_linked is unavailable: HoloOcean has no public electrical-state "
                "contract. Use manual states; capture timing is not a power state."
            )
        self.load_kind = config.get("load_kind", "continuous")
        if self.load_kind not in ("continuous", "discrete"):
            raise ConfigurationError("load_kind must be continuous or discrete")
        brownout = config.get("brownout", {})
        keys(
            brownout,
            {"minimum_bus_voltage_V", "minimum_supplied_fraction", "behavior", "restart_delay_s"},
            f"{name} brownout",
        )
        self.minimum_voltage = (
            None
            if brownout.get("minimum_bus_voltage_V") is None
            else number(brownout["minimum_bus_voltage_V"], "minimum_bus_voltage_V", positive=True)
        )
        self.minimum_fraction = (
            None
            if brownout.get("minimum_supplied_fraction") is None
            else number(
                brownout["minimum_supplied_fraction"],
                "minimum_supplied_fraction",
                positive=True,
                maximum=1,
            )
        )
        self.brownout_enabled = (
            self.minimum_voltage is not None or self.minimum_fraction is not None
        )
        if self.brownout_enabled and self.load_kind != "discrete":
            raise ConfigurationError("Brownout thresholds require load_kind: discrete")
        self.brownout_behavior = brownout.get("behavior", "latch_off")
        if self.brownout_behavior not in ("latch_off", "auto_restart"):
            raise ConfigurationError("brownout.behavior must be latch_off or auto_restart")
        self.restart_delay = (
            number(required(brownout, "restart_delay_s"), "restart_delay_s", minimum=0)
            if self.brownout_behavior == "auto_restart"
            else 0.0
        )
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
        if self.brownout_enabled and self.states["off_W"] != 0:
            raise ConfigurationError("Brownout rail-off approximation requires off_W: 0")
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
        self.brownout_latched = False
        self.brownout_elapsed_s = 0.0
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
        self.brownout_latched = False
        self.brownout_elapsed_s = 0.0

    @property
    def power_ready(self):
        return not self.brownout_latched or (
            self.brownout_behavior == "auto_restart"
            and self.brownout_elapsed_s >= self.restart_delay
        )

    def requires_brownout(self, voltage, supplied_fraction):
        if not self.brownout_enabled or self.state == PayloadState.OFF:
            return False
        return (self.minimum_voltage is not None and voltage < self.minimum_voltage) or (
            self.minimum_fraction is not None and supplied_fraction < self.minimum_fraction - 1e-9
        )

    def commit_service(self, dt_s, tripped):
        """Commit only after backend success; coarse tick-aligned rail-off/restart policy."""
        if tripped or not self.power_ready:
            if not self.brownout_latched or self.power_ready:
                self.brownout_elapsed_s = 0.0
            self.brownout_latched = True
            self.brownout_elapsed_s += dt_s
            return
        if self.brownout_latched:
            self.brownout_latched = False
            self.brownout_elapsed_s = 0.0
            self.elapsed_s = 0.0
        self.step(dt_s)

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
