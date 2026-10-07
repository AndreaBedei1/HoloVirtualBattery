"""Chain-closure tool: momentum balance and independent T200 power lookup (synthetic)."""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from holoenergy.models.propulsion import ThrusterModel

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "verify_energy_chain", ROOT / "tools/verify_energy_chain.py"
)
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)

PARAMETERS = {
    "mass_kg": 11.5,
    "drag_coefficient": 0.8,
    "area_m2": 0.45,
    "density_kg_m3": 997.0,
    "linear_damping_per_s": 1.0,
    "fully_submerged_ratio": 1.0,
}
PROFILE = json.loads((ROOT / "holoenergy/profiles/thrusters/bluerobotics_t200.json").read_text())


def synthetic_trace(scale, steps=50, dt=0.01, yaw_deg=30.0):
    """Explicit Euler + ether damping with the drag applied at ``scale`` of its SI value."""
    tables = chain.T200Tables(PROFILE)
    current = [0.5, 0.0, 0.0]
    applied = [1.0, 1.0, 1.0, 1.0, 12.0, -6.0, 4.0, 2.5]
    rpy = [0.0, 0.0, yaw_deg]
    v = [0.0, 0.0, 0.0]
    rows = []
    for k in range(steps):
        thrust = chain.thruster_force_world(applied, rpy)
        drag = chain.drag_force_N(v, current, PARAMETERS)
        force = [t + scale * d for t, d in zip(thrust, drag, strict=True)]
        gain = 1 - PARAMETERS["linear_damping_per_s"] * dt
        v = [gain * (a + f * dt / PARAMETERS["mass_kg"]) for a, f in zip(v, force, strict=True)]
        powers = [tables.power(f, 15.5) for f in applied]
        rows.append(
            {
                "t_s": (k + 1) * dt,
                "current_m_s": current,
                "com_velocity_m_s": v,
                "rpy_deg": rpy,
                "applied_N": applied,
                "voltage_V": 15.5,
                "thruster_power_W": powers,
                "power_propulsion_W": sum(powers),
            }
        )
    return rows, tables


def test_momentum_balance_closes_only_with_the_applied_drag_scale():
    rows, tables = synthetic_trace(scale=1.0)
    result = chain.close_trace(rows, PARAMETERS, 1.0, tables, 0.01)
    assert max(result["max_abs_force_residual_N"]) < 1e-9
    assert result["peak_drag_N"] > 10
    stock_rows, _ = synthetic_trace(scale=0.01)
    stock = chain.close_trace(stock_rows, PARAMETERS, 0.01, tables, 0.01)
    assert max(stock["max_abs_force_residual_N"]) < 1e-9
    # Assuming the SI drag on a 0.01-scaled backend leaves 99% of the drag unexplained.
    assert (
        max(stock["max_abs_force_residual_assuming_SI_drag_N"]) > 0.9 * 0.5 * 997 * 0.8 * 0.45 * 0.2
    )


def test_rotation_maps_body_surge_to_world():
    world = chain.thruster_force_world([0, 0, 0, 0, 1, 1, 1, 1], [0.0, 0.0, 90.0])
    assert world == pytest.approx([0.0, 4 / math.sqrt(2), 0.0], abs=1e-12)


def test_trace_must_be_per_tick():
    rows, tables = synthetic_trace(scale=1.0)
    with pytest.raises(ValueError, match="per tick"):
        chain.close_trace(rows[::2], PARAMETERS, 1.0, tables, 0.01)


@pytest.mark.parametrize("force", [-3.7, -0.2, 0.0, 0.4, 7.25, 18.0, 28.0])
@pytest.mark.parametrize("voltage", [10.0, 13.3, 15.71, 16.0, 19.9])
def test_independent_t200_lookup_matches_holoenergy(force, voltage):
    independent = chain.T200Tables(PROFILE).power(force, voltage)
    model = ThrusterModel(PROFILE)
    if abs(force) > model.max_force(voltage, "forward" if force > 0 else "reverse"):
        pytest.skip("outside the measured force domain at this voltage")
    assert independent == pytest.approx(model.power(force, voltage), rel=1e-12, abs=1e-12)
