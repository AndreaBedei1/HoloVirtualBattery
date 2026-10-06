"""Lumped pack heat balance: sources S1/S2 in docs/scientific_sources.md."""

from math import exp, expm1, sqrt

from .._validation import keys, number, required, timestep


class ThermalModel:
    def __init__(self, config):
        keys(
            config,
            {
                "water_temperature_C",
                "initial_temperature_C",
                "thermal_capacity_J_per_C",
                "cooling_coeff_W_per_C",
                "derating_temperature_C",
                "cutoff_temperature_C",
                "minimum_temperature_C",
            },
            "thermal",
        )
        self.ambient_C = number(
            required(config, "water_temperature_C"), "water_temperature_C", minimum=-273.14
        )
        self.initial_C = number(
            required(config, "initial_temperature_C"), "initial_temperature_C", minimum=-273.14
        )
        self.capacity = number(
            required(config, "thermal_capacity_J_per_C"), "thermal_capacity_J_per_C", positive=True
        )
        self.cooling = number(
            required(config, "cooling_coeff_W_per_C"), "cooling_coeff_W_per_C", minimum=0
        )
        self.derating_C = number(
            required(config, "derating_temperature_C"), "derating_temperature_C", minimum=-273.14
        )
        self.cutoff_C = number(
            required(config, "cutoff_temperature_C"),
            "cutoff_temperature_C",
            minimum=self.derating_C,
        )
        if self.cutoff_C == self.derating_C:
            raise ValueError("Thermal cutoff must exceed derating threshold")
        minimum = config.get("minimum_temperature_C")
        self.minimum_C = (
            None
            if minimum is None
            else number(minimum, "minimum_temperature_C", minimum=-273.14, maximum=self.derating_C)
        )
        self.temperature_C = self.initial_C

    def reset(self):
        self.temperature_C = self.initial_C

    @property
    def critical(self):
        return self.temperature_C >= self.cutoff_C - 1e-10 or (
            self.minimum_C is not None and self.temperature_C < self.minimum_C
        )

    @property
    def derating_factor(self):
        if self.critical:
            return 0.0
        if self.temperature_C <= self.derating_C:
            return 1.0
        return (self.cutoff_C - self.temperature_C) / (self.cutoff_C - self.derating_C)

    def step(self, heat_W, dt_s):
        """Exact solution for heat/cooling held constant over one interval.

        Negative heat is allowed for an experimentally supplied entropic term.
        """
        heat = number(heat_W, "heat_W")
        dt = timestep(dt_s)
        if self.cooling == 0:
            self.temperature_C += heat * dt / self.capacity
        else:
            decay = exp(-self.cooling * dt / self.capacity)
            self.temperature_C = (
                self.ambient_C
                + (self.temperature_C - self.ambient_C) * decay
                + heat / self.cooling * (-expm1(-self.cooling * dt / self.capacity))
            )
        return self.temperature_C

    def current_limit(self, resistance, entropy_V_per_K, dt_s):
        """Anticipate the cutoff at the end of the interval, avoiding overshoot."""
        dt = timestep(dt_s)
        if self.critical:
            return 0.0
        if self.cooling == 0:
            heat_limit = self.capacity * (self.cutoff_C - self.temperature_C) / dt
        else:
            decay = exp(-self.cooling * dt / self.capacity)
            heat_limit = (
                self.cooling
                * (self.cutoff_C - self.ambient_C - (self.temperature_C - self.ambient_C) * decay)
                / (-expm1(-self.cooling * dt / self.capacity))
            )
        heat_limit = max(0.0, heat_limit)
        a = (self.temperature_C + 273.15) * entropy_V_per_K
        if resistance == 0:
            return heat_limit / (-a) if a < 0 else float("inf")
        # R I² - T*(dU/dT)*I <= heat_limit; positive root.
        return (a + sqrt(a * a + 4 * resistance * heat_limit)) / (2 * resistance)
