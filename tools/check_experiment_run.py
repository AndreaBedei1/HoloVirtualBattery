"""Check one experimental run directory against experiments/schema (stdlib only).

Verifies metadata fields, the time-series column contract, declared units, strictly
increasing time, finite numbers, raw-file hashes and the in-water safety flag for
steps that power thrusters. It validates structure, not physical plausibility, and
never fills missing data.
"""

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "experiments/schema/run_metadata.schema.json"
REQUIRED_COLUMNS = [
    "time_s",
    "battery_voltage_V",
    "battery_current_A",
    "battery_temperature_C",
    "water_temperature_C",
    "mission_phase",
]
THRUSTER = re.compile(r"^thruster_[A-Za-z0-9]+_command_(N|pwm_us|norm)$")
STATE = {
    "depth_m",
    "position_x_m",
    "position_y_m",
    "position_z_m",
    "velocity_x_m_s",
    "velocity_y_m_s",
    "velocity_z_m_s",
    "roll_deg",
    "pitch_deg",
    "yaw_deg",
}
TEXT_COLUMNS = re.compile(r"^(mission_phase|sensor_[A-Za-z0-9_]+_state)$")
THRUSTER_STEPS = {
    "thruster_characterization_in_water",
    "hover",
    "surge",
    "sway",
    "yaw",
    "vertical",
    "calibration_mission",
    "held_out_validation_mission",
}


def unit_of(column):
    """Unit suffix encoded in a column name, e.g. battery_voltage_V -> V."""
    match = THRUSTER.match(column)
    if match:
        return match.group(1)
    for suffix in ("m_s", "pwm_us", "deg", "rpm", "W", "V", "A", "C", "m", "s"):
        if column.endswith("_" + suffix):
            return suffix
    return None


def check_metadata(metadata, schema):
    problems = []
    for key in schema["required"]:
        if key not in metadata:
            problems.append(f"metadata: missing '{key}'")
    properties = schema["properties"]
    for key in ("schema_version", "dataset_kind"):
        if key in metadata and metadata[key] != properties[key]["const"]:
            problems.append(f"metadata: {key} must be {properties[key]['const']!r}")
    for key in ("role", "protocol_step"):
        if key in metadata and metadata[key] not in properties[key]["enum"]:
            problems.append(f"metadata: invalid {key} {metadata[key]!r}")
    if not re.match(properties["run_id"]["pattern"], str(metadata.get("run_id", ""))):
        problems.append("metadata: run_id must match " + properties["run_id"]["pattern"])
    for block in ("vehicle", "battery", "environment", "time_sync", "safety"):
        required = properties[block].get("required", [])
        value = metadata.get(block, {})
        if not isinstance(value, dict):
            problems.append(f"metadata: {block} must be an object")
            continue
        problems += [f"metadata: {block}.{k} missing" for k in required if k not in value]
    safety = metadata.get("safety", {})
    if metadata.get("protocol_step") in THRUSTER_STEPS and not (
        safety.get("in_water") and safety.get("secured") and safety.get("authorized_personnel")
    ):
        problems.append("safety: thruster steps require in_water, secured, authorized_personnel")
    return problems


def check_run(run_dir):
    run_dir = Path(run_dir)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    problems = []
    metadata_path, series_path = run_dir / "metadata.json", run_dir / "timeseries.csv"
    if not metadata_path.is_file() or not series_path.is_file():
        return ["run needs metadata.json and timeseries.csv"], {}
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    problems += check_metadata(metadata, schema)
    with series_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])
        rows = list(reader)
    problems += [f"timeseries: missing column '{c}'" for c in REQUIRED_COLUMNS if c not in header]
    if not any(THRUSTER.match(c) for c in header):
        problems.append("timeseries: no thruster_<id>_command_<N|pwm_us|norm> column")
    if not STATE.intersection(header):
        problems.append("timeseries: no vehicle state column")
    channels = metadata.get("channels", {})
    for column in header:
        if column in ("time_s", "mission_phase"):
            continue
        declared = channels.get(column)
        if declared is None:
            problems.append(f"channels: '{column}' not declared in metadata")
        elif unit_of(column) not in (None, declared.get("unit")) and not TEXT_COLUMNS.match(column):
            problems.append(f"channels: unit of '{column}' is not {declared.get('unit')!r}")
    previous = -math.inf
    for number, row in enumerate(rows, start=2):
        if len(row) != len(header):
            problems.append(f"timeseries line {number}: {len(row)} cells, expected {len(header)}")
            continue
        for column, cell in zip(header, row, strict=True):
            if cell == "" or TEXT_COLUMNS.match(column):
                continue
            try:
                value = float(cell)
            except ValueError:
                problems.append(f"timeseries line {number}: '{column}' is not numeric")
                continue
            if not math.isfinite(value):
                problems.append(f"timeseries line {number}: '{column}' is not finite")
        try:
            time = float(row[header.index("time_s")])
        except (ValueError, IndexError):
            problems.append(f"timeseries line {number}: time_s missing")
            continue
        if not time > previous:
            problems.append(f"timeseries line {number}: time_s not strictly increasing")
        previous = time
    for item in metadata.get("raw_files", []):
        path = run_dir / item.get("path", "")
        if not path.is_file():
            problems.append(f"raw file missing: {item.get('path')}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item.get("sha256"):
            problems.append(f"raw file hash mismatch: {item.get('path')}")
    summary = {"samples": len(rows), "columns": header, "run_id": metadata.get("run_id")}
    return problems, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    problems, summary = check_run(args.run_dir)
    for problem in problems:
        print(f"FAIL: {problem}")
    if problems:
        sys.exit(1)
    print(
        f"PASS: {summary['run_id']} ({summary['samples']} samples, {len(summary['columns'])} columns)"
    )


if __name__ == "__main__":
    main()
