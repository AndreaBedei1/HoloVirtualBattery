"""Single-agent, direct-thruster wrapper. No changes or connections to HoloOcean core."""

from collections.abc import Mapping
from contextlib import ExitStack
from math import isclose

from ._validation import ConfigurationError, keys, number
from .accounting import EnergyRuntime
from .config import load_config, model_warnings
from .logging import EnergyLogger
from .models.battery import make_battery
from .models.components import ComponentModel
from .models.converters import ConverterModel
from .models.hotel_load import HotelLoad
from .models.power_manager import PowerManager
from .models.propulsion import PropulsionModel
from .models.thermal import IdealThermalModel, ThermalModel
from .models.vehicle import VehicleProfile, vector3


class EnergyAwareEnv:
    def __init__(
        self,
        env,
        config_path=None,
        *,
        config=None,
        control_contract=None,
        dynamics_adapter=None,
        telemetry=None,
    ):
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
        if not self.propulsion.min_voltage <= self.battery.nominal_V <= self.propulsion.max_voltage:
            raise ConfigurationError(
                "Battery nominal_voltage_V is incompatible with the actuator voltage domain"
            )
        self.payload = ComponentModel(
            self.config.get("sensors", {}), self.config.get("components", [])
        )
        if "hotel_load" not in self.config:
            raise ConfigurationError("Supply explicit hotel_load.constant_W (zero is allowed)")
        self.hotel = HotelLoad(self.config["hotel_load"])
        self.converters = ConverterModel(self.config.get("converters", {}))
        self.power_manager = PowerManager(
            self.battery, self.thermal, self.propulsion, self.converters
        )
        self.contract = control_contract or getattr(env, "energy_action_contract", None)
        self._validate_contract()
        self.vehicle = VehicleProfile(self.config.get("vehicle", {}))
        self.dynamics_adapter = dynamics_adapter
        self.dynamics_status = "backend_owned"
        if self.vehicle.mode == "adapter":
            if dynamics_adapter is None or not callable(
                getattr(dynamics_adapter, "configure_vehicle", None)
            ):
                raise ConfigurationError(
                    "vehicle.dynamics_mode: adapter requires configure_vehicle(profile)"
                )
            dynamics_adapter.configure_vehicle(self.vehicle)
            self.dynamics_status = "applied_by_explicit_adapter"
        elif self.vehicle.has_physical_description:
            self.dynamics_status = "descriptive_only_not_applied"
        self.environment = {}
        initial_environment = self.config.get("environment", {})
        self.set_environment(**{k: v for k, v in initial_environment.items() if k != "metadata"})
        self.warnings = model_warnings(self.config)
        if self.dynamics_status == "descriptive_only_not_applied":
            self.warnings.append(
                "Vehicle/payload physical parameters are descriptive; dynamics backend must configure them"
            )
        hotel_names = set(self.hotel.components) | (
            {"hotel_constant"} if self.hotel.constant_W else set()
        )
        if (
            set(self.propulsion.ids) & (set(self.payload.components) | hotel_names)
            or set(self.payload.components) & hotel_names
        ):
            raise ConfigurationError("Actuator and component accounting IDs must not overlap")
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
        self.energy = EnergyRuntime(self)
        self.telemetry = telemetry
        if telemetry is None and self.config.get("telemetry", {}).get("enabled", False):
            from .telemetry import TelemetryPublisher

            self.telemetry = TelemetryPublisher.from_config(self.config["telemetry"])

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
        # Agent-specific action layouts belong to profiles/adapters. Runtime public
        # action bounds and the explicit direct-effort contract remain authoritative.

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

    def set_environment(self, **values):
        keys(
            values,
            {"water_temperature_C", "water_density_kg_m3", "current_velocity_m_s", "current_mode"},
            "environment update",
        )
        candidate = dict(self.environment)
        if "water_temperature_C" in values:
            candidate["water_temperature_C"] = number(
                values["water_temperature_C"], "water_temperature_C", minimum=-273.14
            )
        if "water_density_kg_m3" in values:
            candidate["water_density_kg_m3"] = number(
                values["water_density_kg_m3"], "water_density_kg_m3", positive=True
            )
        if "current_velocity_m_s" in values:
            candidate["current_velocity_m_s"] = vector3(
                values["current_velocity_m_s"], "current_velocity_m_s"
            )
        mode = values.get("current_mode", candidate.get("current_mode", "descriptive"))
        if mode not in ("descriptive", "native", "adapter"):
            raise ConfigurationError("current_mode must be descriptive, native or adapter")
        if self.environment.get("current_mode") in ("native", "adapter") and mode == "descriptive":
            raise ConfigurationError(
                "Cannot relabel an applied environment as descriptive; reset with an explicit backend contract"
            )
        candidate["current_mode"] = mode
        dynamics_values = {
            k: candidate[k]
            for k in ("current_velocity_m_s", "water_density_kg_m3")
            if k in values or (k in candidate and mode != self.environment.get("current_mode"))
        }
        if dynamics_values and mode == "adapter":
            setter = getattr(self.dynamics_adapter, "set_environment", None)
            if not callable(setter):
                raise ConfigurationError("Environment adapter requires set_environment(values)")
            setter(dynamics_values)
        elif dynamics_values and mode == "native":
            if "water_density_kg_m3" in dynamics_values:
                raise ConfigurationError(
                    "Native HoloOcean has no public water-density setter; use a dynamics adapter"
                )
            contract = self.contract or {}
            if contract.get("dynamics_mode") == "fossen":
                raise ConfigurationError(
                    "HoloOcean native currents are unsupported for Fossen; use an explicit adapter"
                )
            setter = getattr(self.env, "set_ocean_currents", None)
            name = contract.get("agent_name", self.config["simulation"].get("agent_name"))
            if not callable(setter) or not name:
                raise ConfigurationError(
                    "Native current requires public set_ocean_currents and an explicit agent_name"
                )
            setter(name, candidate["current_velocity_m_s"])
        self.environment = candidate
        if "water_temperature_C" in candidate:
            self.thermal.ambient_C = candidate["water_temperature_C"]

    def _vehicle_observation(self, state):
        """Only documented sensors or explicit SI VehicleState; absent channels stay null."""
        from math import sqrt

        result = {
            "linear_speed_m_s": None,
            "angular_speed_rad_s": None,
            "acceleration_m_s2": None,
            "depth_m": None,
        }
        explicit = state.get("VehicleState", {})
        if isinstance(explicit, Mapping):
            for key in result:
                if key in explicit and explicit[key] is not None:
                    result[key] = (
                        vector3(explicit[key], key)
                        if key == "acceleration_m_s2"
                        else number(float(explicit[key]), key)
                    )
        if result["linear_speed_m_s"] is None and "VelocitySensor" in state:
            velocity = state["VelocitySensor"]
            if len(velocity) == 3:
                result["linear_speed_m_s"] = sqrt(sum(float(v) ** 2 for v in velocity))
        if result["depth_m"] is None and "PoseSensor" in state:
            pose = state["PoseSensor"]
            result["depth_m"] = -float(pose[2][3])  # documented HoloOcean NWU frame
        if "DynamicsSensor" in state:
            dynamics = state["DynamicsSensor"]
            if len(dynamics) in (18, 19):
                if result["linear_speed_m_s"] is None:
                    result["linear_speed_m_s"] = sqrt(sum(float(v) ** 2 for v in dynamics[3:6]))
                if result["angular_speed_rad_s"] is None:
                    result["angular_speed_rad_s"] = sqrt(
                        sum(float(v) ** 2 for v in dynamics[12:15])
                    )
                if result["acceleration_m_s2"] is None:
                    result["acceleration_m_s2"] = [float(v) for v in dynamics[:3]]
                if result["depth_m"] is None:
                    result["depth_m"] = -float(dynamics[8])
        return result

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
        component_powers = dict(served_sensors)
        # Legacy aggregate hotel remains explicit and separate from user components.
        if self.hotel.constant_W:
            component_powers["hotel_constant"] = (
                self.hotel.constant_W * plan.auxiliary_service_factor
            )
        component_powers.update(
            {n: p * plan.auxiliary_service_factor for n, p in self.hotel.components.items()}
        )
        category_power = {
            k: sum(served_sensors[n] for n, c in self.payload.components.items() if c.category == k)
            for k in ("sensors", "compute", "auxiliaries")
        }
        row.update(
            power_sensors_W=category_power["sensors"],
            power_compute_W=category_power["compute"],
            power_auxiliary_W=category_power["auxiliaries"] + plan.hotel_power_W,
            component_power_W=component_powers,
            component_states={
                **row["sensor_states"],
                **{n: "ACTIVE" for n in component_powers if n not in served_sensors},
            },
            component_power_status=dict(row["sensor_power_status"]),
            actuator_power_W=dict(zip(self.propulsion.ids, plan.thruster_power_W, strict=True)),
            actuators={
                identity: {
                    "command": a,
                    "applied_effort": b,
                    "force_N": b
                    if self.propulsion.units == "force_N"
                    else thruster.force(b, point.voltage_V),
                    "power_W": p,
                    "action_units": self.propulsion.units,
                    "effort_kind": "submitted to backend; realized thrust not measured",
                }
                for identity, a, b, p, thruster in zip(
                    self.propulsion.ids,
                    action,
                    applied,
                    plan.thruster_power_W,
                    self.propulsion.thrusters,
                    strict=True,
                )
            },
            battery_temperature_C=self.thermal.temperature_C,
            remaining_energy_Wh=self.battery.remaining_energy_Wh(self.thermal.temperature_C),
            remaining_energy_basis="OCV work upper bound; load-dependent cutoff excluded"
            if self.config["fidelity_level"] == "L1"
            else "ideal energy storage",
            chemistry=self.battery.chemistry,
            environment=dict(self.environment),
            vehicle_dynamics_status=self.dynamics_status,
            **self._vehicle_observation(state),
        )
        self.energy.record(row)
        row["endurance_estimates"] = self.energy.endurance()
        if self.telemetry is not None:
            self.telemetry.publish(row)
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
            "power_sensors_W",
            "power_compute_W",
            "power_auxiliary_W",
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
        for key in ("component_power_W", "actuator_power_W"):
            row[key] = {name: sum(r[key][name] for r in rows) / count for name in row[key]}
        row["actuators"] = {
            name: {**item, "power_W": row["actuator_power_W"][name]}
            for name, item in row["actuators"].items()
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
        if self.vehicle.mode == "adapter":
            self.dynamics_adapter.configure_vehicle(self.vehicle)
        if self.energy.duration_s:
            self.energy.episodes.append(self.energy.summary())
        self.battery.reset()
        self.thermal.reset()
        self.payload.reset()
        self.hotel.reset()
        self.time_s = 0.0
        self.step_index = 0
        self.episode += 1
        self._faulted = False
        self.energy.reset()
        self.environment = {}
        self.set_environment(
            **{k: v for k, v in self.config["environment"].items() if k != "metadata"}
        )
        if self.telemetry is not None:
            self.telemetry.event("reset", episode=self.episode)
        return state

    def close(self):
        if not self._closed:
            self._closed = True
            with ExitStack() as cleanup:
                close = getattr(self.env, "close", None)
                if close is not None:
                    cleanup.callback(close)
                elif getattr(self.env, "__exit__", None) is not None:
                    cleanup.callback(self.env.__exit__, None, None, None)
                cleanup.callback(self.logger.close)
                if self.telemetry is not None:
                    cleanup.callback(self.telemetry.close)
                try:
                    summary = self.energy.summary()
                    self.logger.metadata["energy_summary"] = summary
                    if self.logger.path is not None:
                        self.energy.export_summary(str(self.logger.path) + ".summary.json")
                        self.energy.export_summary(str(self.logger.path) + ".summary.csv")
                    if self.telemetry is not None:
                        self.telemetry.event(
                            "end_mission", summary=summary, energy=self.energy.latest
                        )
                except Exception as exc:
                    self.logger.mark_failure(exc)
                    raise

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self.logger.mark_failure(exc)
        self.close()

    def __getattr__(self, name):
        if name in {"tick", "act", "set_ticks_per_sec"}:
            raise AttributeError(
                f"Use EnergyAwareEnv.step; {name} would bypass energy/timing accounting"
            )
        return getattr(self.env, name)
