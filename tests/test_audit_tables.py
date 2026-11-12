"""Invariants of the generated parameter audit and sensor table."""

import importlib.util
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_parameter_audit_rows_are_traceable():
    warnings.simplefilter("ignore", UserWarning)
    rows, _ = load("build_parameter_audit").collect()
    assert len(rows) > 30
    for r in rows:
        if r["status"] == "configured" and r["effective_grade"] in "ABC":
            assert r["source_id"], r["parameter_id"]
        if r["status"] in ("unlinked", "unconfigured"):
            assert r["effective_grade"] == "D", r["parameter_id"]
        # A relation cap can only lower a grade.
        assert r["effective_grade"] >= r["evidence_grade"] or r["status"] != "configured", r[
            "parameter_id"
        ]
    t200 = next(
        r for r in rows if r["parameter_id"] == "bluerobotics_t200.static_force_power_curve"
    )
    assert t200["effective_grade"] == "B" and t200["applied_relation"] == "representative"
    assert any(r["parameter_id"] == "config:converters.payload_efficiency" for r in rows)


def test_sensor_table_ground_truth_is_zero_watt():
    rows = load("build_sensor_table").build()
    truth = [r for r in rows if r["class"] == "simulator ground truth"]
    assert {r["holoocean_sensor"] for r in truth} >= {
        "PoseSensor",
        "VelocitySensor",
        "DynamicsSensor",
    }
    assert all(r["power_W"] == "" and r["default_behaviour"].startswith("0 W") for r in truth)
    derived = [r for r in rows if r["class"] == "derived/processed"]
    assert all("compute" in r["real_world_mapping"] for r in derived)
