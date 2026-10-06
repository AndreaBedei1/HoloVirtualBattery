"""User-specified one-at-a-time studies and independent Monte Carlo sampling (S12)."""

import copy
import csv
import json
import random
from pathlib import Path

from .._validation import ConfigurationError, keys, number, required
from ..provenance import digest, write_json
from .replay import run_mission


def parameter(config, path, value=None):
    parts = path.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current or not isinstance(current[part], dict):
            raise ConfigurationError(f"Unknown scalar parameter {path}")
        current = current[part]
    if parts[-1] not in current:
        raise ConfigurationError(f"Unconfigured parameter {path}")
    old = number(current[parts[-1]], path)
    if value is not None:
        current[parts[-1]] = number(value, path)
    return old


def study(config, commands, specification, output_dir, **run_kwargs):
    """Return every requested draw, including failures; never clip or resample invalid draws."""
    keys(specification, {"mode", "parameters", "seed", "samples", "independent"}, "study")
    mode = required(specification, "mode")
    parameters = required(specification, "parameters")
    if not isinstance(parameters, dict) or not parameters:
        raise ConfigurationError(
            "Specify at least one parameter and its perturbations/distribution"
        )
    baseline = {p: parameter(config, p) for p in parameters}
    scenarios = [("baseline", {}, None)]
    if mode == "sensitivity":
        for path, spec in parameters.items():
            keys(spec, {"values", "relative_changes"}, "sensitivity parameter")
            if ("values" in spec) == ("relative_changes" in spec):
                raise ConfigurationError("Supply exactly one of values or relative_changes")
            values = spec.get("values")
            if values is None:
                values = [
                    baseline[path] * (1 + number(x, "relative change", minimum=-1))
                    for x in spec["relative_changes"]
                ]
            if not values:
                raise ConfigurationError("Perturbations cannot be empty")
            for i, value in enumerate(values):
                scenarios.append(
                    (f"parameter_{len(scenarios):04d}_{i}", {path: number(value, path)}, None)
                )
    elif mode == "monte_carlo":
        if specification.get("independent") is not True:
            raise ConfigurationError(
                "Declare independent: true; correlated draws are not supported"
            )
        seed, samples = required(specification, "seed"), required(specification, "samples")
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise ConfigurationError("Monte Carlo seed must be an integer")
        if isinstance(samples, bool) or not isinstance(samples, int) or samples <= 0:
            raise ConfigurationError("Monte Carlo samples must be a positive integer")
        rng = random.Random(seed)

        def draw(spec):
            keys(spec, {"distribution", "low", "high", "mean", "std", "values"}, "distribution")
            kind = required(spec, "distribution")
            if kind == "uniform":
                lo, hi = (
                    number(required(spec, "low"), "low"),
                    number(required(spec, "high"), "high"),
                )
                if hi < lo:
                    raise ConfigurationError("uniform high must be >= low")
                return rng.uniform(lo, hi)
            if kind == "normal":
                return rng.gauss(
                    number(required(spec, "mean"), "mean"),
                    number(required(spec, "std"), "std", minimum=0),
                )
            if kind == "choice":
                values = required(spec, "values")
                if not values:
                    raise ConfigurationError("choice values cannot be empty")
                return rng.choice([number(x, "choice value") for x in values])
            raise ConfigurationError("distribution must be uniform, normal or choice")

        for i in range(samples):
            scenarios.append(
                (f"sample_{i:05d}", {p: draw(spec) for p, spec in parameters.items()}, seed)
            )
    else:
        raise ConfigurationError("mode must be sensitivity or monte_carlo")
    commands = list(commands)
    output_dir = Path(output_dir)
    records = []
    for label, overrides, seed in scenarios:
        candidate = copy.deepcopy(config)
        for path, value in overrides.items():
            parameter(candidate, path, value)
        record = {
            "label": label,
            "parameters": {**baseline, **overrides},
            "seed": seed,
            "configuration_sha256": digest(candidate),
        }
        try:
            result = run_mission(candidate, commands, output_dir / label, seed=seed, **run_kwargs)
            record.update(
                {
                    "status": "success",
                    **result["metrics"],
                    "run_id": result["provenance"]["run_id"],
                    "provenance_path": str(output_dir / label / "energy.jsonl.metadata.json"),
                }
            )
        except (ValueError, OSError, RuntimeError) as exc:
            record.update({"status": "failed", "error": str(exc)})
        records.append(record)
    report = {
        "specification": specification,
        "command_history_sha256": digest(commands),
        "interpretation": "User-specified study; not calibrated BlueROV2 uncertainty. "
        "Independent draws; invalid draws are retained as failures.",
        "records": records,
    }
    write_json(output_dir / "study.json", report)
    fields = sorted(set().union(*(r.keys() for r in records)))
    with (output_dir / "study.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({**record, "parameters": json.dumps(record["parameters"])})
    return report
