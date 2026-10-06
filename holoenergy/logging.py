"""JSONL/CSV step logs and a reproducibility sidecar containing resolved inputs."""

import csv
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from . import __version__
from ._validation import ConfigurationError, keys

FIELDS = [
    "run_id",
    "episode",
    "step",
    "time_s",
    "dt_s",
    "soc",
    "available_soc",
    "voltage_V",
    "current_A",
    "power_total_W",
    "power_propulsion_W",
    "power_payload_W",
    "power_hotel_W",
    "power_conversion_loss_W",
    "power_battery_loss_W",
    "heat_generated_W",
    "requested_power_W",
    "available_power_W",
    "unmet_power_W",
    "temperature_C",
    "energy_used_Wh",
    "battery_internal_loss_Wh",
    "chemical_energy_used_Wh",
    "derating_factor",
    "auxiliary_service_factor",
    "battery_state",
    "cutoff_reason",
    "thruster_power_W",
    "sensor_power_W",
    "sensor_states",
    "requested_action",
    "applied_action",
    "actions_derated",
    "dynamics_energy_consistent",
    "temperature_outside_calibration",
    "model_warnings",
    "step_completed",
]


class EnergyLogger:
    def __init__(self, config, resolved_config, model_warnings, *, context=None):
        keys(config, {"enabled", "format", "path"}, "logging")
        self.enabled = config.get("enabled", False)
        if not isinstance(self.enabled, bool):
            raise ConfigurationError("logging.enabled must be a boolean")
        self.format = config.get("format", "jsonl")
        if self.format not in ("jsonl", "csv"):
            raise ConfigurationError("logging.format must be jsonl or csv")
        self.run_id = str(uuid4())
        self.handle = None
        self.writer = None
        if self.enabled:
            if not config.get("path"):
                raise ConfigurationError("Enabled logging requires path")
            path = Path(config["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            canonical = json.dumps(resolved_config, sort_keys=True, allow_nan=False)
            metadata = {
                "run_id": self.run_id,
                "holoenergy_version": __version__,
                "resolved_config_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
                "resolved_config": resolved_config,
                "model_warnings": model_warnings,
                "context": context or {},
                "samples": "interval means for power/current/voltage; end states for SOC/temperature",
            }
            path.with_suffix(path.suffix + ".metadata.json").write_text(
                json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
            )
            self.handle = path.open("w", encoding="utf-8", newline="")
            if self.format == "csv":
                self.writer = csv.DictWriter(self.handle, fieldnames=FIELDS)
                self.writer.writeheader()

    def write(self, row):
        if self.handle is None:
            return
        if self.format == "jsonl":
            self.handle.write(json.dumps(row, allow_nan=False) + "\n")
        else:
            self.writer.writerow(
                {
                    key: json.dumps(value, allow_nan=False)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )
        self.handle.flush()

    def close(self):
        if self.handle is not None:
            self.handle.close()
            self.handle = None
