"""Drag audit driver: still-water family metrics and case sets; no Unreal launch."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sys.path.insert(0, str(ROOT / "examples"))
driver = load("drag_driver", "examples/verify_holoocean_drag_units.py")


def test_autodrag_family_scales_every_step():
    record = {
        "case": "autodrag_x_0.4",
        "observed_expected_scale": 1.0000001,
        "step_observed_expected_scales": [1.0000001, 0.9999999, None],
        "maximum_source_prediction_error_m_s": 1e-8,
    }
    summary = driver.family_summary([record])
    assert summary["step_observations"] == 2
    assert summary["step_scale_mean"] == pytest.approx(1.0)
    assert driver.projected_scale([0, 0, 0], [0, 0, 0]) is None
    assert driver.projected_scale([0.02, 0, 0], [2, 0, 0]) == pytest.approx(0.01)
    names = [c["name"] for c in driver.autodrag_cases()]
    assert {"thrust_0_10N", "gravity_air", "neutral_zero"} <= set(names)
    assert "autodrag_yaw90_world_x" in names
    assert all(c["current"] == [0, 0, 0] for c in driver.autodrag_cases())
