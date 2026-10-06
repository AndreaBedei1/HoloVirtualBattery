"""Synthetic device policies and software provenance, not hardware measurements."""

import json

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.provenance import digest, file_hash


def test_brownout_sheds_discrete_device_and_keeps_balance(fake, config):
    config["battery"]["max_current_A"] = 0.5
    config["sensors"]["Sonar"].update(
        {
            "load_kind": "discrete",
            "brownout": {"minimum_supplied_fraction": 1, "behavior": "latch_off"},
        }
    )
    with EnergyAwareEnv(fake, config=config) as env:
        e = env.step([0] * 8)["Energy"]
        assert e["sensor_power_status"]["Sonar"] == "BROWNOUT"
        assert e["sensor_power_W"]["Sonar"] == 0
        assert e["unmet_power_W"] >= 5 / 0.8
        assert e["power_total_W"] == pytest.approx(
            e["power_hotel_W"] + e["power_conversion_loss_W"]
        )
        assert env.step([0] * 8)["Energy"]["sensor_power_W"]["Sonar"] == 0
        env.reset()
        assert not env.payload.components["Sonar"].brownout_latched


def test_voltage_brownout_restart_delay_and_manual_override(fake, config):
    config["sensors"]["Sonar"].update(
        {
            "load_kind": "discrete",
            "brownout": {
                "minimum_bus_voltage_V": 16,
                "behavior": "auto_restart",
                "restart_delay_s": 0.3,
            },
        }
    )
    with EnergyAwareEnv(fake, config=config) as env:
        env.step([0] * 8)
        env.battery.ocv_curve = ((0, 17), (1, 17))
        assert env.step([0] * 8)["Energy"]["sensor_power_W"]["Sonar"] == 0
        assert env.step([0] * 8)["Energy"]["sensor_power_W"]["Sonar"] == 0
        assert env.step([0] * 8)["Energy"]["sensor_power_W"]["Sonar"] == 5
        env.set_payload_state("Sonar", "OFF")
        assert env.step([0] * 8)["Energy"]["sensor_power_W"]["Sonar"] == 0


def test_no_brownout_state_mutation_on_backend_failure(fake, config):
    config["sensors"]["Sonar"].update(
        {"load_kind": "discrete", "brownout": {"minimum_bus_voltage_V": 17}}
    )
    fake.fail_on = 0
    with EnergyAwareEnv(fake, config=config) as env:
        with pytest.raises(RuntimeError):
            env.step([0] * 8)
        assert not env.payload.components["Sonar"].brownout_latched


def test_sensor_linked_fails_explicitly(fake, config):
    config["sensors"]["Sonar"]["power_policy"] = "sensor_linked"
    with pytest.raises(ConfigurationError, match="no public electrical-state"):
        EnergyAwareEnv(fake, config=config)


def test_finalized_provenance_hashes_and_parameter_inputs(fake, config, tmp_path):
    source = tmp_path / "measured.csv"
    source.write_text("synthetic fixture only\n", encoding="utf-8")
    path = tmp_path / "out.csv"
    config["provenance"] = {
        "random_seed": 123,
        "input_datasets": [str(source)],
        "calibration_status": "synthetic test fixture",
        "scenario": "test",
    }
    config["logging"] = {"enabled": True, "format": "csv", "path": str(path)}
    with EnergyAwareEnv(fake, config=config) as env:
        resolved = env.config
        env.step([0] * 8)
    meta = json.loads(path.with_suffix(".csv.metadata.json").read_text())
    assert meta["git"]["commit"]
    assert meta["resolved_config_sha256"] == digest(resolved)
    assert meta["input_datasets"][str(source.resolve())] == file_hash(source)
    assert meta["output_dataset_sha256"] == file_hash(path)
    assert meta["random_seed"] == 123 and meta["status"] == "closed"
    assert meta["profiles"]["sensors"] == config["sensors"]
    assert meta["created_utc"] and meta["closed_utc"]


def test_failure_before_first_sample_is_recorded(fake, config, tmp_path):
    path = tmp_path / "failed.jsonl"
    config["logging"] = {"enabled": True, "format": "jsonl", "path": str(path)}
    fake.fail_on = 0
    with EnergyAwareEnv(fake, config=config) as env:
        with pytest.raises(RuntimeError):
            env.step([0] * 8)
    meta = json.loads(path.with_suffix(".jsonl.metadata.json").read_text())
    assert meta["status"] == "partial" and meta["rows_written"] == 0
    assert meta["run_error"]["type"] == "RuntimeError"
    assert meta["output_dataset_sha256"] == file_hash(path)
