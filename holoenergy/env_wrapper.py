"""Single-agent, direct-thruster wrapper. No changes or connections to HoloOcean core."""

from collections.abc import Mapping
from math import isclose

from ._validation import ConfigurationError, keys, number
from .config import load_config, model_warnings
from .logging import EnergyLogger
from .models.battery import make_battery
from .models.converters import ConverterModel
from .models.hotel_load import HotelLoad
from .models.payload import PayloadModel
from .models.power_manager import PowerManager
from .models.propulsion import PropulsionModel
from .models.thermal import IdealThermalModel, ThermalModel


class EnergyAwareEnv:
    def __init__(self, env, config_path=None, *, config=None, control_contract=None):
        self.env = env
        self.config = load_config(config_path, data=config)
        self.dt_s = self.config["simulation"]["dt_s"]
        manager = self.config.get("power_manager", {})
        keys(manager, {"apply_derating_to_actions"}, "power_manager")
        self.apply_derating = manager.get("apply_derating_to_actions", False)
        if not isinstance(self.apply_derating, bool):
            raise ConfigurationError("apply_derating_to_actions must be a boolean")
        self.battery = make_battery(self.config["battery"])
        thermal_type = IdealThermalModel if self.config["fidelity_level"] == "L0" else ThermalModel
        self.thermal = thermal_type(self.config["thermal"])
        self.propulsion = PropulsionModel(self.config["propulsion"])
        self.payload = PayloadModel(self.config.get("sensors", {}))
        if "hotel_load" not in self.config:
            raise ConfigurationError("Supply explicit hotel_load.constant_W (zero is allowed)")
        self.hotel = HotelLoad(self.config["hotel_load"])
        self.converters = ConverterModel(self.config.get("converters", {}))
        self.power_manager = PowerManager(
            self.battery, self.thermal, self.propulsion, self.converters
        )
        self.contract = control_contract or getattr(env, "energy_action_contract", None)
        self._validate_contract()
        self.warnings = model_warnings(self.config)
        if self.contract is None:
            self.warnings.append("Caller must verify direct-thruster units and simulation dt_s")
        for item in self.payload.components.values():
            if item.active_is_upper_bound:
                self.warnings.append(f"{item.name}.ACTIVE uses a datasheet maximum, not a mean")
        self.logger = EnergyLogger(
            self.config.get("logging", {}),
            self.config,
            self.warnings,
            context={
                "control_contract": self.contract,
                "backend_class": f"{type(env).__module__}.{type(env).__qualname__}",
            },
        )
        self.time_s = 0.0
        self.episode = 0
        self.step_index = 0
        self._faulted = False
        self._closed = False

    def _validate_contract(self):
        agents = getattr(self.env, "agents", None)
        if isinstance(agents, Mapping) and len(agents) > 1:
            raise ConfigurationError(
                "v0.1 supports one controlled agent; multi-agent energy is unsupported"
            )
        actual = getattr(self.env, "energy_action_contract", None)
        if actual is not None and self.contract is not None and actual != self.contract:
            raise ConfigurationError("Environment and supplied control contracts disagree")
        contract = actual or self.contract
        if self.apply_derating and contract is None:
            raise ConfigurationError(
                "Action derating requires control_contract (or env.energy_action_contract) "
                "with agent_type, control_scheme, action_units, thruster_count and dt_s"
            )
        if contract is None:
            return
        expected = self.config["simulation"]
        if type(self.env).__module__.startswith("holoocean.") and isinstance(agents, Mapping):
            if len(agents) != 1:
                raise ConfigurationError(
                    "Reset HoloOcean before wrapping a single controlled agent"
                )
            agent = next(iter(agents.values()))
            expected_type = expected.get("expected_agent_type", contract.get("agent_type"))
            if expected_type and type(agent).__name__ != expected_type:
                raise ConfigurationError("Runtime HoloOcean agent type does not match the contract")
        checks = {
            "action_units": self.propulsion.units,
            "thruster_count": self.propulsion.count,
        }
        if "expected_agent_type" in expected:
            checks["agent_type"] = expected["expected_agent_type"]
        if "control_scheme" in expected:
            checks["control_scheme"] = expected["control_scheme"]
        if "agent_name" in expected:
            checks["agent_name"] = expected["agent_name"]
        for name, value in checks.items():
            if contract.get(name) != value:
                raise ConfigurationError(f"Control contract mismatch: {name} must be {value}")
        if not isclose(contract.get("dt_s", -1), self.dt_s, rel_tol=1e-9):
            raise ConfigurationError("Control contract dt_s does not match simulation.dt_s")
        if contract.get("agent_type") == "BlueROV2" and (
            contract.get("control_scheme") != 0
            or self.propulsion.count != 8
            or self.propulsion.units != "force_N"
        ):
            raise ConfigurationError("BlueROV2 integration requires scheme 0 and eight forces in N")

    def _backend_action_limit(self, action):
        """Respect public simulator bounds before estimating applied thruster loads."""
        space = getattr(self.env, "action_space", None)
        if space is None:
            return 1.0
        if tuple(space.shape) != (self.propulsion.count,):
            raise ConfigurationError(
                "Runtime action space is not the configured direct thruster vector"
            )
        low, high = space.get_low(), space.get_high()
        if low is None or high is None:
            return 1.0
        if isinstance(low, (int, float)):
            low = [low] * self.propulsion.count
        if isinstance(high, (int, float)):
            high = [high] * self.propulsion.count
        if len(low) != self.propulsion.count or len(high) != self.propulsion.count:
            raise ConfigurationError("Simulator action bounds must match the thruster count")
        factor = 1.0
        for a, lo, hi in zip(action, low, high, strict=True):
            lo = number(float(lo), "simulator action lower bound", maximum=0)
            hi = number(float(hi), "simulator action upper bound", minimum=0)
            if a > 0:
                factor = min(factor, hi / a)
            elif a < 0:
                factor = min(factor, lo / a)
        return factor

    @staticmethod
    def _action_like(original, values):
        if hasattr(original, "dtype") and hasattr(original, "copy"):
            # Keep floating precision even if caller passed an integer numpy array.
            return original.astype(float, copy=True) * 0 + values
        if isinstance(original, tuple):
            return tuple(values)
        return list(values)

    def set_payload_state(self, name, state):
        self.payload.set_state(name, state)

    def _one_tick(self, action, original, kwargs):
        self._validate_contract()
        dt, t = self.dt_s, self.thermal.temperature_C
        sensor_requested = self.payload.preview(dt)
        sensor_demand = dict(sensor_requested)
        disconnected = {
            name for name, item in self.payload.components.items() if not item.power_ready
        }
        for name in disconnected:
            sensor_requested[name] = 0.0
        plan = self.power_manager.plan(
            action,
            sum(sensor_requested.values()),
            self.hotel.power_W,
            dt,
            action_factor_limit=self._backend_action_limit(action),
        )
        # Monotone shedding: never reconnect a tripped rail within the same tick.
        for _ in range(len(sensor_requested)):
            tripped = {
                name
                for name, item in self.payload.components.items()
                if name not in disconnected
                and item.requires_brownout(plan.voltage_V, plan.auxiliary_service_factor)
            }
            if not tripped:
                break
            disconnected.update(tripped)
            for name in tripped:
                sensor_requested[name] = 0.0
            plan = self.power_manager.plan(
                action,
                sum(sensor_requested.values()),
                self.hotel.power_W,
                dt,
                action_factor_limit=self._backend_action_limit(action),
            )
        outgoing = self._action_like(original, plan.action) if self.apply_derating else original
        try:
            state = self.env.step(outgoing, **kwargs)
        except Exception:
            self._faulted = True
            raise
        if not isinstance(state, Mapping):
            self._faulted = True
            raise TypeError("HoloEnergy requires an environment returning a state mapping")
        if "Energy" in state:
            self._faulted = True
            raise ValueError(
                "Environment already contains an Energy key; do not nest energy wrappers"
            )
        if self.thermal.critical:
            self.battery.mark_cutoff("temperature")
        limits = {
            "thermal_factor": self.thermal.derating_factor,
            "thermal_current_limit": self.thermal.current_limit(
                self.battery.resistance(t), self.battery.entropy(), dt
            ),
        }
        point = self.battery.step(plan.power_W, dt, t, **limits)
        self.thermal.step(point.heat_W, dt)
        for name, item in self.payload.components.items():
            item.commit_service(dt, name in disconnected)
        if self.thermal.critical:
            self.battery.mark_cutoff("temperature")
        if hasattr(self.battery, "cutoff_V") and point.current_A > 0:
            end_voltage = self.battery.ocv(self.thermal.temperature_C) - (
                point.current_A * self.battery.resistance(self.thermal.temperature_C)
            )
            if end_voltage <= self.battery.cutoff_V + 1e-10:
                self.battery.mark_cutoff("voltage")
        self.time_s += dt
        served_sensors = {
            name: power * plan.auxiliary_service_factor for name, power in sensor_requested.items()
        }
        state_name = "NORMAL"
        limited = plan.factor < 1 - 1e-9 or plan.auxiliary_service_factor < 1 - 1e-9
        if self.battery.cutoff:
            state_name = "CUTOFF"
        elif self.thermal.derating_factor < 1:
            state_name = "THERMAL_DERATING"
        elif limited:
            state_name = "POWER_LIMITED"
        elif self.battery.soc <= self.battery.low_soc_threshold:
            state_name = "LOW_SOC"
        applied = plan.action if self.apply_derating else action
        row = {
            "run_id": self.logger.run_id,
            "fidelity_level": self.config["fidelity_level"],
            "episode": self.episode,
            "step": self.step_index,
            "time_s": self.time_s,
            "dt_s": dt,
            "soc": self.battery.soc,
            "available_soc": self.battery.available_soc(self.thermal.temperature_C),
            "voltage_V": point.voltage_V,
            "current_A": point.current_A,
            "power_total_W": point.power_W,
            "power_propulsion_W": sum(plan.thruster_power_W),
            "power_payload_W": sum(served_sensors.values()),
            "power_hotel_W": plan.hotel_power_W,
            "power_conversion_loss_W": plan.conversion_loss_W,
            "power_battery_loss_W": point.resistive_loss_W,
            "heat_generated_W": point.heat_W,
            "requested_power_W": plan.requested_power_W
            + sum(sensor_demand[name] for name in disconnected) / self.converters.payload,
            "available_power_W": plan.available_power_W,
            "unmet_power_W": max(0, plan.requested_power_W - point.power_W)
            + sum(sensor_demand[name] for name in disconnected) / self.converters.payload,
            "temperature_C": self.thermal.temperature_C,
            "water_temperature_C": self.thermal.ambient_C,
            "thermal_derating_factor": self.thermal.derating_factor,
            "minimum_voltage_V": point.voltage_V,
            "peak_current_A": point.current_A,
            "peak_temperature_C": self.thermal.temperature_C,
            "energy_used_Wh": self.battery.energy_used_Wh,
            "battery_internal_loss_Wh": self.battery.internal_loss_Wh,
            "chemical_energy_used_Wh": self.battery.chemical_energy_Wh,
            "derating_factor": plan.factor,
            "auxiliary_service_factor": plan.auxiliary_service_factor,
            "battery_state": state_name,
            "cutoff_reason": self.battery.cutoff_reason,
            "thruster_power_W": plan.thruster_power_W,
            "sensor_power_W": served_sensors,
            "sensor_states": {
                name: item.state.value for name, item in self.payload.components.items()
            },
            "sensor_power_status": {
                name: "BROWNOUT" if name in disconnected else "POWERED"
                for name in self.payload.components
            },
            "requested_action": action,
            "requested_power_is_capped": any(
                abs(a - b) > 1e-8
                for a, b in zip(
                    action, self.propulsion.bounded_request(action, point.voltage_V), strict=True
                )
            )
            if any(action)
            else False,
            "applied_action": applied,
            "actions_derated": self.apply_derating,
            "dynamics_energy_consistent": self.apply_derating
            or all(isclose(a, b, abs_tol=1e-9) for a, b in zip(action, plan.action, strict=True)),
            "temperature_outside_calibration": self.battery.temperature_outside_calibration(t),
            "model_warnings": self.warnings,
            "step_completed": True,
        }
        return dict(state), row

    @staticmethod
    def _aggregate(rows, completed=True):
        row = dict(rows[-1])
        count = len(rows)
        for key in (
            "voltage_V",
            "current_A",
            "power_total_W",
            "power_propulsion_W",
            "power_payload_W",
            "power_hotel_W",
            "power_conversion_loss_W",
            "power_battery_loss_W",
            "heat_generated_W",
            "requested_power_W",
            "available_power_W",
            "unmet_power_W",
        ):
            row[key] = sum(r[key] for r in rows) / count
        row["dt_s"] = sum(r["dt_s"] for r in rows)
        row["derating_factor"] = min(r["derating_factor"] for r in rows)
        row["auxiliary_service_factor"] = min(r["auxiliary_service_factor"] for r in rows)
        row["thermal_derating_factor"] = min(r["thermal_derating_factor"] for r in rows)
        row["minimum_voltage_V"] = min(r["minimum_voltage_V"] for r in rows)
        row["peak_current_A"] = max(r["peak_current_A"] for r in rows)
        row["peak_temperature_C"] = max(r["peak_temperature_C"] for r in rows)
        row["thruster_power_W"] = [
            sum(r["thruster_power_W"][i] for r in rows) / count
            for i in range(len(row["thruster_power_W"]))
        ]
        row["sensor_power_W"] = {
            name: sum(r["sensor_power_W"][name] for r in rows) / count
            for name in row["sensor_power_W"]
        }
        row["dynamics_energy_consistent"] = all(r["dynamics_energy_consistent"] for r in rows)
        row["requested_power_is_capped"] = any(r["requested_power_is_capped"] for r in rows)
        row["temperature_outside_calibration"] = any(
            r["temperature_outside_calibration"] for r in rows
        )
        row["step_completed"] = completed
        return row

    def step(self, action, ticks=1, **kwargs):
        if self._closed:
            raise RuntimeError("EnergyAwareEnv is closed")
        if self._faulted:
            raise RuntimeError("Environment advancement failed; reset before stepping again")
        if isinstance(ticks, bool) or not isinstance(ticks, int) or ticks <= 0:
            raise ValueError("ticks must be a positive integer")
        values = self.propulsion.validate_action(action)
        self.step_index += 1
        rows = []
        try:
            for _ in range(ticks):
                state, row = self._one_tick(values, action, kwargs)
                rows.append(row)
        except Exception as exc:
            if rows:
                self.logger.write(self._aggregate(rows, completed=False))
            self.logger.mark_failure(exc)
            raise
        row = self._aggregate(rows)
        self.logger.write(row)
        state["Energy"] = row
        return state

    def reset(self, *args, **kwargs):
        if self._closed:
            raise RuntimeError("EnergyAwareEnv is closed")
        state = self.env.reset(*args, **kwargs)
        self.battery.reset()
        self.thermal.reset()
        self.payload.reset()
        self.hotel.reset()
        self.time_s = 0.0
        self.step_index = 0
        self.episode += 1
        self._faulted = False
        return state

    def close(self):
        if not self._closed:
            self.logger.close()
            close = getattr(self.env, "close", None)
            if close is not None:
                close()
            elif getattr(self.env, "__exit__", None) is not None:
                self.env.__exit__(None, None, None)
            self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    def __getattr__(self, name):
        if name in {"tick", "act", "set_ticks_per_sec"}:
            raise AttributeError(
                f"Use EnergyAwareEnv.step; {name} would bypass energy/timing accounting"
            )
        return getattr(self.env, name)
