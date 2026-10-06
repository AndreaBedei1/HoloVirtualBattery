"""Serializable run provenance; no scientific status is inferred from a file hash."""

import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import __version__
from ._validation import ConfigurationError, keys
from .config import _placeholders


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def file_hash(path):
    checksum = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def git_state():
    root = Path(__file__).resolve().parent

    def git(*args):
        try:
            result = subprocess.run(
                ["git", "-C", str(root), *args],
                capture_output=True,
                text=True,
                timeout=5,
                check=True,
            )
            return result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            return None

    commit, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    repository_root = git("rev-parse", "--show-toplevel")
    if repository_root is None or (Path(repository_root) / "holoenergy").resolve() != root:
        return {
            "commit": None,
            "dirty": None,
            "working_tree_status": None,
            "reason": "Package is not the source tree of a Git checkout",
        }
    return {
        "commit": commit,
        "dirty": None if status is None else bool(status),
        "working_tree_status": status,
    }


def run_provenance(config, *, context=None, run_id=None):
    inputs = config.get("provenance", {})
    keys(
        inputs,
        {"scenario", "random_seed", "input_datasets", "calibration_status", "purpose", "manifest"},
        "provenance",
    )
    seed = inputs.get("random_seed")
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, int)):
        raise ConfigurationError("provenance.random_seed must be an integer or null")
    datasets = inputs.get("input_datasets", [])
    if not isinstance(datasets, list) or any(not isinstance(p, str) for p in datasets):
        raise ConfigurationError("provenance.input_datasets must be a list of file paths")
    try:
        holo_version = importlib.metadata.version("holoocean")
    except importlib.metadata.PackageNotFoundError:
        holo_version = None
    profiles = {
        k: config.get(k, {})
        for k in ("vehicle", "battery", "propulsion", "sensors", "components", "environment")
    }
    return {
        "run_id": run_id or str(uuid4()),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "holoenergy_version": __version__,
        "git": git_state(),
        "package_source_sha256": digest(
            {
                str(p.relative_to(Path(__file__).parent)).replace("\\", "/"): file_hash(p)
                for p in sorted(Path(__file__).parent.rglob("*"))
                if p.is_file() and p.suffix in (".py", ".yaml", ".json")
            }
        ),
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "holoocean_version": holo_version,
        "scenario": inputs.get("scenario"),
        "random_seed": seed,
        "resolved_config": config,
        "resolved_config_sha256": digest(config),
        "profiles": profiles,
        "profile_sha256": {k: digest(v) for k, v in profiles.items()},
        "input_datasets": {str(Path(p).resolve()): file_hash(p) for p in datasets},
        "placeholders": sorted(set(_placeholders(config))),
        "calibration_status": inputs.get("calibration_status", "unverified / not declared"),
        "purpose": inputs.get("purpose", "unspecified"),
        "manifest": inputs.get("manifest"),
        "context": context or {},
        "status": "running",
    }


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(path)
