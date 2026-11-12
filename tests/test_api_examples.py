"""Every API example runs without a simulator and returns a provenance-aware report."""

import importlib.util
import warnings
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("api_examples", ROOT / "examples/api_examples.py")
api = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(api)


@pytest.mark.parametrize("example", api.EXAMPLES, ids=lambda f: f.__name__)
def test_api_example(example):
    warnings.simplefilter("ignore", UserWarning)
    report = example()
    assert report["terminal_energy_Wh"] > 0
    assert set(report["evidence"]["share_percent"]) == {"A", "B", "C", "D"}
    assert report["duration_s"] == pytest.approx(2.0)


def test_desert_example_charges_communication_energy():
    warnings.simplefilter("ignore", UserWarning)
    assert api.desert_integration()["category_energy_Wh"]["communications"] > 0
