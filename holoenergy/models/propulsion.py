"""Voltage-dependent bidirectional measured thruster tables (source S6).

Force input uses inverse force->electrical power lookup. Normalized input uses
ESC PWM convention from the selected profile, not an arbitrary cubic law.
"""

from bisect import bisect_left

from .._validation import ConfigurationError, curve, interpolate, keys, number, required
from .actuator import make_actuator


class ThrusterModel:
    def __init__(self, config):
        keys(config, {"model", "voltage_tables"}, "thruster profile")
        self.name = required(config, "model")
        self.tables = []
        raw = required(config, "voltage_tables")
        for table in raw:
            keys(table, {"voltage_V", "forward", "reverse"}, "thruster voltage table")
            v = number(required(table, "voltage_V"), "voltage_V", positive=True)
            if self.tables and v <= self.tables[-1][0]:
                raise ConfigurationError("Thruster voltages must be strictly increasing")
            directions = {}
            for direction in ("forward", "reverse"):
                rows = required(table, direction)
                for row in rows:
                    keys(row, {"command", "force_N", "power_W"}, f"thruster {direction}")
                cmd_power = curve(
                    [[r["command"], r["power_W"]] for r in rows], "command-power curve", y_min=0
                )
                cmd_force = curve(
                    [[r["command"], r["force_N"]] for r in rows], "command-force curve", y_min=0
                )
                if cmd_power[0] != (0, 0) or cmd_force[0] != (0, 0):
                    raise ConfigurationError(
                        "Thruster curves must start at zero command/force/power"
                    )
                if cmd_power[-1][0] != 1:
                    raise ConfigurationError("Thruster commands must span [0,1]")
                if any(b[1] < a[1] for a, b in zip(cmd_power, cmd_power[1:], strict=False)) or any(
                    b[1] < a[1] for a, b in zip(cmd_force, cmd_force[1:], strict=False)
                ):
                    raise ConfigurationError("Thruster power and force must be nondecreasing")
                # Zero-thrust deadband must have zero propulsion power; ESC idle is hotel load.
                force_power = {}
                for (_, f), (_, p) in zip(cmd_force, cmd_power, strict=True):
                    force_power[f] = max(force_power.get(f, 0), p)
                if force_power.get(0) != 0 or cmd_force[-1][1] <= 0:
                    raise ConfigurationError(
                        "Thruster requires positive max force and zero idle power"
                    )
                directions[direction] = {
                    "command_power": cmd_power,
                    "command_force": cmd_force,
                    "force_power": tuple(sorted(force_power.items())),
                    "max_force": cmd_force[-1][1],
                }
            self.tables.append((v, directions))
        if not self.tables:
            raise ConfigurationError("Thruster profile needs at least one voltage table")
        self.min_voltage = self.tables[0][0]
        self.max_voltage = self.tables[-1][0]

    def _voltage_check(self, voltage):
        number(voltage, "thruster voltage", positive=True)
        if not self.min_voltage - 1e-9 <= voltage <= self.max_voltage + 1e-9:
            raise ValueError(
                f"{self.name}: voltage {voltage:g} V outside measured range "
                f"[{self.min_voltage:g}, {self.max_voltage:g}]"
            )

    def _bracket(self, voltage):
        index = bisect_left([v for v, _ in self.tables], voltage)
        if index == len(self.tables):
            return self.tables[-1:]
        if index == 0 or abs(self.tables[index][0] - voltage) < 1e-9:
            return self.tables[index : index + 1]
        return self.tables[index - 1 : index + 1]

    def power(self, action, voltage, units="force_N"):
        if units not in ("force_N", "normalized_command"):
            raise ValueError("Unsupported thruster action units")
        if action == 0:
            return 0.0
        self._voltage_check(voltage)
        direction = "forward" if action > 0 else "reverse"
        maximum = self.max_force(voltage, direction) if units == "force_N" else 1.0
        if abs(action) > maximum + 1e-8:
            raise ValueError("Thruster action exceeds the measured force/command domain")
        key = "force_power" if units == "force_N" else "command_power"
        values = tuple(
            (v, interpolate(data[direction][key], abs(action)))
            for v, data in self._bracket(voltage)
        )
        return interpolate(values, voltage)

    def max_force(self, voltage, direction):
        self._voltage_check(voltage)
        # Inverse lookup requires force support in both bracketing voltage experiments.
        return min(data[direction]["max_force"] for _, data in self._bracket(voltage))

    def force(self, command, voltage):
        if command == 0:
            return 0.0
        self._voltage_check(voltage)
        direction = "forward" if command > 0 else "reverse"
        f = interpolate(
            tuple(
                (v, interpolate(data[direction]["command_force"], abs(command)))
                for v, data in self.tables
            ),
            voltage,
        )
        return f if command > 0 else -f


class PropulsionModel:
    def __init__(self, config):
        keys(
            config,
            {"thruster_count", "action_units", "thruster", "thrusters", "actuator_ids"},
            "propulsion",
        )
        count = required(config, "thruster_count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            raise ConfigurationError("thruster_count must be a positive integer")
        self.count = count
        self.units = required(config, "action_units")
        if self.units not in ("force_N", "normalized_command"):
            raise ConfigurationError("action_units must be force_N or normalized_command")
        if ("thruster" in config) == ("thrusters" in config):
            raise ConfigurationError("Supply exactly one of thruster or per-thruster thrusters")
        if "thruster" in config:
            shared = make_actuator(config["thruster"])
            self.thrusters = [shared] * count
        else:
            if len(config["thrusters"]) != count:
                raise ConfigurationError("thrusters length must equal thruster_count")
            self.thrusters = [make_actuator(t) for t in config["thrusters"]]
        self.actuators = self.thrusters
        self.ids = config.get("actuator_ids", [f"T{i + 1}" for i in range(count)])
        if (
            not isinstance(self.ids, list)
            or len(self.ids) != count
            or any(not isinstance(i, str) or not i for i in self.ids)
            or len(set(self.ids)) != count
        ):
            raise ConfigurationError("actuator_ids must be unique nonempty strings matching count")
        if self.units != "force_N" and any(getattr(t, "force_only", False) for t in self.thrusters):
            raise ConfigurationError("Force-only actuator data requires action_units: force_N")
        self.min_voltage = max(t.min_voltage for t in self.thrusters)
        self.max_voltage = min(t.max_voltage for t in self.thrusters)
        if self.min_voltage > self.max_voltage:
            raise ConfigurationError("Thruster voltage domains do not overlap")

    def validate_action(self, action):
        try:
            values = list(action)
        except TypeError as exc:
            raise ValueError("Action must be a direct per-thruster vector") from exc
        if len(values) != self.count:
            raise ValueError(f"Expected {self.count} direct thruster commands, got {len(values)}")
        # numpy scalar types can be converted here, but arrays/strings/bools are rejected.
        result = []
        for value in values:
            if isinstance(value, (str, bool)) or getattr(value, "ndim", 0) != 0:
                raise ValueError("Thruster commands must be scalar finite numbers")
            result.append(number(float(value), "thruster action"))
        if self.units == "normalized_command" and any(abs(v) > 1 for v in result):
            raise ValueError("Normalized thruster commands must lie in [-1,1]")
        return result

    def powers(self, action, voltage):
        return [
            t.power(a, voltage, self.units) for t, a in zip(self.thrusters, action, strict=True)
        ]

    def bounded_request(self, action, voltage):
        """Cap only an unattainable demand estimate; applied powers never extrapolate."""
        if self.units == "normalized_command":
            return list(action)
        return [
            max(
                -thruster.max_force(voltage, "reverse"),
                min(thruster.max_force(voltage, "forward"), a),
            )
            if a
            else 0.0
            for thruster, a in zip(self.thrusters, action, strict=True)
        ]

    def max_action_factor(self, action, voltage, voltage_max=None):
        factor = 1.0
        for thruster, a in zip(self.thrusters, action, strict=True):
            if a:
                limit = (
                    1.0
                    if self.units == "normalized_command"
                    else min(
                        thruster.max_force(v, "forward" if a > 0 else "reverse")
                        for v in [
                            voltage,
                            voltage_max or voltage,
                            *(
                                v
                                for v, _ in thruster.tables
                                if voltage <= v <= (voltage_max or voltage)
                            ),
                        ]
                    )
                )
                factor = min(factor, limit / abs(a))
        return factor
