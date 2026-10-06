"""Disjoint experimental-run manifests, verified by raw file hash and run identity."""

import json
from pathlib import Path

from .._validation import ConfigurationError, keys, required
from ..provenance import file_hash

ROLES = {"parameter_identification", "model_selection", "final_validation"}


def verify_manifest(path):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    keys(manifest, {"schema_version", "dataset_kind", "runs", "notes"}, "dataset manifest")
    if manifest.get("schema_version") != 1:
        raise ConfigurationError("Dataset manifest schema_version must be 1")
    if manifest.get("dataset_kind") not in ("experimental", "synthetic_test_fixture"):
        raise ConfigurationError("Declare dataset_kind: experimental or synthetic_test_fixture")
    runs = required(manifest, "runs")
    if not isinstance(runs, list) or not runs:
        raise ConfigurationError("Manifest must contain runs")
    seen_ids, seen_hashes, seen_groups = set(), set(), {}
    for run in runs:
        keys(
            run, {"run_id", "role", "path", "sha256", "independence_group", "notes"}, "dataset run"
        )
        identity, role = required(run, "run_id"), required(run, "role")
        if not isinstance(identity, str) or not identity or identity in seen_ids:
            raise ConfigurationError("Run IDs must be unique nonempty strings; no split-run reuse")
        if role not in ROLES:
            raise ConfigurationError(f"Unknown dataset role {role}")
        data_path = (path.parent / required(run, "path")).resolve()
        actual = file_hash(data_path)
        if actual != required(run, "sha256"):
            raise ConfigurationError(f"Dataset hash mismatch for {identity}")
        if actual in seen_hashes:
            raise ConfigurationError("The same dataset content cannot appear twice in a manifest")
        group = required(run, "independence_group")
        if not isinstance(group, str) or not group:
            raise ConfigurationError("Specify a cycle/mission independence_group")
        if group in seen_groups and seen_groups[group] != role:
            raise ConfigurationError(
                "One cycle/mission independence_group cannot cross dataset roles"
            )
        seen_ids.add(identity)
        seen_hashes.add(actual)
        seen_groups[group] = role
    return {**manifest, "manifest_sha256": file_hash(path), "verified": True}


def require_run(path, run_id, role):
    manifest = verify_manifest(path)
    run = next((r for r in manifest["runs"] if r["run_id"] == run_id), None)
    if run is None or run["role"] != role:
        raise ConfigurationError(f"Run {run_id} is not assigned to {role}")
    return manifest, run
