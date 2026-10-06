"""All data generated here are synthetic mathematical test fixtures, never experiments."""

import copy
import csv
import json
import subprocess
import sys

import pytest

from holoenergy._validation import ConfigurationError
from holoenergy.analysis.calibration import apply_battery_maps, battery_maps
from holoenergy.analysis.datasets import verify_manifest
from holoenergy.analysis.evaluation import energy, evaluate, evaluate_files, read_series
from holoenergy.analysis.replay import compare_models, read_mission, run_mission
from holoenergy.analysis.sensitivity import study
from holoenergy.provenance import file_hash


def write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def manifest_for(tmp_path, inputs):
    path = tmp_path / "manifest.json"
    value = {
        "schema_version": 1,
        "dataset_kind": "synthetic_test_fixture",
        "runs": [
            {
                "run_id": f"test_{i}",
                "role": role,
                "path": str(p),
                "sha256": file_hash(p),
                "independence_group": f"synthetic_group_{i}",
            }
            for i, (p, role) in enumerate(inputs)
        ],
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_identical_mission_comparison_metrics_and_provenance(config, tmp_path):
    commands = [{"action": [5] * 8}, {"action": [0] * 8}]
    with pytest.warns(UserWarning):
        results = compare_models(config, commands, tmp_path)
    l0, l1 = (results[k]["metrics"] for k in ("L0", "L1"))
    for result in results.values():
        m = result["metrics"]
        assert m["mission_completed"] is None
        assert m["command_sequence_completed"]
        assert m["terminal_energy_Wh"] == pytest.approx(
            sum(
                m[k]
                for k in (
                    "propulsion_energy_Wh",
                    "payload_energy_Wh",
                    "hotel_energy_Wh",
                    "conversion_loss_Wh",
                )
            )
        )
        assert result["provenance"]["command_history"] == commands
        assert m["wrapper_overhead_s"] >= 0
    assert l0["battery_internal_loss_Wh"] == 0 < l1["battery_internal_loss_Wh"]
    assert (tmp_path / "comparison.csv").exists()
    assert (
        results["L0"]["provenance"]["command_history_sha256"]
        == results["L1"]["provenance"]["command_history_sha256"]
    )


def test_goal_observer_is_explicit_and_not_electrical_feasibility(config, tmp_path):
    config["battery"]["max_current_A"] = 0.01
    result = run_mission(
        config, [{"action": [0] * 8}] * 3, tmp_path, completion_observer=lambda state: False
    )
    assert result["metrics"]["mission_completed"] is False
    assert not result["metrics"]["power_feasible"]
    assert result["metrics"]["derating_duration_s"] == pytest.approx(0.3)


def test_mission_csv_grid_and_state_import(tmp_path):
    path = write_csv(
        tmp_path / "commands.csv",
        [
            {
                "time_s": 0,
                "action": "[0,0]",
                "sensor_states": '{"DVL":"OFF"}',
                "water_temperature_C": 5,
            },
            {"time_s": 0.1, "action": "[1,-1]", "sensor_states": "{}", "water_temperature_C": 6},
        ],
    )
    rows = read_mission(path, 0.1)
    assert rows[1]["action"] == [1, -1]
    with pytest.raises(ConfigurationError, match="one row"):
        read_mission(path, 0.2)


def test_sensitivity_preserves_baseline_and_invalid_draws(config, tmp_path):
    before = copy.deepcopy(config)
    result = study(
        config,
        [{"action": [10] * 8}],
        {
            "mode": "sensitivity",
            "parameters": {
                "hotel_load.constant_W": {"relative_changes": [-0.2, 0, 0.2]},
                "converters.payload_efficiency": {"values": [1.1]},
            },
        },
        tmp_path,
    )
    assert config == before
    assert len(result["records"]) == 5
    assert result["records"][-1]["status"] == "failed"
    assert "<= 1" in result["records"][-1]["error"]
    assert (tmp_path / "study.csv").exists()


def test_seeded_monte_carlo_reproducible_and_explicit(config, tmp_path):
    spec = {
        "mode": "monte_carlo",
        "seed": 42,
        "samples": 3,
        "independent": True,
        "parameters": {
            "battery.internal_resistance_ohm": {"distribution": "uniform", "low": 0.05, "high": 0.2}
        },
    }
    a = study(config, [{"action": [5] * 8}], spec, tmp_path / "a")
    b = study(config, [{"action": [5] * 8}], spec, tmp_path / "b")
    assert [r["parameters"] for r in a["records"]] == [r["parameters"] for r in b["records"]]
    assert [r["terminal_energy_Wh"] for r in a["records"]] == [
        r["terminal_energy_Wh"] for r in b["records"]
    ]
    del spec["independent"]
    with pytest.raises(ConfigurationError, match="independent"):
        study(config, [{"action": [0] * 8}], spec, tmp_path / "bad")


def test_import_ocv_r_capacity_current_without_fabricated_cells(battery_config, tmp_path):
    path = write_csv(
        tmp_path / "maps.csv",
        [
            {
                "temperature_C": t,
                "soc": soc,
                "ocv_V": 12 + 4 * soc,
                "resistance_ohm": 0.2 - soc * 0.1,
            }
            for t in (5, 25)
            for soc in (0, 0.5, 1)
        ],
    )
    q = write_csv(
        tmp_path / "capacity.csv",
        [
            {"temperature_C": 5, "available_capacity_Ah": 8},
            {"temperature_C": 25, "available_capacity_Ah": 10},
        ],
    )
    i = write_csv(
        tmp_path / "current.csv",
        [{"temperature_C": 5, "max_current_A": 10}, {"temperature_C": 25, "max_current_A": 20}],
    )
    manifest = manifest_for(tmp_path, [(p, "parameter_identification") for p in (path, q, i)])
    result = battery_maps(
        path,
        capacity_path=q,
        current_path=i,
        reference_capacity_Ah=10,
        reference_current_A=20,
        manifest_path=manifest,
    )
    assert result["capacity_temperature_curve"] == [(5, 0.8), (25, 1)]
    assert result["max_current_temperature_curve"] == [(5, 0.5), (25, 1)]
    assert len(result["metadata"]["calibration_runs"]) == 3
    battery_config["metadata"] = {
        "placeholders": ["ocv_curve", "internal_resistance_ohm", "max_current_temperature_curve"]
    }
    complete = apply_battery_maps(battery_config, result)
    assert complete["metadata"]["placeholders"] == []
    assert complete["metadata"]["source_profile_sha256"]


@pytest.mark.parametrize("case", ["missing", "duplicate", "incomplete", "validation_role"])
def test_import_rejects_missing_or_reused_validation_measurements(tmp_path, case):
    rows = [
        {"temperature_C": 5, "soc": s, "ocv_V": 12 + 4 * s, "resistance_ohm": 0.1}
        for s in (0, 0.5, 1)
    ]
    if case == "missing":
        rows[1]["ocv_V"] = ""
    if case == "duplicate":
        rows.append(dict(rows[0]))
    if case == "incomplete":
        rows.pop()
    path = write_csv(tmp_path / "test.csv", rows)
    manifest = manifest_for(
        tmp_path,
        [(path, "final_validation" if case == "validation_role" else "parameter_identification")],
    )
    with pytest.raises(ConfigurationError):
        battery_maps(path, manifest_path=manifest)


@pytest.mark.parametrize("case", ["hash", "duplicate_content", "duplicate_id", "cross_role_group"])
def test_manifest_detects_leakage_and_tampering(tmp_path, case):
    a, b = tmp_path / "a.csv", tmp_path / "b.csv"
    a.write_text("synthetic A")
    b.write_text("synthetic B")
    path = manifest_for(tmp_path, [(a, "parameter_identification"), (b, "final_validation")])
    assert verify_manifest(path)["verified"]
    value = json.loads(path.read_text())
    if case == "hash":
        a.write_text("tampered synthetic fixture")
    if case == "duplicate_content":
        value["runs"][1].update({"path": str(a), "sha256": file_hash(a)})
    if case == "duplicate_id":
        value["runs"][1]["run_id"] = value["runs"][0]["run_id"]
    if case == "cross_role_group":
        value["runs"][1]["independence_group"] = value["runs"][0]["independence_group"]
    path.write_text(json.dumps(value))
    with pytest.raises(ConfigurationError):
        verify_manifest(path)


def test_exact_electrical_thermal_energy_and_event_metrics(tmp_path):
    measured = [
        {
            "time_s": t,
            "voltage_V": 12,
            "current_A": 2,
            "temperature_C": temperature,
            "soc": 0.8 - 0.1 * t,
            "battery_state": "CUTOFF" if t == 2 else "NORMAL",
            "derating_factor": 0.5 if t >= 1 else 1,
        }
        for t, temperature in ((0, 20), (1, 22), (2, 21))
    ]
    predicted = [
        {
            **r,
            "voltage_V": 13,
            "power_total_W": 26,
            "dt_s": 1,
            "temperature_C": r["temperature_C"] + 1,
            "soc": r["soc"] - 0.1,
        }
        for r in measured[1:]
    ]
    result = evaluate(predicted, measured, reserve_soc=0.65)
    assert result["voltage_V"]["mae"] == 1
    assert result["power_total_W"]["rmse"] == 2
    assert result["energy_error_Wh"] == pytest.approx(4 / 3600)
    assert result["final_soc_error"] == pytest.approx(-0.1)
    assert result["thermal_peak_error_C"] == 1 and result["thermal_time_to_peak_error_s"] == 0
    assert result["cutoff_timing"]["error_s"] == 0
    assert result["derating_timing"]["error_s"] == 0
    assert result["reserve_violations"] == {"predicted": 2, "measured": 1}


def test_alignment_no_extrapolation_and_missing_channels():
    p = [{"time_s": 0, "voltage_V": 10}, {"time_s": 2, "voltage_V": 14}]
    m = [{"time_s": 0.5, "voltage_V": 11}, {"time_s": 1.5, "voltage_V": 13}]
    exact = evaluate(p, m, predicted_sample_kind="instantaneous")
    assert exact["voltage_V"] is None and exact["energy_error_Wh"] is None
    linear = evaluate(
        p, m, alignment="linear", predicted_sample_kind="instantaneous", reserve_soc=0.2
    )
    assert linear["voltage_V"]["rmse"] == 0
    assert linear["reserve_violations"] == {"predicted": None, "measured": None}


def test_energy_sampling_semantics_reject_gaps_and_mean_product():
    rows = [
        {"time_s": 1, "dt_s": 1, "voltage_V": 10, "current_A": 2},
        {"time_s": 2, "dt_s": 1, "voltage_V": 10, "current_A": 2},
    ]
    with pytest.raises(ConfigurationError, match="power_total_W"):
        energy(rows, sample_kind="interval_mean")
    for row in rows:
        row["power_total_W"] = 20
    assert energy(rows, sample_kind="interval_mean") == pytest.approx(40 / 3600)
    rows[-1]["dt_s"] = 0.5
    with pytest.raises(ConfigurationError, match="gaps/overlaps"):
        energy(rows, sample_kind="interval_mean")


def test_real_format_import_mapping_and_manifest_evaluation(tmp_path):
    m = write_csv(
        tmp_path / "measured.csv",
        [
            {
                "timestamp": t,
                "V": 12,
                "I": 2,
                "pack_T": 20,
                "thruster_commands": "[0,0]",
                "sensor_states": "{}",
            }
            for t in (0, 1, 2)
        ],
    )
    p = write_csv(
        tmp_path / "prediction.csv",
        [
            {"time_s": t, "dt_s": 1, "power_total_W": 24, "voltage_V": 12, "current_A": 2}
            for t in (1, 2)
        ],
    )
    mapping = {"voltage_V": "V", "current_A": "I", "temperature_C": "pack_T"}
    rows = read_series(m, columns=mapping)
    assert rows[0]["thruster_commands"] == [0, 0]
    manifest = manifest_for(tmp_path, [(m, "final_validation")])
    result = evaluate_files(p, m, manifest_path=manifest, run_id="test_0", measured_columns=mapping)
    assert result["voltage_V"]["rmse"] == 0
    assert result["provenance"]["dataset_kind"] == "synthetic_test_fixture"
    with pytest.raises(ConfigurationError, match="assigned"):
        evaluate_files(p, m, manifest_path=manifest, run_id="test_0", role="model_selection")


def test_offline_cli_compare_and_help(config, tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config))
    mission = write_csv(
        tmp_path / "commands.csv",
        [{"time_s": i * 0.1, "action": "[0,0,0,0,5,5,5,5]"} for i in range(3)],
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "holoenergy.analysis.cli",
            "compare",
            "--config",
            str(path),
            "--mission",
            str(mission),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "mission completion unknown" in result.stdout
    assert (tmp_path / "out/comparison.csv").exists()
