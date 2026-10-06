"""Independent SI and classification checks; never launch an Unreal process."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "drag_audit", Path(__file__).resolve().parents[1] / "tools/audit_holoocean_drag.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
classify, drag_force_N, predicted_velocity = (
    audit.classify,
    audit.drag_force_N,
    audit.predicted_velocity,
)


@pytest.fixture
def parameters():
    # Deliberately simple synthetic numbers: k = rho*Cd*A/2 = 1 N/(m/s)^2.
    return {
        "density_kg_m3": 10,
        "drag_coefficient": 0.2,
        "area_m2": 1,
        "fully_submerged_ratio": 1,
        "mass_kg": 2,
        "linear_damping_per_s": 1,
        "explicit_drag_unit_conversion": False,
    }


def test_relative_flow_vector_sign_and_quadratic_scaling(parameters):
    assert drag_force_N([0, 0, 0], [3, 4, 0], parameters) == [15, 20, 0]
    assert drag_force_N([3, 4, 0], [0, 0, 0], parameters) == [-15, -20, 0]
    assert drag_force_N([3, 4, 0], [3, 4, 0], parameters) == [0, 0, 0]
    first = drag_force_N([0, 0, 0], [1, 0, 0], parameters)[0]
    second = drag_force_N([0, 0, 0], [2, 0, 0], parameters)[0]
    assert second / first == 4


def test_ue_force_step_then_damping_is_not_a_drag_coefficient_fit(parameters):
    assert predicted_velocity([1, 0, 0], [2, 0, 0], 0.1, parameters) == pytest.approx([0.99, 0, 0])


@pytest.mark.parametrize(
    "scale,expected", [(0.01, "CASE C"), (100, "CASE C"), (1, "CASE B"), (2, "INCONCLUSIVE")]
)
def test_classification_requires_absolute_force_reference(scale, expected, parameters):
    assert classify(scale, True, parameters) == expected
    assert classify(scale, False, parameters) == "INCONCLUSIVE"


def test_corrected_source_and_correct_binary_is_case_a(parameters):
    parameters["explicit_drag_unit_conversion"] = True
    assert classify(1, True, parameters) == "CASE A"


def test_bad_vectors_are_rejected(parameters):
    with pytest.raises(ValueError):
        drag_force_N([0, 0], [1, 0, 0], parameters)
    with pytest.raises(ValueError):
        drag_force_N([0, 0, float("nan")], [1, 0, 0], parameters)
