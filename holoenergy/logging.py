"""JSONL/CSV step logs and a reproducibility sidecar containing resolved inputs."""

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from ._validation import ConfigurationError, keys
from .provenance import file_hash, run_provenance, write_json

FIELDS = [
    "run_id",
    "fidelity_level",
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
    "water_temperature_C",
    "thermal_derating_factor",
    "minimum_voltage_V",
    "peak_current_A",
    "peak_temperature_C",
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
    "sensor_power_status",
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
        self.path = None
        self.metadata = run_provenance(resolved_config, context=context, run_id=self.run_id)
        self.metadata.update(
            {
                "model_warnings": model_warnings,
                "samples": "interval means for power/current/voltage; end states for SOC/temperature",
            }
        )
        self.rows_written = 0
        self.steps_completed = True
        if self.enabled:
            if not config.get("path"):
                raise ConfigurationError("Enabled logging requires path")
            path = Path(config["path"])
            path.parent.mkdir(parents=True, exist_ok=True)
            self.path = path
            write_json(path.with_suffix(path.suffix + ".metadata.json"), self.metadata)
            self.handle = path.open("w", encoding="utf-8", newline="")
            if self.format == "csv":
                self.writer = csv.DictWriter(self.handle, fieldnames=FIELDS)
                self.writer.writeheader()

    def write(self, row):
        self.rows_written += 1
        self.steps_completed = self.steps_completed and row["step_completed"]
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
            self.metadata.update(
                {
                    "closed_utc": datetime.now(timezone.utc).isoformat(),
                    "output_dataset_sha256": file_hash(self.path),
                    "rows_written": self.rows_written,
                    "status": "closed" if self.steps_completed else "partial",
                }
            )
            write_json(self.path.with_suffix(self.path.suffix + ".metadata.json"), self.metadata)
