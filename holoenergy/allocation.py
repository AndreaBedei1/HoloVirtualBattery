"""Generic actuator geometry and thrust allocation for an arbitrary number of thrusters.

Frame: vehicle body frame of the dynamics backend, origin at the centre of mass.  For
HoloOcean this is the client body frame (x forward, y left, z up, metres).  A
generalized force (wrench) is ``tau = [Fx, Fy, Fz, Mx, My, Mz]`` in N and N*m.

Each thruster ``i`` with unit direction ``d_i`` at position ``r_i`` contributes the
column ``[d_i, r_i x d_i]`` of the configuration matrix ``B`` (6 x n), so
``tau = B f`` with ``f`` the signed thrust magnitudes (N): the effector configuration
matrix of control allocation (Johansen and Fossen 2013, Automatica 49(5):1087-1103,
doi:10.1016/j.automatica.2013.01.035; source id ALLOC-JF2013).

Methods
-------
``pseudoinverse``
    Weighted minimum-norm solution ``f = W^-1/2 (B W^-1/2)^+ tau``; for a rank-deficient
    configuration it returns the least-squares wrench with minimum weighted effort.
``redistributed``
    Box-bounded redistributed pseudo-inverse: saturate violating actuators at their
    bound, re-solve for the remaining ones, repeat.  Simple, deterministic and widely
    used; not guaranteed to be the constrained optimum (Johansen and Fossen 2013, §2).
``power_irls``
    Iteratively reweighted pseudo-inverse with weights from a supplied electrical
    power function ``P_i(f)``: an engineering heuristic toward lower electrical power,
    reported as such; equality ``B f = tau`` is preserved when feasible.

No method changes the requested wrench silently: the achieved wrench and residual
are always returned.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ._validation import ConfigurationError, number

_DOF = ("Fx", "Fy", "Fz", "Mx", "My", "Mz")


def _vec3(value, name):
    if not isinstance(value, (list, tuple, np.ndarray)) or len(value) != 3:
        raise ConfigurationError(f"{name} must contain three numbers")
    return np.array([number(float(v), name) for v in value], dtype=float)


@dataclass(frozen=True)
class ActuatorGeometry:
    """Thruster mounting: position (m) and unit thrust direction in the body frame."""

    id: str
    position_m: tuple
    direction: tuple

    def __post_init__(self):
        if not isinstance(self.id, str) or not self.id:
            raise ConfigurationError("Actuator geometry requires a nonempty id")
        p = _vec3(self.position_m, f"{self.id}.position_m")
        d = _vec3(self.direction, f"{self.id}.direction")
        norm = float(np.linalg.norm(d))
        if abs(norm - 1.0) > 1e-6:
            raise ConfigurationError(f"{self.id}.direction must be a unit vector (|d|={norm:.6g})")
        object.__setattr__(self, "position_m", tuple(float(x) for x in p))
        object.__setattr__(self, "direction", tuple(float(x) for x in d))

    @classmethod
    def from_mapping(cls, data):
        allowed = {"id", "position_m", "direction", "direction_deg"}
        extra = set(data) - allowed
        if extra:
            raise ConfigurationError(f"Unknown actuator geometry fields {sorted(extra)}")
        if "direction_deg" in data:
            if "direction" in data:
                raise ConfigurationError("Give direction or direction_deg, not both")
            direction = direction_from_angles(**data["direction_deg"])
        else:
            direction = data.get("direction")
        return cls(data.get("id"), data.get("position_m"), direction)

    def column(self):
        r = np.array(self.position_m)
        d = np.array(self.direction)
        return np.concatenate([d, np.cross(r, d)])


def direction_from_angles(azimuth=0.0, elevation=0.0):
    """Unit vector from azimuth (deg, about +z from +x toward +y) and elevation (deg, toward +z)."""
    az = np.deg2rad(number(azimuth, "azimuth"))
    el = np.deg2rad(number(elevation, "elevation"))
    return (float(np.cos(el) * np.cos(az)), float(np.cos(el) * np.sin(az)), float(np.sin(el)))


def configuration_matrix(actuators):
    if not actuators:
        raise ConfigurationError("At least one actuator is required")
    ids = [a.id for a in actuators]
    if len(set(ids)) != len(ids):
        raise ConfigurationError("Actuator ids must be unique")
    return np.column_stack([a.column() for a in actuators])


@dataclass(frozen=True)
class AllocationResult:
    forces_N: tuple
    requested_wrench: tuple
    achieved_wrench: tuple
    residual: tuple
    residual_norm: float
    saturated: tuple
    method: str
    iterations: int
    notes: tuple = field(default_factory=tuple)

    def to_dict(self):
        return {
            "forces_N": list(self.forces_N),
            "requested_wrench": dict(zip(_DOF, self.requested_wrench, strict=True)),
            "achieved_wrench": dict(zip(_DOF, self.achieved_wrench, strict=True)),
            "residual_norm": self.residual_norm,
            "saturated": list(self.saturated),
            "method": self.method,
            "iterations": self.iterations,
            "notes": list(self.notes),
        }


def controllable_dofs(B, tol=1e-9):
    """Rank and the wrench subspace the layout can generate (orthonormal basis)."""
    u, s, _ = np.linalg.svd(B)
    rank = int(np.sum(s > tol * max(1.0, s[0] if s.size else 1.0)))
    return rank, u[:, :rank]


class ThrustAllocator:
    """Allocate a body wrench to ``n`` thrusters of arbitrary position and orientation."""

    METHODS = ("pseudoinverse", "redistributed", "power_irls")

    def __init__(self, actuators, *, method="redistributed", weights=None, dof_weights=None):
        self.actuators = list(actuators)
        self.B = configuration_matrix(self.actuators)
        self.n = self.B.shape[1]
        if method not in self.METHODS:
            raise ConfigurationError(f"Allocation method must be one of {self.METHODS}")
        self.method = method
        w = np.ones(self.n) if weights is None else np.array(weights, dtype=float)
        if w.shape != (self.n,) or np.any(w <= 0) or not np.all(np.isfinite(w)):
            raise ConfigurationError("Allocation weights must be n positive finite numbers")
        self.weights = w
        q = np.ones(6) if dof_weights is None else np.array(dof_weights, dtype=float)
        if q.shape != (6,) or np.any(q < 0):
            raise ConfigurationError("dof_weights must be six nonnegative numbers")
        self.dof_weights = q
        self.rank, self.basis = controllable_dofs(self.B)

    @property
    def ids(self):
        return [a.id for a in self.actuators]

    def _solve(self, tau, free, fixed_f, weights):
        """Weighted minimum-norm least squares on the free actuators."""
        Q = np.sqrt(self.dof_weights)
        target = Q * (tau - self.B[:, ~free] @ fixed_f[~free])
        A = Q[:, None] * self.B[:, free]
        sqrt_w = np.sqrt(weights[free])
        x = np.linalg.pinv(A / sqrt_w, rcond=1e-10) @ target
        f = fixed_f.copy()
        f[free] = x / sqrt_w
        return f

    def allocate(self, wrench, *, lower=None, upper=None, power_functions=None):
        tau = np.array([number(float(v), "wrench component") for v in wrench], dtype=float)
        if tau.shape != (6,):
            raise ConfigurationError("Wrench must have six components [Fx,Fy,Fz,Mx,My,Mz]")
        lo = np.full(self.n, -np.inf) if lower is None else np.array(lower, dtype=float)
        hi = np.full(self.n, np.inf) if upper is None else np.array(upper, dtype=float)
        if lo.shape != (self.n,) or hi.shape != (self.n,) or np.any(lo > 0) or np.any(hi < 0):
            raise ConfigurationError("Bounds must be n values with lower <= 0 <= upper")
        notes = []
        if self.rank < 6:
            notes.append(f"layout rank {self.rank} < 6: unreachable wrench components are residual")
        method = self.method
        free = np.ones(self.n, dtype=bool)
        f = np.zeros(self.n)
        weights = self.weights.copy()
        iterations = 0
        if method == "power_irls":
            if power_functions is None or len(power_functions) != self.n:
                raise ConfigurationError("power_irls requires one power function per actuator")
            f = self._solve(tau, free, f, weights)
            for step in range(1, 31):
                iterations = step
                # Local quadratic model P_i(f) ~ w_i f^2 matched at the current point; the
                # signed force selects the forward or reverse branch of the actuator model.
                new = np.array(
                    [
                        max(p(x) / max(x * x, 1e-6), 1e-9) if abs(x) > 1e-6 else weights[i]
                        for i, (p, x) in enumerate(zip(power_functions, f, strict=True))
                    ]
                )
                f_new = self._solve(tau, free, np.zeros(self.n), new)
                if np.max(np.abs(f_new - f)) < 1e-6:
                    f = f_new
                    break
                f, weights = f_new, new
            notes.append("power_irls: heuristic reweighting, not a certified optimum")
        else:
            f = self._solve(tau, free, f, weights)
        if method in ("redistributed", "power_irls") and (np.any(f < lo) or np.any(f > hi)):
            fixed = np.zeros(self.n)
            for _ in range(self.n):
                iterations += 1
                violating = free & ((f < lo - 1e-12) | (f > hi + 1e-12))
                if not np.any(violating):
                    break
                fixed[violating] = np.clip(f[violating], lo[violating], hi[violating])
                free &= ~violating
                if not np.any(free):
                    f = fixed
                    break
                f = self._solve(tau, free, fixed, weights)
            f = np.clip(f, lo, hi)
        elif method == "pseudoinverse" and (np.any(f < lo) or np.any(f > hi)):
            notes.append("pseudoinverse result clipped to bounds without redistribution")
            f = np.clip(f, lo, hi)
        achieved = self.B @ f
        residual = tau - achieved
        saturated = tuple(
            self.actuators[i].id
            for i in range(self.n)
            if (np.isfinite(hi[i]) and f[i] >= hi[i] - 1e-9)
            or (np.isfinite(lo[i]) and f[i] <= lo[i] + 1e-9)
        )
        return AllocationResult(
            tuple(float(x) for x in f),
            tuple(float(x) for x in tau),
            tuple(float(x) for x in achieved),
            tuple(float(x) for x in residual),
            float(np.linalg.norm(residual)),
            saturated,
            method,
            iterations,
            tuple(notes),
        )

    def wrench(self, forces):
        f = np.array(forces, dtype=float)
        if f.shape != (self.n,):
            raise ConfigurationError(f"Expected {self.n} actuator forces")
        return tuple(float(x) for x in self.B @ f)

    def projection_report(self):
        """Per-actuator projection of unit thrust on each body axis (force projection loss)."""
        rows = []
        for a, col in zip(self.actuators, self.B.T, strict=True):
            rows.append(
                {
                    "id": a.id,
                    "direction": list(a.direction),
                    "position_m": list(a.position_m),
                    **{k: float(v) for k, v in zip(_DOF, col, strict=True)},
                }
            )
        return {"rank": self.rank, "actuators": rows}

    def max_wrench_along(self, direction, lower, upper):
        """Largest scalar s such that s*direction is exactly allocatable within bounds.

        Solved by bisection on the redistributed allocator; ``direction`` is a 6-vector.
        """
        d = np.array(direction, dtype=float)
        if not np.any(d):
            raise ConfigurationError("Direction must be nonzero")
        lo, hi = 0.0, 1.0
        while self.allocate(d * hi, lower=lower, upper=upper).residual_norm < 1e-9 * max(hi, 1):
            hi *= 2
            if hi > 1e7:
                return float("inf")
        for _ in range(60):
            mid = 0.5 * (lo + hi)
            if self.allocate(d * mid, lower=lower, upper=upper).residual_norm < 1e-9 * max(mid, 1):
                lo = mid
            else:
                hi = mid
        return lo


__all__ = [
    "ActuatorGeometry",
    "AllocationResult",
    "ThrustAllocator",
    "configuration_matrix",
    "controllable_dofs",
    "direction_from_angles",
]
