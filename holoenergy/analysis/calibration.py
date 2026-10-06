"""Import already identified PACK measurements; no fitting or missing-cell imputation."""

import csv
from collections import defaultdict
from pathlib import Path

from .._validation import ConfigurationError, number
from ..config import _merge
from ..models.battery import RintBattery
from ..provenance import digest, file_hash
from .datasets import verify_manifest


def csv_rows(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ConfigurationError(f"Empty measurement CSV: {path}")
    return rows


def measured_number(row, key, **bounds):
    if not row.get(key):
        raise ConfigurationError(f"Missing measurement {key}; no imputation is performed")
    try:
        return number(float(row[key]), key, **bounds)
    except ValueError as exc:
        raise ConfigurationError(f"Invalid {key}: {row[key]}") from exc


def battery_maps(
    path,
    *,
    capacity_path=None,
    current_path=None,
    reference_capacity_Ah=None,
    reference_current_A=None,
    protocol=None,
    manifest_path=None,
):
    rows = csv_rows(path)
    output, measured = {}, []
    for field, target in (
        ("ocv_V", "ocv_temperature_curves"),
        ("resistance_ohm", "resistance_soc_temperature_curves"),
    ):
        if not any(row.get(field) for row in rows):
            continue
        tables = defaultdict(dict)
        for row in rows:
            t = measured_number(row, "temperature_C", minimum=-273.14)
            soc = measured_number(row, "soc", minimum=0, maximum=1)
            if soc in tables[t]:
                raise ConfigurationError(
                    "Duplicate SOC/temperature measurement; preaggregate explicitly"
                )
            tables[t][soc] = measured_number(row, field, minimum=0, positive=field == "ocv_V")
        grid = None
        for table in tables.values():
            coordinates = sorted(table)
            if len(coordinates) < 2 or coordinates[0] != 0 or coordinates[-1] != 1:
                raise ConfigurationError("Each measured table must span reference SOC [0,1]")
            if grid is not None and coordinates != grid:
                raise ConfigurationError(
                    "Incomplete SOC-temperature grid; no imputation is performed"
                )
            grid = coordinates
        output[target] = [
            {"temperature_C": t, "curve": sorted(points.items())}
            for t, points in sorted(tables.items())
        ]
        if field == "ocv_V":
            for table in output[target]:
                RintBattery._ocv(table["curve"])
            # Required fallback: an explicitly measured first-temperature curve, not a fabricated one.
            output["ocv_curve"] = output[target][0]["curve"]
            measured.append("ocv_curve")
        measured.append(target)
    if not output:
        raise ConfigurationError("Provide measured ocv_V and/or resistance_ohm")
    inputs = [path]
    for extra_path, value_key, target, reference in (
        (
            capacity_path,
            "available_capacity_Ah",
            "capacity_temperature_curve",
            reference_capacity_Ah,
        ),
        (current_path, "max_current_A", "max_current_temperature_curve", reference_current_A),
    ):
        if extra_path is None:
            continue
        reference = number(reference, "explicit reference value", positive=True)
        table = {}
        for row in csv_rows(extra_path):
            t = measured_number(row, "temperature_C", minimum=-273.14)
            if t in table:
                raise ConfigurationError("Duplicate temperature measurement")
            table[t] = measured_number(row, value_key, minimum=0) / reference
            if not 0 < table[t] <= 1 and target == "capacity_temperature_curve":
                raise ConfigurationError("Reference capacity must be the highest usable capacity")
            if not 0 <= table[t] <= 1 and target == "max_current_temperature_curve":
                raise ConfigurationError(
                    "Reference current must cover every measured current limit"
                )
        output[target] = sorted(table.items())
        measured.append(target)
        inputs.append(extra_path)
    output["metadata"] = {
        "value_kind": "user_supplied_measured_maps",
        "measured_fields": measured,
        "input_sha256": {str(Path(p).resolve()): file_hash(p) for p in inputs},
        "protocol": protocol,
        "reference_capacity_Ah": reference_capacity_Ah,
        "reference_current_A": reference_current_A,
        "soc_basis": "reference-capacity SOC; NOT temperature-renormalized SOC",
        "calibration_status": "imported identified measurements; held-out validation not established",
        "notes": "Profile overlay only. Import does not establish traceability of instruments, "
        "rest/pulse suitability, or independent validation. Preserve unused placeholders.",
    }
    if manifest_path is not None:
        manifest = verify_manifest(manifest_path)
        registered = []
        for input_path in inputs:
            checksum = file_hash(input_path)
            run = next((r for r in manifest["runs"] if r["sha256"] == checksum), None)
            if run is None or run["role"] != "parameter_identification":
                raise ConfigurationError("Every map input must belong to parameter_identification")
            registered.append(run["run_id"])
        output["metadata"].update(
            {
                "calibration_runs": registered,
                "calibration_manifest_sha256": manifest["manifest_sha256"],
                "dataset_kind": manifest["dataset_kind"],
            }
        )
    return output


def apply_battery_maps(base, maps):
    """Keep unmeasured placeholders; replace status only for imported fields."""
    result = _merge(base, maps)
    for metadata_key, field in (
        ("reference_capacity_Ah", "capacity_Ah"),
        ("reference_current_A", "max_current_A"),
    ):
        reference = maps["metadata"].get(metadata_key)
        if reference is not None and reference != base[field]:
            raise ConfigurationError(f"Measured-map reference does not match base {field}")
    measured = set(maps["metadata"]["measured_fields"])
    superseded = set()
    if "resistance_soc_temperature_curves" in maps:
        superseded = {"internal_resistance_ohm", "resistance_temperature_curve"}
    result["metadata"]["placeholders"] = [
        p
        for p in base.get("metadata", {}).get("placeholders", [])
        if p not in measured | superseded
    ]
    result["metadata"]["superseded_fields"] = sorted(superseded)
    result["metadata"]["source_profile_sha256"] = digest(base)
    result["metadata"]["value_kind"] = "mixed_profile_with_imported_measurements"
    RintBattery(result)
    return result
