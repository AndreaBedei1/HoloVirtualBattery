"""Evaluate explicitly synchronized logs; no automatic time shift, extrapolation or calibration."""

import csv
import json
from bisect import bisect_left
from pathlib import Path

from .._validation import ConfigurationError, number
from ..provenance import file_hash
from .datasets import require_run
from .metrics import errors

NUMERIC = {
    "time_s",
    "dt_s",
    "voltage_V",
    "current_A",
    "power_total_W",
    "temperature_C",
    "water_temperature_C",
    "soc",
    "energy_used_Wh",
    "derating_factor",
    "completion_time_s",
}


def read_series(path, *, columns=None):
    """Canonical SI columns; optional mapping canonical->CSV column; retain extra fields."""
    path = Path(path)
    if path.suffix.lower() == ".jsonl":
        raw = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    else:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            raw = list(csv.DictReader(handle))
    result = []
    for source in raw:
        row = dict(source)
        for target, original in (columns or {}).items():
            if original not in source:
                raise ConfigurationError(f"Missing mapped column {original}")
            row[target] = source[original]
        if "time_s" not in row and "timestamp" in row:
            row["time_s"] = row["timestamp"]
        for key, value in list(row.items()):
            if value == "" or value is None:
                row[key] = None
            elif key in NUMERIC:
                row[key] = number(float(value), key)
            elif isinstance(value, str):
                try:
                    row[key] = json.loads(value)
                except ValueError:
                    pass
        if row.get("time_s") is None:
            raise ConfigurationError("Provide synchronized numeric time_s/timestamp in seconds")
        if result and row["time_s"] <= result[-1]["time_s"]:
            raise ConfigurationError(
                "Times must be finite and strictly increasing; split reset episodes"
            )
        if row.get("soc") is not None:
            number(row["soc"], "soc", minimum=0, maximum=1)
        if row.get("dt_s") is not None:
            number(row["dt_s"], "dt_s", positive=True)
        result.append(row)
    if len(result) < 2:
        raise ConfigurationError("At least two samples are required")
    return result


def _value_at(rows, times, t, key, alignment, tolerance):
    j = bisect_left(times, t)
    if j < len(times) and abs(times[j] - t) <= tolerance:
        return rows[j].get(key)
    if j and abs(times[j - 1] - t) <= tolerance:
        return rows[j - 1].get(key)
    if alignment == "exact":
        return None
    if j == 0 or j == len(times):
        return None
    a, b = rows[j - 1].get(key), rows[j].get(key)
    if a is None or b is None:
        return None
    return a + (b - a) * (t - times[j - 1]) / (times[j] - times[j - 1])


def energy(rows, *, sample_kind, start=None, end=None):
    """Full covered intervals or trapezoidal instantaneous power; no E from mean V*mean I."""

    def power(row):
        if row.get("power_total_W") is not None:
            return row["power_total_W"]
        if (
            sample_kind == "instantaneous"
            and row.get("voltage_V") is not None
            and row.get("current_A") is not None
        ):
            return row["voltage_V"] * row["current_A"]
        raise ConfigurationError("Energy requires power_total_W; instant V*I is also supported")

    if sample_kind == "interval_mean":
        total = 0.0
        previous_end = None
        for row in rows:
            if row.get("dt_s") is None:
                raise ConfigurationError("Interval means require dt_s and interval-end time_s")
            left, right = row["time_s"] - row["dt_s"], row["time_s"]
            if previous_end is not None and abs(left - previous_end) > 1e-8:
                raise ConfigurationError(
                    "Interval means contain gaps/overlaps; total energy unavailable"
                )
            previous_end = right
            duration = max(
                0,
                min(right, end if end is not None else right)
                - max(left, start if start is not None else left),
            )
            if duration:
                total += power(row) * duration
        return total / 3600
    if sample_kind != "instantaneous":
        raise ConfigurationError("sample_kind must be instantaneous or interval_mean")
    total = 0.0
    for a, b in zip(rows, rows[1:], strict=False):
        left, right = a["time_s"], b["time_s"]
        lo, hi = (
            max(left, start if start is not None else left),
            min(right, end if end is not None else right),
        )
        if hi <= lo:
            continue
        pa, pb = power(a), power(b)
        slope = (pb - pa) / (right - left)
        total += (pa + slope * (lo - left) + pa + slope * (hi - left)) * (hi - lo) / 2
    return total / 3600


def evaluate(
    predicted,
    measured,
    *,
    alignment="exact",
    tolerance_s=1e-8,
    predicted_sample_kind="interval_mean",
    measured_sample_kind="instantaneous",
    reserve_soc=None,
):
    if alignment not in ("exact", "linear"):
        raise ConfigurationError("alignment must be exact or linear (explicit opt-in)")
    tolerance_s = number(tolerance_s, "tolerance_s", minimum=0)
    times = [r["time_s"] for r in predicted]
    start = max(
        predicted[0]["time_s"] - (predicted[0].get("dt_s", 0) or 0)
        if predicted_sample_kind == "interval_mean"
        else predicted[0]["time_s"],
        measured[0]["time_s"] - (measured[0].get("dt_s", 0) or 0)
        if measured_sample_kind == "interval_mean"
        else measured[0]["time_s"],
    )
    end = min(predicted[-1]["time_s"], measured[-1]["time_s"])
    if end <= start:
        raise ConfigurationError("No common time interval")

    def paired(key):
        p, m, t = [], [], []
        for row in measured:
            if not start <= row["time_s"] <= end or row.get(key) is None:
                continue
            value = _value_at(predicted, times, row["time_s"], key, alignment, tolerance_s)
            if value is not None:
                p.append(value)
                m.append(row[key])
                t.append(row["time_s"])
        return p, m, t

    result = {
        "alignment": alignment,
        "tolerance_s": tolerance_s,
        "evaluation_interval_s": [start, end],
        "samples_measured": len(measured),
        "sampling_note": "Equal-weight paired metrics; align/resample with instrumentation knowledge. "
        "No automatic lag correction or extrapolation.",
    }
    for key in ("voltage_V", "current_A", "power_total_W", "temperature_C"):
        if key == "temperature_C" and all(r.get("fidelity_level") == "L0" for r in predicted):
            result[key] = None
            result["thermal_unavailable_reason"] = (
                "L0 reference temperature is not a thermal prediction"
            )
            continue
        p, m, t = paired(key)
        result[key] = errors(p, m) if p else None
        if key == "temperature_C" and p:
            ip, im = p.index(max(p)), m.index(max(m))
            result["thermal_peak_error_C"] = max(p) - max(m)
            result["thermal_time_to_peak_error_s"] = t[ip] - t[im]

    # Derive power only from instantaneous simultaneous voltage/current; preserve interval means.
    def with_power(rows, kind):
        return [
            {
                **r,
                "power_total_W": r.get("power_total_W")
                if r.get("power_total_W") is not None
                else (
                    r["voltage_V"] * r["current_A"]
                    if kind == "instantaneous"
                    and r.get("voltage_V") is not None
                    and r.get("current_A") is not None
                    else None
                ),
            }
            for r in rows
        ]

    measured_power = with_power(measured, measured_sample_kind)
    predicted_power = with_power(predicted, predicted_sample_kind)
    if result["power_total_W"] is None:
        p, m = [], []
        for row in measured_power:
            if row["power_total_W"] is not None and start <= row["time_s"] <= end:
                v = _value_at(
                    predicted_power, times, row["time_s"], "power_total_W", alignment, tolerance_s
                )
                if v is not None:
                    p.append(v)
                    m.append(row["power_total_W"])
        result["power_total_W"] = errors(p, m) if p else None
    try:
        ep = energy(predicted, sample_kind=predicted_sample_kind, start=start, end=end)
        em = energy(measured, sample_kind=measured_sample_kind, start=start, end=end)
        result.update(
            {
                "predicted_energy_Wh": ep,
                "measured_energy_Wh": em,
                "energy_error_Wh": ep - em,
                "relative_energy_error_percent": None if em == 0 else 100 * (ep - em) / em,
            }
        )
    except ConfigurationError as exc:
        result.update(
            {
                "energy_error_Wh": None,
                "relative_energy_error_percent": None,
                "energy_unavailable_reason": str(exc),
            }
        )
    end_p = _value_at(predicted, times, end, "soc", alignment, tolerance_s)
    measured_times = [r["time_s"] for r in measured]
    end_m = _value_at(measured, measured_times, end, "soc", alignment, tolerance_s)
    result["final_soc_error"] = None if end_p is None or end_m is None else end_p - end_m

    def event(rows, key):
        return next(
            (
                r["time_s"]
                for r in rows
                if start <= r["time_s"] <= end
                and (
                    r.get("battery_state") == "CUTOFF"
                    if key == "cutoff"
                    else r.get("derating_factor", 1) < 1 - 1e-9
                )
            ),
            None,
        )

    for key in ("cutoff", "derating"):
        tp, tm = event(predicted, key), event(measured, key)
        result[f"{key}_timing"] = {
            "predicted_s": tp,
            "measured_s": tm,
            "error_s": None if tp is None or tm is None else tp - tm,
        }
    result["mission_completed"] = {
        "predicted": predicted[-1].get("mission_completed"),
        "measured": measured[-1].get("mission_completed"),
    }
    cp, cm = predicted[-1].get("completion_time_s"), measured[-1].get("completion_time_s")
    result["completion_time"] = {
        "predicted_s": cp,
        "measured_s": cm,
        "error_s": None if cp is None or cm is None else cp - cm,
    }
    if reserve_soc is not None:
        reserve_soc = number(reserve_soc, "reserve_soc", minimum=0, maximum=1)
        result["reserve_violations"] = {
            label: None
            if not any(r.get("soc") is not None for r in rows)
            else sum(
                r.get("soc") is not None and r["soc"] < reserve_soc
                for r in rows
                if start <= r["time_s"] <= end
            )
            for label, rows in (("predicted", predicted), ("measured", measured))
        }
        result["reserve_threshold_soc"] = reserve_soc
    return result


def evaluate_files(
    predicted_path,
    measured_path,
    *,
    manifest_path,
    run_id,
    role="final_validation",
    measured_columns=None,
    **kwargs,
):
    manifest, run = require_run(manifest_path, run_id, role)
    if file_hash(measured_path) != run["sha256"]:
        raise ConfigurationError("Evaluation input is not the registered dataset")
    sidecar = Path(predicted_path).with_suffix(Path(predicted_path).suffix + ".metadata.json")
    predicted_metadata = (
        json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else None
    )
    if predicted_metadata and predicted_metadata.get("output_dataset_sha256") != file_hash(
        predicted_path
    ):
        raise ConfigurationError("Prediction sidecar/output hash mismatch")

    def check_identification(value):
        if isinstance(value, dict):
            for identity in value.get("calibration_runs", []):
                registered = next((r for r in manifest["runs"] if r["run_id"] == identity), None)
                if registered is None or registered["role"] != "parameter_identification":
                    raise ConfigurationError(
                        "Prediction profile uses a run outside parameter_identification"
                    )
            for child in value.values():
                check_identification(child)
        elif isinstance(value, list):
            for child in value:
                check_identification(child)

    if predicted_metadata:
        check_identification(predicted_metadata.get("resolved_config", {}))
    result = evaluate(
        read_series(predicted_path), read_series(measured_path, columns=measured_columns), **kwargs
    )
    result["provenance"] = {
        "manifest_sha256": manifest["manifest_sha256"],
        "run_id": run_id,
        "role": role,
        "dataset_kind": manifest["dataset_kind"],
        "predicted_sha256": file_hash(predicted_path),
        "measured_sha256": file_hash(measured_path),
        "prediction_provenance": predicted_metadata,
        "prediction_provenance_available": predicted_metadata is not None,
    }
    return result
