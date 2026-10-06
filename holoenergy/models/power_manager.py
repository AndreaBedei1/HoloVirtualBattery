"""Couple nonlinear loads to the battery; shed propulsion before auxiliaries."""

from dataclasses import dataclass

from .converters import ConverterModel


@dataclass(frozen=True)
class PowerPlan:
    action: list[float]
    factor: float
    voltage_V: float
    current_A: float
    power_W: float
    requested_power_W: float
    available_power_W: float
    thruster_power_W: list[float]
    payload_power_W: float
    hotel_power_W: float
    conversion_loss_W: float
    auxiliary_service_factor: float


class PowerManager:
    def __init__(self, battery, thermal, propulsion, converters=None):
        self.battery = battery
        self.thermal = thermal
        self.propulsion = propulsion
        self.converters = converters or ConverterModel({})

    def plan(self, action, payload_W, hotel_W, dt_s):
        t = self.thermal.temperature_C
        u = self.battery.ocv(t)
        r = self.battery.resistance(t)
        thermal_current = self.thermal.current_limit(r, self.battery.entropy(), dt_s)
        i_max = self.battery.current_limit(
            t,
            dt_s,
            thermal_factor=self.thermal.derating_factor,
            thermal_current_limit=thermal_current,
        )
        # For nonzero propulsion, keep all coupled evaluations inside the measured domain.
        if any(action):
            if u > self.propulsion.max_voltage + 1e-9:
                raise ValueError("Battery OCV exceeds the thruster profile voltage range")
            if u < self.propulsion.min_voltage:
                force_factor = 0.0
            else:
                if r > 0:
                    i_max = min(i_max, max(0, (u - self.propulsion.min_voltage) / r))
                force_factor = 1.0
        else:
            force_factor = 1.0
        v_min = u - i_max * r
        available = i_max * v_min
        c = self.converters
        fixed = c.input_power(0, payload_W, hotel_W)
        requested_prop = sum(self.propulsion.powers(action, u)) if force_factor else 0.0
        requested = c.input_power(requested_prop, payload_W, hotel_W)
        if available <= 0:
            return PowerPlan(
                [0.0] * len(action),
                0.0,
                u,
                0.0,
                0.0,
                requested,
                0.0,
                [0.0] * len(action),
                0.0,
                0.0,
                0.0,
                0.0,
            )
        if fixed > available:
            # Fractional service is an accounting approximation, not a brownout/reboot model.
            service = available / fixed
            requested = (
                c.input_power(sum(self.propulsion.powers(action, v_min)), payload_W, hotel_W)
                if force_factor
                else fixed
            )
            return PowerPlan(
                [0.0] * len(action),
                0.0,
                v_min,
                i_max,
                available,
                requested,
                available,
                [0.0] * len(action),
                payload_W * service,
                hotel_W * service,
                available - (payload_W + hotel_W) * service,
                service,
            )
        upper = self.propulsion.max_action_factor(action, v_min) if force_factor else 0.0

        def load_at(factor, voltage):
            powers = self.propulsion.powers([a * factor for a in action], voltage)
            return c.input_power(sum(powers), payload_W, hotel_W)

        factor = upper
        if load_at(upper, v_min) > available:
            low, high = 0.0, upper
            for _ in range(36):
                mid = (low + high) / 2
                if load_at(mid, v_min) <= available:
                    low = mid
                else:
                    high = mid
            factor = low
        scaled = [a * factor for a in action]
        # Solve P_load(V(I)) = I*(U-I*R) on the permitted high-voltage branch.
        low, high = 0.0, i_max
        for _ in range(40):
            mid = (low + high) / 2
            voltage = u - mid * r
            if load_at(factor, voltage) > mid * voltage:
                low = mid
            else:
                high = mid
        current = (low + high) / 2
        voltage = u - current * r
        powers = self.propulsion.powers(scaled, voltage)
        power = c.input_power(sum(powers), payload_W, hotel_W)
        requested = (
            c.input_power(sum(self.propulsion.powers(action, voltage)), payload_W, hotel_W)
            if force_factor
            else fixed
        )
        return PowerPlan(
            scaled,
            factor,
            voltage,
            current,
            power,
            requested,
            available,
            powers,
            payload_W,
            hotel_W,
            power - sum(powers) - payload_W - hotel_W,
            1.0,
        )
