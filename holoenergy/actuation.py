"""Action interface between a controller, the energy model and the dynamics backend.

Two action modes:

``thrusters`` (default, v0.1 behaviour)
    The caller submits one effort per configured actuator; the same vector is sent to
    the backend.
``wrench``
    The caller submits a body wrench ``[Fx, Fy, Fz, Mx, My, Mz]`` (N, N*m).  HoloEnergy
    allocates it over the *configured* actuator layout (arbitrary count and orientation),
    computes electrical power from the individual actuator forces, and maps the result
    to the backend:

    * ``direct``: the configured layout *is* the backend agent's actuator set; forces are
      reordered by ``backend_index`` and sent unchanged;
    * ``wrench_equivalent``: the configured layout is virtual (e.g. a 6-thruster
      BlueROV2 Standard emulated on HoloOcean's 8-thruster agent).  The wrench actually
      produced by the virtual actuators, ``B_virtual f``, is re-allocated on the native
      layout within the native clamp and sent to the backend.  The rigid body, mass and
      drag remain the native agent's; only the actuation layout differs.  Any residual
      between the virtual and native wrench is logged and marks the tick as
      dynamics/energy inconsistent.
"""

from __future__ import annotations

import numpy as np

from ._validation import ConfigurationError, keys, number
from .allocation import ActuatorGeometry, ThrustAllocator

WRENCH_TOLERANCE = 1e-6


class ActuationLayer:
    def __init__(self, propulsion, config=None):
        config = config or {}
        keys(config, {"action_mode", "geometry", "allocation", "backend"}, "actuation")
        self.propulsion = propulsion
        self.mode = config.get("action_mode", "thrusters")
        if self.mode not in ("thrusters", "wrench"):
            raise ConfigurationError("actuation.action_mode must be thrusters or wrench")
        geometry = config.get("geometry")
        self.geometry = None
        self.allocator = None
        if geometry is not None:
            if not isinstance(geometry, list) or len(geometry) != propulsion.count:
                raise ConfigurationError("actuation.geometry must list every configured actuator")
            items = [ActuatorGeometry.from_mapping(g) for g in geometry]
            if [g.id for g in items] != list(propulsion.ids):
                raise ConfigurationError("Geometry ids must match actuator ids in the same order")
            self.geometry = items
            allocation = config.get("allocation", {})
            keys(allocation, {"method", "weights", "dof_weights"}, "actuation.allocation")
            self.allocator = ThrustAllocator(
                items,
                method=allocation.get("method", "redistributed"),
                weights=allocation.get("weights"),
                dof_weights=allocation.get("dof_weights"),
            )
        if self.mode == "wrench" and self.allocator is None:
            raise ConfigurationError("action_mode: wrench requires actuation.geometry")
        backend = config.get("backend", {})
        keys(
            backend,
            {"mapping", "backend_index", "native_geometry", "native_clamp_N", "agent_type"},
            "actuation.backend",
        )
        self.mapping = backend.get("mapping", "direct")
        if self.mapping not in ("direct", "wrench_equivalent"):
            raise ConfigurationError(
                "actuation.backend.mapping must be direct or wrench_equivalent"
            )
        self.agent_type = backend.get("agent_type")
        self.native_clamp = backend.get("native_clamp_N")
        if self.native_clamp is not None:
            self.native_clamp = number(self.native_clamp, "native_clamp_N", positive=True)
        if self.mapping == "direct":
            index = backend.get("backend_index", list(range(propulsion.count)))
            if sorted(index) != list(range(propulsion.count)):
                raise ConfigurationError("backend_index must be a permutation of actuator indices")
            self.backend_index = list(index)
            self.backend_count = propulsion.count
            self.native = None
        else:
            if self.mode != "wrench" or self.allocator is None:
                raise ConfigurationError("wrench_equivalent mapping requires action_mode: wrench")
            native = backend.get("native_geometry")
            if not isinstance(native, list) or not native:
                raise ConfigurationError("wrench_equivalent requires native_geometry")
            if self.native_clamp is None:
                raise ConfigurationError("wrench_equivalent requires native_clamp_N")
            native_items = [ActuatorGeometry.from_mapping(g) for g in native]
            self.native = ThrustAllocator(native_items, method="redistributed")
            self.backend_count = len(native_items)
            self.backend_index = None
            if self.native.rank < self.allocator.rank:
                raise ConfigurationError("Native layout cannot span the virtual layout's wrenches")

    # -- request side -----------------------------------------------------------------
    def validate_wrench(self, action):
        try:
            values = [float(v) for v in action]
        except TypeError as exc:
            raise ValueError("Wrench action must be six numbers [Fx,Fy,Fz,Mx,My,Mz]") from exc
        if len(values) != 6:
            raise ValueError("Wrench action must have six components")
        return [number(v, "wrench component") for v in values]

    def bounds(self, voltage):
        lo, hi = [], []
        for thruster in self.propulsion.thrusters:
            lo.append(-thruster.max_force(voltage, "reverse"))
            hi.append(thruster.max_force(voltage, "forward"))
        lo, hi = np.array(lo), np.array(hi)
        if self.mapping == "direct" and self.native_clamp is not None:
            lo = np.maximum(lo, -self.native_clamp)
            hi = np.minimum(hi, self.native_clamp)
        return lo, hi

    def allocate(self, wrench, voltage, power_functions=None):
        lo, hi = self.bounds(voltage)
        if power_functions is None and self.allocator.method == "power_irls":
            # Review E-09: power-weighted allocation uses the electrical thruster model at the
            # allocation voltage (force clamped to the table domain of each branch).
            power_functions = [
                (
                    lambda f, th=thruster, a=low, b=high: th.power(
                        min(max(f, a), b), voltage, "force_N"
                    )
                )
                for thruster, low, high in zip(self.propulsion.thrusters, lo, hi, strict=True)
            ]
        return self.allocator.allocate(wrench, lower=lo, upper=hi, power_functions=power_functions)

    def limit_to_native(self, forces, voltage):
        """Re-allocate a virtual layout to the wrench the native body can apply.

        If the native layout cannot reproduce the virtual wrench within its clamp, the
        virtual actuators are re-allocated to the native achievable wrench, so that the
        electrical energy is computed for thrust the dynamics actually receive.
        """
        tau = self.allocator.wrench(forces)
        clamp = np.full(self.backend_count, self.native_clamp)
        native = self.native.allocate(tau, lower=-clamp, upper=clamp)
        if native.residual_norm <= WRENCH_TOLERANCE:
            return list(forces), {"native_limited": False}
        achievable = self.native.wrench(native.forces_N)
        lo, hi = self.bounds(voltage)
        limited = self.allocator.allocate(achievable, lower=lo, upper=hi)
        return list(limited.forces_N), {
            "native_limited": True,
            "native_unmet_wrench_norm": native.residual_norm,
        }

    # -- backend side -----------------------------------------------------------------
    def backend_action(self, forces):
        """Return (backend vector, native wrench residual norm, info)."""
        if self.mapping == "direct":
            out = [0.0] * self.backend_count
            for i, f in zip(self.backend_index, forces, strict=True):
                out[i] = float(f)
            return out, 0.0, {}
        tau = self.allocator.wrench(forces)
        clamp = np.full(self.backend_count, self.native_clamp)
        result = self.native.allocate(tau, lower=-clamp, upper=clamp)
        return (
            list(result.forces_N),
            result.residual_norm,
            {"virtual_wrench": list(tau), "native_saturated": list(result.saturated)},
        )

    def describe(self):
        return {
            "action_mode": self.mode,
            "mapping": self.mapping,
            "configured_actuators": list(self.propulsion.ids),
            "backend_actuator_count": self.backend_count,
            "allocation_method": None if self.allocator is None else self.allocator.method,
            "layout_rank": None if self.allocator is None else self.allocator.rank,
            "native_clamp_N": self.native_clamp,
            "agent_type": self.agent_type,
        }
