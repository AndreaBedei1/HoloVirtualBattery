"""One launch path for installed, rebuilt or patched native HoloOcean Ocean packages.

``make_env`` reproduces the parameters of ``holoocean.make(scenario_cfg=...)``
(world ``pre_start_steps`` and bounds from the package ``config.json``), but can
start a separately built executable. It never writes to a simulator package.
Comparisons between binaries therefore differ only in the executable.
"""

import copy
import hashlib
import json
import uuid
from pathlib import Path

PACKAGE_EXE = Path("Windows/Holodeck/Binaries/Win64/Holodeck.exe")
BUILD_MANIFEST = "holoenergy_build_manifest.json"


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def resolve_binary(binary=None):
    """Return (executable, package_root, package_config_path) for a package executable."""
    if binary is None:
        from holoocean import packagemanager

        binary = packagemanager.get_binary_path_for_package("Ocean")
    configured = Path(binary)
    executable = (
        configured if configured.suffix.lower() == ".exe" else Path(str(configured) + ".exe")
    )
    if not executable.is_file():
        raise FileNotFoundError(f"Native executable not found: {executable}")
    executable = executable.resolve()
    if tuple(p.lower() for p in executable.parts[-5:]) != tuple(
        p.lower() for p in PACKAGE_EXE.parts
    ):
        raise ValueError(f"Expected <package>/{PACKAGE_EXE.as_posix()}, got {executable}")
    package_root = executable.parents[4]
    config = package_root / "config.json"
    if not config.is_file():
        raise FileNotFoundError(f"Package config not found next to the executable: {config}")
    return executable, package_root, config


def make_env(scenario, ticks_per_sec, binary=None, show_viewport=False, verbose=False):
    """Start ``binary`` (default: installed Ocean) exactly as holoocean.make would start it."""
    from holoocean.environments import HoloOceanEnvironment

    executable, _, config_path = resolve_binary(binary)
    package_config = json.loads(config_path.read_text(encoding="utf-8"))
    worlds = [w for w in package_config["worlds"] if w["name"] == scenario["world"]]
    if len(worlds) != 1:
        raise ValueError(f"World {scenario['world']!r} not declared in {config_path}")
    world = worlds[0]
    scenario = copy.deepcopy(scenario)
    if "env_min" not in scenario and "env_min" in world:
        scenario["env_min"] = world["env_min"]
        scenario["env_max"] = world["env_max"]
    return HoloOceanEnvironment(
        scenario=scenario,
        binary_path=str(executable)[: -len(".exe")],
        start_world=True,
        uuid=str(uuid.uuid4()),
        gl_version=4,
        verbose=verbose,
        pre_start_steps=world["pre_start_steps"],
        show_viewport=show_viewport,
        ticks_per_sec=ticks_per_sec,
        frames_per_sec=False,
        copy_state=True,
    )


def package_identity(binary=None, hash_debug_symbols=True):
    """Executable/package identity; reads the build manifest of separately built packages."""
    executable, package_root, config = resolve_binary(binary)
    pdb = executable.with_suffix(".pdb")
    manifest_path = package_root / BUILD_MANIFEST
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
    )
    return {
        "binary_path": str(executable),
        "binary_sha256": file_hash(executable),
        "binary_size_bytes": executable.stat().st_size,
        "pdb_sha256": file_hash(pdb) if hash_debug_symbols and pdb.is_file() else None,
        "package_root": str(package_root),
        "package_config_path": str(config),
        "package_config_sha256": file_hash(config),
        "build_manifest_path": str(manifest_path) if manifest else None,
        "build_manifest_sha256": file_hash(manifest_path) if manifest else None,
        "build_variant": manifest.get("variant") if manifest else "installed package",
        "build_source_commit": manifest.get("holoocean_source", {}).get("commit")
        if manifest
        else None,
        "build_patch_sha256": manifest.get("patch", {}).get("sha256") if manifest else None,
    }
