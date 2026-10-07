"""Structure checks for future real runs; fixtures are synthetic and live in tmp only."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "experiment_check", ROOT / "tools/check_experiment_run.py"
)
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)

HEADER = [
    "time_s",
    "battery_voltage_V",
    "battery_current_A",
    "battery_temperature_C",
    "water_temperature_C",
    "mission_phase",
    "thruster_1_command_pwm_us",
    "depth_m",
    "sensor_camera_state",
]
ROWS = [
    ["0.0", "16.1", "1.2", "21.0", "15.0", "hover", "1500", "1.0", "ACTIVE"],
    ["0.1", "16.0", "3.4", "21.0", "15.0", "hover", "1560", "1.0", "ACTIVE"],
    ["0.2", "", "3.5", "21.1", "15.0", "hover", "1560", "1.01", "ACTIVE"],
]


def metadata(raw_hash):
    channels = {c: {"unit": checker.unit_of(c) or "text", "source": "fixture"} for c in HEADER}
    for name in ("time_s", "mission_phase"):
        channels.pop(name)
    return {
        "schema_version": 1,
        "run_id": "synthetic_fixture_001",
        "dataset_kind": "experimental",
        "role": "parameter_identification",
        "independence_group": "fixture_cycle_1",
        "protocol_step": "hover",
        "start_time_utc": "2026-10-07T10:00:00Z",
        "vehicle": {
            "model": "fixture",
            "configuration": "fixture",
            "thruster_layout": "fixture",
            "payload": [],
        },
        "battery": {
            "model": "fixture",
            "chemistry": "fixture",
            "nominal_voltage_V": 14.8,
            "rated_capacity_Ah": 18,
            "initial_soc_method": "fixture",
        },
        "environment": {"water_body": "fixture", "water_temperature_sensor": "fixture"},
        "instruments": [
            {
                "name": "fixture meter",
                "measures": ["battery_voltage_V"],
                "calibration_reference": "fixture",
                "sample_rate_Hz": 10,
                "uncertainty": "fixture",
            }
        ],
        "channels": channels,
        "time_sync": {"method": "fixture", "max_offset_s": 0.01},
        "safety": {"in_water": True, "secured": True, "authorized_personnel": True},
        "software": {"holoenergy_commit": None},
        "raw_files": [{"path": "raw/log.bin", "sha256": raw_hash}],
        "operator_notes": "synthetic test fixture, not a measurement",
    }


def write_run(path, meta=None, rows=ROWS, raw=b"raw-bytes"):
    (path / "raw").mkdir(parents=True)
    (path / "raw/log.bin").write_bytes(raw)
    meta = meta or metadata(hashlib.sha256(b"raw-bytes").hexdigest())
    (path / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    lines = [",".join(HEADER)] + [",".join(r) for r in rows]
    (path / "timeseries.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_valid_run_passes_and_missing_values_stay_missing(tmp_path):
    problems, summary = checker.check_run(write_run(tmp_path / "run"))
    assert problems == []
    assert summary["samples"] == 3


def test_thruster_steps_require_in_water_safety(tmp_path):
    meta = metadata(hashlib.sha256(b"raw-bytes").hexdigest())
    meta["safety"]["in_water"] = False
    problems, _ = checker.check_run(write_run(tmp_path / "run", meta=meta))
    assert any("in_water" in p for p in problems)


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda rows: [rows[0], rows[0]], "strictly increasing"),
        (lambda rows: [rows[0], ["0.1", "nan"] + rows[1][2:]], "not finite"),
        (lambda rows: [rows[0][:-1]], "cells"),
    ],
)
def test_time_series_contract(tmp_path, mutation, expected):
    rows = mutation(copy.deepcopy(ROWS))
    problems, _ = checker.check_run(write_run(tmp_path / "run", rows=rows))
    assert any(expected in p for p in problems)


def test_undeclared_channel_and_raw_hash_mismatch(tmp_path):
    meta = metadata("0" * 64)
    del meta["channels"]["depth_m"]
    problems, _ = checker.check_run(write_run(tmp_path / "run", meta=meta))
    assert any("'depth_m' not declared" in p for p in problems)
    assert any("hash mismatch" in p for p in problems)


def test_repository_contains_no_experimental_runs_yet():
    runs = [
        p
        for part in ("calibration", "validation")
        for p in (ROOT / "experiments" / part).iterdir()
        if p.is_dir()
    ]
    assert runs == []
