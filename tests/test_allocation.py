import numpy as np
import pytest

from holoenergy._validation import ConfigurationError
from holoenergy.allocation import (
    ActuatorGeometry,
    ThrustAllocator,
    configuration_matrix,
    direction_from_angles,
)

S = 1 / np.sqrt(2)
# HoloOcean 2.3.0 BlueROV2 (client body frame, CoM origin), derived from BlueROV2.h/.cpp.
HEAVY = [
    ActuatorGeometry("V1", (0.12, -0.2181, 0.0809), (0, 0, 1)),
    ActuatorGeometry("V2", (0.12, 0.2181, 0.0809), (0, 0, 1)),
    ActuatorGeometry("V3", (-0.12, 0.2181, 0.0809), (0, 0, 1)),
    ActuatorGeometry("V4", (-0.12, -0.2181, 0.0809), (0, 0, 1)),
    ActuatorGeometry("H1", (0.1562, -0.0988, 0.0), (S, S, 0)),
    ActuatorGeometry("H2", (0.1562, 0.0988, 0.0), (S, -S, 0)),
    ActuatorGeometry("H3", (-0.1562, 0.0988, 0.0), (S, S, 0)),
    ActuatorGeometry("H4", (-0.1562, -0.0988, 0.0), (S, -S, 0)),
]


def test_configuration_matrix_columns_are_force_and_moment():
    B = configuration_matrix(HEAVY)
    assert B.shape == (6, 8)
    # Equal forward command on the four vectored thrusters: pure surge, no yaw.
    tau = B @ np.array([0, 0, 0, 0, 1, 1, 1, 1.0])
    assert tau[0] == pytest.approx(4 * S)
    assert np.allclose(tau[1:], 0, atol=1e-12)
    # Equal vertical thrust: heave plus a pitch moment only if z-offset couples (it does not).
    tau = B @ np.array([1, 1, 1, 1, 0, 0, 0, 0.0])
    assert tau[2] == pytest.approx(4)
    assert np.allclose(tau[[0, 1, 3, 4, 5]], 0, atol=1e-12)


def test_arbitrary_count_and_orientation():
    for n in (3, 4, 5, 6, 7, 8, 12):
        actuators = [
            ActuatorGeometry(
                f"T{i}",
                (np.cos(2 * np.pi * i / n), np.sin(2 * np.pi * i / n), 0.1 * (i % 2)),
                direction_from_angles(azimuth=360 * i / n + 90, elevation=30 if i % 2 else -30),
            )
            for i in range(n)
        ]
        allocator = ThrustAllocator(actuators, method="pseudoinverse")
        f = np.linspace(-1, 1, n)
        tau = allocator.wrench(f)
        result = allocator.allocate(tau)
        assert result.residual_norm < 1e-8
        assert len(result.forces_N) == n


def test_rank_deficient_layout_reports_residual():
    planar = [
        ActuatorGeometry("L", (0, 0.2, 0), (1, 0, 0)),
        ActuatorGeometry("R", (0, -0.2, 0), (1, 0, 0)),
    ]
    allocator = ThrustAllocator(planar, method="pseudoinverse")
    assert allocator.rank == 2
    result = allocator.allocate([10, 5, 0, 0, 0, 1])
    # Fx and Mz achievable; sway is not.
    assert result.achieved_wrench[0] == pytest.approx(10)
    assert result.achieved_wrench[5] == pytest.approx(1)
    assert result.residual[1] == pytest.approx(5)
    assert any("rank" in n for n in result.notes)


def test_redistributed_respects_bounds_and_keeps_wrench_when_feasible():
    allocator = ThrustAllocator(HEAVY, method="redistributed")
    lo, hi = np.full(8, -28.75), np.full(8, 28.75)
    tau = [50, 10, 0, 0, 0, 2.0]
    result = allocator.allocate(tau, lower=lo, upper=hi)
    assert all(-28.75 - 1e-9 <= f <= 28.75 + 1e-9 for f in result.forces_N)
    assert result.residual_norm < 1e-6
    # Infeasible surge: saturates and reports a residual instead of exceeding bounds.
    result = allocator.allocate([200, 0, 0, 0, 0, 0], lower=lo, upper=hi)
    assert max(result.forces_N) <= 28.75 + 1e-9
    assert result.residual_norm > 1
    assert result.saturated


def test_power_irls_preserves_wrench_and_does_not_increase_power():
    allocator = ThrustAllocator(HEAVY, method="power_irls")
    base = ThrustAllocator(HEAVY, method="pseudoinverse")

    def p(f):  # convex test function, not a hardware model
        return 2.0 * abs(f) ** 1.5

    tau = [40, 15, 20, 1, 0.5, 3]
    irls = allocator.allocate(tau, power_functions=[p] * 8)
    ref = base.allocate(tau)
    assert irls.residual_norm < 1e-6
    assert sum(p(f) for f in irls.forces_N) <= sum(p(f) for f in ref.forces_N) + 1e-9


def test_geometry_validation():
    with pytest.raises(ConfigurationError, match="unit vector"):
        ActuatorGeometry("x", (0, 0, 0), (1, 1, 0))
    with pytest.raises(ConfigurationError, match="unique"):
        configuration_matrix([HEAVY[0], HEAVY[0]])
    g = ActuatorGeometry.from_mapping(
        {"id": "a", "position_m": [0, 0, 0], "direction_deg": {"azimuth": 45, "elevation": 0}}
    )
    assert g.direction == pytest.approx((S, S, 0))


def test_max_wrench_along_matches_simple_case():
    allocator = ThrustAllocator(HEAVY)
    lo, hi = np.full(8, -28.75), np.full(8, 28.75)
    surge = allocator.max_wrench_along([1, 0, 0, 0, 0, 0], lo, hi)
    assert surge == pytest.approx(4 * 28.75 * S, rel=1e-6)
    heave = allocator.max_wrench_along([0, 0, 1, 0, 0, 0], lo, hi)
    assert heave == pytest.approx(4 * 28.75, rel=1e-6)
