"""Discharge-only L0 / Rint L1 models. Equations: scientific_sources.md S1–S5."""

from dataclasses import dataclass
from math import sqrt

from .._validation import ConfigurationError, curve, interpolate, keys, number, required, timestep


@dataclass(frozen=True)
class BatteryPoint:
    voltage_V: float
    current_A: float
    power_W: float
    heat_W: float
    resistive_loss_W: float
    chemical_power_W: float
    requested_power_W: float


class RintBattery:
    """Reference coulomb-counted SOC; temperature affects accessible charge.

    Q_available = Q_ref * max(0, SOC_ref - (1-f_capacity(T))).
    This reversible unavailable-charge convention avoids creating/deleting
    charge when temperature changes. Its accessible tail requires calibration.
    """

    def __init__(self, config):
        keys(
            config,
            {
                "model",
                "capacity_Ah",
                "nominal_voltage_V",
                "initial_soc",
                "internal_resistance_ohm",
                "cutoff_voltage_V",
                "max_current_A",
                "max_power_W",
                "ocv_curve",
                "ocv_temperature_curves",
                "capacity_temperature_curve",
                "resistance_temperature_curve",
                "resistance_soc_temperature_curves",
                "max_current_temperature_curve",
                "entropy_curve_V_per_K",
                "low_soc_threshold",
            },
            "Rint battery",
        )
        if config.get("model") != "rint":
            raise ConfigurationError("RintBattery requires model: rint")
        self.capacity_Ah = number(required(config, "capacity_Ah"), "capacity_Ah", positive=True)
        self.nominal_V = number(
            required(config, "nominal_voltage_V"), "nominal_voltage_V", positive=True
        )
        self.initial_soc = number(
            required(config, "initial_soc"), "initial_soc", minimum=0, maximum=1
        )
        self.resistance_tables = []
        for table in config.get("resistance_soc_temperature_curves", []):
            keys(table, {"temperature_C", "curve"}, "resistance temperature table")
            t = number(required(table, "temperature_C"), "temperature_C", minimum=-273.14)
            points = curve(required(table, "curve"), "resistance SOC curve", y_min=0)
            if len(points) < 2 or points[0][0] != 0 or points[-1][0] != 1:
                raise ConfigurationError("Resistance SOC curves must span SOC [0,1]")
            if self.resistance_tables:
                if t <= self.resistance_tables[-1][0]:
                    raise ConfigurationError("Resistance temperatures must be strictly increasing")
                if [p[0] for p in points] != [p[0] for p in self.resistance_tables[0][1]]:
                    raise ConfigurationError("Resistance tables require a common SOC grid")
            self.resistance_tables.append((t, points))
        self.resistance_ref = (
            0.0
            if self.resistance_tables
            else number(
                required(config, "internal_resistance_ohm"), "internal_resistance_ohm", minimum=0
            )
        )
        self.cutoff_V = number(
            required(config, "cutoff_voltage_V"), "cutoff_voltage_V", positive=True
        )
        self.max_current_A = number(
            required(config, "max_current_A"), "max_current_A", positive=True
        )
        limit = config.get("max_power_W")
        self.max_power_W = (
            float("inf") if limit is None else number(limit, "max_power_W", positive=True)
        )
        self.low_soc_threshold = number(
            config.get("low_soc_threshold", 0.2), "low_soc_threshold", minimum=0, maximum=1
        )
        self.ocv_curve = self._ocv(required(config, "ocv_curve"))
        self.ocv_tables = []
        for table in config.get("ocv_temperature_curves", []):
            keys(table, {"temperature_C", "curve"}, "OCV temperature table")
            t = number(required(table, "temperature_C"), "temperature_C", minimum=-273.14)
            if self.ocv_tables and t <= self.ocv_tables[-1][0]:
                raise ConfigurationError("OCV temperatures must be strictly increasing")
            self.ocv_tables.append((t, self._ocv(required(table, "curve"))))
        self.capacity_curve = curve(
            config.get("capacity_temperature_curve", [[25, 1]]),
            "capacity_temperature_curve",
            positive=True,
            y_max=1,
        )
        self.resistance_curve = curve(
            config.get("resistance_temperature_curve", [[25, 1]]),
            "resistance_temperature_curve",
            positive=True,
        )
        self.current_curve = curve(
            config.get("max_current_temperature_curve", [[25, 1]]),
            "max_current_temperature_curve",
            y_min=0,
            y_max=1,
        )
        entropy = config.get("entropy_curve_V_per_K")
        self.entropy_curve = None if entropy is None else curve(entropy, "entropy_curve_V_per_K")
        if self.entropy_curve and (self.entropy_curve[0][0] != 0 or self.entropy_curve[-1][0] != 1):
            raise ConfigurationError("Entropy curve must span SOC [0,1]")
        self.reset()

    @staticmethod
    def _ocv(data):
        points = curve(data, "ocv_curve", positive=True)
        if len(points) < 2 or points[0][0] != 0 or points[-1][0] != 1:
            raise ConfigurationError("OCV curve must span SOC [0,1]")
        if any(b[1] < a[1] for a, b in zip(points, points[1:], strict=False)):
            raise ConfigurationError("Discharge OCV must be nondecreasing with SOC")
        return points

    def reset(self):
        self.soc = self.initial_soc
        self.energy_used_Wh = 0.0
        self.internal_loss_Wh = 0.0
        self.chemical_energy_Wh = 0.0
        self.cutoff = False
        self.cutoff_reason = None

    def mark_cutoff(self, reason):
        self.cutoff = True
        self.cutoff_reason = reason

    def ocv(self, temperature_C):
        if not self.ocv_tables:
            return interpolate(self.ocv_curve, self.soc)
        return interpolate(
            tuple((t, interpolate(points, self.soc)) for t, points in self.ocv_tables),
            temperature_C,
        )

    def resistance(self, temperature_C):
        if self.resistance_tables:
            return interpolate(
                tuple((t, interpolate(points, self.soc)) for t, points in self.resistance_tables),
                temperature_C,
            )
        return self.resistance_ref * interpolate(self.resistance_curve, temperature_C)

    def entropy(self):
        return 0.0 if self.entropy_curve is None else interpolate(self.entropy_curve, self.soc)

    def available_charge_Ah(self, temperature_C):
        factor = interpolate(self.capacity_curve, temperature_C)
        return self.capacity_Ah * max(0, self.soc - (1 - factor))

    def available_soc(self, temperature_C):
        return self.available_charge_Ah(temperature_C) / (
            self.capacity_Ah * interpolate(self.capacity_curve, temperature_C)
        )

    def current_limit(
        self, temperature_C, dt_s, *, thermal_factor=1.0, thermal_current_limit=float("inf")
    ):
        dt = timestep(dt_s)
        number(temperature_C, "temperature_C", minimum=-273.14)
        number(thermal_factor, "thermal_factor", minimum=0, maximum=1)
        if self.cutoff:
            return 0.0
        u, r = self.ocv(temperature_C), self.resistance(temperature_C)
        # Only the stable, high-voltage branch of P = I(U-IR) is permitted.
        if u <= self.cutoff_V:
            return 0.0
        charge = self.available_charge_Ah(temperature_C)
        if charge <= 1e-12:
            return 0.0
        limit = min(
            self.max_current_A * interpolate(self.current_curve, temperature_C) * thermal_factor,
            charge * 3600 / dt,
            thermal_current_limit,
        )
        if r > 0:
            limit = min(limit, u / (2 * r), (u - self.cutoff_V) / r)
        if limit < 0:
            raise ValueError("thermal_current_limit must be nonnegative")
        if limit * (u - limit * r) > self.max_power_W:
            limit = self.current_for_power(self.max_power_W, temperature_C)
        return limit

    def current_for_power(self, power_W, temperature_C):
        power = number(power_W, "power_W", minimum=0)
        u, r = self.ocv(temperature_C), self.resistance(temperature_C)
        if power == 0:
            return 0.0
        if r == 0:
            return power / u
        discriminant = u * u - 4 * r * power
        if discriminant < -1e-10 * u * u:
            raise ValueError("Requested power has no real high-voltage Rint solution")
        discriminant = max(0.0, discriminant)
        # Algebraically stable root for small powers.
        return 2 * power / (u + sqrt(discriminant))

    def available_power(self, temperature_C, dt_s, **limits):
        i = self.current_limit(temperature_C, dt_s, **limits)
        return i * (self.ocv(temperature_C) - i * self.resistance(temperature_C))

    def step(self, power_W, dt_s, temperature_C=25.0, **limits):
        dt = timestep(dt_s)
        requested = number(power_W, "power_W", minimum=0)
        power = min(requested, self.available_power(temperature_C, dt, **limits))
        u, r = self.ocv(temperature_C), self.resistance(temperature_C)
        i = self.current_for_power(power, temperature_C)
        v = u - i * r
        loss = i * i * r
        heat = loss - i * (temperature_C + 273.15) * self.entropy()
        self.soc = max(0.0, self.soc - i * dt / (3600 * self.capacity_Ah))
        self.energy_used_Wh += power * dt / 3600
        self.internal_loss_Wh += loss * dt / 3600
        self.chemical_energy_Wh += u * i * dt / 3600
        # Terminal voltage is a start-of-interval point; test end state separately.
        if self.available_charge_Ah(temperature_C) <= 1e-12:
            self.mark_cutoff("available_charge")
        elif self.ocv(temperature_C) - i * self.resistance(temperature_C) <= self.cutoff_V + 1e-10:
            self.mark_cutoff("voltage")
        return BatteryPoint(v, i, power, heat, loss, u * i, requested)

    def temperature_outside_calibration(self, temperature_C):
        tables = [self.capacity_curve, self.resistance_curve, self.current_curve]
        if self.ocv_tables:
            tables.append(self.ocv_tables)
        if self.resistance_tables:
            if not self.resistance_tables[0][0] <= temperature_C <= self.resistance_tables[-1][0]:
                return True
            tables.remove(self.resistance_curve)
        return any(not p[0][0] <= temperature_C <= p[-1][0] for p in tables)


class EnergyBucketBattery:
    """Ideal constant-voltage bucket: no sag or resistive heating (L0)."""

    def __init__(self, config):
        keys(
            config,
            {
                "model",
                "capacity_Wh",
                "nominal_voltage_V",
                "initial_soc",
                "max_current_A",
                "max_power_W",
                "low_soc_threshold",
            },
            "L0 battery",
        )
        if config.get("model") != "energy_bucket":
            raise ConfigurationError("EnergyBucketBattery requires model: energy_bucket")
        self.capacity_Wh = number(required(config, "capacity_Wh"), "capacity_Wh", positive=True)
        self.nominal_V = number(
            required(config, "nominal_voltage_V"), "nominal_voltage_V", positive=True
        )
        self.initial_soc = number(
            required(config, "initial_soc"), "initial_soc", minimum=0, maximum=1
        )
        self.max_current_A = number(
            required(config, "max_current_A"), "max_current_A", positive=True
        )
        p = config.get("max_power_W")
        self.max_power_W = float("inf") if p is None else number(p, "max_power_W", positive=True)
        self.low_soc_threshold = number(
            config.get("low_soc_threshold", 0.2), "low_soc_threshold", minimum=0, maximum=1
        )
        self.reset()

    reset = RintBattery.reset
    mark_cutoff = RintBattery.mark_cutoff

    def ocv(self, temperature_C):
        return self.nominal_V

    def resistance(self, temperature_C):
        return 0.0

    def entropy(self):
        return 0.0

    def available_soc(self, temperature_C):
        return self.soc

    def temperature_outside_calibration(self, temperature_C):
        return False

    def current_limit(
        self, temperature_C, dt_s, *, thermal_factor=1.0, thermal_current_limit=float("inf")
    ):
        dt = timestep(dt_s)
        number(thermal_factor, "thermal_factor", minimum=0, maximum=1)
        if self.cutoff or self.soc <= 0:
            return 0.0
        return min(
            self.max_current_A * thermal_factor,
            self.max_power_W / self.nominal_V,
            self.soc * self.capacity_Wh * 3600 / (dt * self.nominal_V),
            thermal_current_limit,
        )

    def available_power(self, temperature_C, dt_s, **limits):
        return self.nominal_V * self.current_limit(temperature_C, dt_s, **limits)

    def step(self, power_W, dt_s, temperature_C=25.0, **limits):
        dt = timestep(dt_s)
        requested = number(power_W, "power_W", minimum=0)
        power = min(requested, self.available_power(temperature_C, dt, **limits))
        energy = power * dt / 3600
        self.energy_used_Wh += energy
        self.chemical_energy_Wh += energy
        self.soc = max(0.0, self.soc - energy / self.capacity_Wh)
        if self.soc <= 1e-12:
            self.mark_cutoff("available_energy")
        return BatteryPoint(self.nominal_V, power / self.nominal_V, power, 0, 0, power, requested)


def make_battery(config):
    if config.get("model") == "rint":
        return RintBattery(config)
    if config.get("model") == "energy_bucket":
        return EnergyBucketBattery(config)
    raise ConfigurationError("battery.model must be energy_bucket or rint (L0/L1)")
