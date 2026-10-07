"""Native timestep audit estimators on synthetic Chaos recursions; no Unreal launch."""

import importlib.util
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


timestep = load("timestep_audit", "tools/audit_holoocean_timestep.py")

PARAMETERS = {
    "mass_kg": 11.5,
    "drag_coefficient": 0.8,
    "area_m2": 0.45,
    "density_kg_m3": 997.0,
    "linear_damping_per_s": 1.0,
    "fully_submerged_ratio": 1.0,
    "source_drag_scale_to_SI": 1.0,
}


def chaos_rows(case, tps, physics_dt, steps=6, v0=(0.0, 0.0, 0.0), accel=(0.0, 0.0, 0.0)):
    """Synthetic sensor rows from the UE 5.3 Chaos recursion with a known physics step."""
    c = PARAMETERS["linear_damping_per_s"]
    v, x, t = list(v0), [0.0, 0.0, 20.0], 0.0
    rows = []
    for step in range(-1, steps):
        if step >= 0:
            new_v = [
                (vi + ai * physics_dt) * (1 - c * physics_dt)
                for vi, ai in zip(v, accel, strict=True)
            ]
            x = [xi + vi * physics_dt for xi, vi in zip(x, new_v, strict=True)]
            sensor = [
                (nv - ov) * tps for nv, ov in zip(new_v, v, strict=True)
            ]  # dv / world DeltaTime
            v, t = new_v, t + 1 / tps
        else:
            sensor = [0.0, 0.0, 0.0]
        rows.append(
            {
                "case": case,
                "trial": 0,
                "ticks_per_sec": tps,
                "step": step,
                "time_s": t,
                "velocity_m_s": v,
                "position_m": x,
                "acceleration_sensor_m_s2": sensor,
                "angular_velocity_rad_s": [0.0, 0.0, 0.0],
                "collision": False,
            }
        )
    return rows


def test_predicted_physics_step_follows_the_ue_cap():
    assert timestep.predicted_physics_dt(20) == pytest.approx(1 / 30, rel=1e-7)
    assert timestep.predicted_physics_dt(30) == pytest.approx(1 / 30, rel=1e-7)
    assert timestep.predicted_physics_dt(100) == pytest.approx(0.01, rel=1e-7)


@pytest.mark.parametrize("tps,physics_dt", [(20, 1 / 30), (100, 0.01), (200, 0.005)])
def test_estimators_recover_the_integrated_step(tps, physics_dt):
    gravity = chaos_rows("gravity_air", tps, physics_dt, accel=(0, 0, -9.8))
    moving = chaos_rows("air_moving_x", tps, physics_dt, v0=(1.0, 0, 0), accel=(0, 0, -9.8))
    thrust = chaos_rows("thrust_x_10N_water", tps, physics_dt, accel=(10 / 11.5, 0, 0))
    for rows, key in (
        (gravity, "gravity_velocity"),
        (moving, "damping_ratio"),
        (thrust, "thrust_first_step"),
    ):
        values = timestep.estimates(rows, PARAMETERS)
        assert values[key], key
        assert all(math.isclose(v, physics_dt, rel_tol=1e-9) for v in values[key])
        assert all(math.isclose(v, physics_dt, rel_tol=1e-9) for v in values["kinematic_position"])
        assert all(
            math.isclose(v, 1 / tps, rel_tol=1e-9) for v in values["world_delta_from_sensor"]
        )


def test_evaluation_flags_a_capped_physics_step():
    rows = []
    for tps, dt in ((20, 1 / 30), (100, 0.01)):
        rows += chaos_rows("gravity_air", tps, dt, accel=(0, 0, -9.8))
        rows += chaos_rows("air_moving_x", tps, dt, v0=(1.0, 0, 0), accel=(0, 0, -9.8))
        rows += chaos_rows("thrust_x_10N_water", tps, dt, accel=(10 / 11.5, 0, 0))
    result = timestep.evaluate(rows, PARAMETERS, [20, 100])
    assert result["20"]["effective_to_client_ratio"] == pytest.approx(2 / 3, rel=1e-9)
    assert not result["20"]["physics_consistent_with_client_clock"]
    assert result["100"]["physics_consistent_with_client_clock"]
    assert result["20"]["world_delta_to_client_ratio"] == pytest.approx(1, rel=1e-9)


def test_continuous_still_water_solution_limits():
    v = timestep.continuous_still_water_velocity(2.5, 0.0, PARAMETERS)
    assert v == pytest.approx(2.5)
    later = timestep.continuous_still_water_velocity(2.5, 0.5, PARAMETERS)
    assert 0 < later < 2.5
    no_drag = dict(PARAMETERS, source_drag_scale_to_SI=0.0)
    assert timestep.continuous_still_water_velocity(2.5, 1.0, no_drag) == pytest.approx(
        2.5 * math.exp(-1.0)
    )
