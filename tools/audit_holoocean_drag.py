"""Non-invasive source/provenance audit and SI oracle for native BlueROV2 drag.

Does not import HoloEnergy or alter a simulator installation. Unsupported source
layouts fail explicitly: source parameters are never fitted to runtime outputs.
"""

import argparse
import hashlib
import importlib.metadata
import json
import math
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.holoocean_backend import package_identity, resolve_binary  # noqa: E402

BASE = "engine/Source/Holodeck/"
SOURCE_FILES = [
    "HolodeckCore/Private/HolodeckBuoyantAgent.cpp",
    "HolodeckCore/Public/HolodeckBuoyantAgent.h",
    "Agents/Private/BlueROV2.cpp",
    "Agents/Public/BlueROV2.h",
    "Agents/Private/BlueROV2ControlThrusters.cpp",
    "General/Private/Conversion.cpp",
    "General/Public/Conversion.h",
    "ClientCommands/Private/OceanCurrentsCommand.cpp",
    "Sensors/Private/DynamicsSensor.cpp",
]


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def git_info(path):
    def read(*args):
        result = subprocess.run(
            ["git", "-C", str(path), *args], capture_output=True, text=True, check=False
        )
        return result.stdout.strip() if result.returncode == 0 else None

    return {"commit": read("rev-parse", "HEAD"), "status": read("status", "--porcelain")}


def source_parameters(root):
    root = Path(root).resolve()
    text = {}
    fingerprints = {}
    for relative in SOURCE_FILES:
        path = root / BASE / relative
        text[relative] = path.read_text(encoding="utf-8-sig")
        fingerprints[BASE + relative] = {
            "sha256": file_hash(path),
            "line_anchors": {
                term: [i + 1 for i, line in enumerate(text[relative].splitlines()) if term in line]
                for term in ("DragForce", "RelativeVel", "AddForce", "ConvertLinearVector")
                if term in text[relative]
            },
        }

    def scalar(body, pattern, label):
        found = re.search(pattern, body)
        if not found:
            raise ValueError(f"Cannot identify {label} in this source; do not infer or fit it")
        value = float(found.group(1))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Invalid source value for {label}")
        return value

    vehicle = text["Agents/Private/BlueROV2.cpp"]
    buoyant = text["HolodeckCore/Private/HolodeckBuoyantAgent.cpp"]
    params = {
        "mass_kg": scalar(vehicle, r"MassInKG\s*=\s*([\d.]+)", "mass"),
        "drag_coefficient": scalar(vehicle, r"CoefficientOfDrag\s*=\s*([\d.]+)", "Cd"),
        "area_m2": scalar(vehicle, r"AreaOfDrag\s*=\s*([\d.]+)", "area"),
        "density_kg_m3": scalar(
            text["HolodeckCore/Public/HolodeckBuoyantAgent.h"],
            r"WaterDensity\s*=\s*([\d.]+)",
            "density",
        ),
        "ue_units_per_m": scalar(
            text["General/Public/Conversion.h"], r"UEUnitsPerMeter\s*=\s*([\d.]+)", "scale"
        ),
        "linear_damping_per_s": scalar(vehicle, r"SetLinearDamping\(([\d.]+)\)", "damping"),
    }
    if "RelativeVel.SizeSquared()" not in buoyant or "RelativeVel.GetSafeNormal()" not in buoyant:
        raise ValueError("Unsupported drag equation; manual source review required")
    scaled = "DragForce *= UEUnitsPerMeter;" in buoyant
    unsupported = "ConvertLinearVector(DragForce" in buoyant
    if unsupported:
        raise ValueError("Drag is already in UE axes: review any coordinate conversion manually")
    params.update(
        source_drag_scale_to_SI=1.0 if scaled else 1.0 / params["ue_units_per_m"],
        explicit_drag_unit_conversion=scaled,
        fully_submerged_ratio=1.0,
        neutral_volume_m3=params["mass_kg"] / params["density_kg_m3"],
        parameter_origin="official/local C++ literals; no runtime fit",
    )
    return {"root": str(root), "git": git_info(root), "parameters": params, "files": fingerprints}


def drag_force_N(velocity, current, parameters):
    """Source equation in SI/world axes, before any raw UE-force conversion."""
    relative = [float(v) - float(c) for v, c in zip(velocity, current, strict=True)]
    if len(relative) != 3 or not all(math.isfinite(v) for v in relative):
        raise ValueError("Velocity/current must be finite SI three-vectors")
    speed = math.sqrt(sum(v * v for v in relative))
    k = 0.5 * parameters["density_kg_m3"] * parameters["drag_coefficient"] * parameters["area_m2"]
    return [-k * speed * v * parameters["fully_submerged_ratio"] for v in relative]


def predicted_velocity(velocity, force_N, dt_s, parameters):
    """UE 5.3 Euler force step then ether damping, no collisions/substeps/overrides."""
    gain = max(0.0, 1.0 - parameters["linear_damping_per_s"] * dt_s)
    return [
        gain * (v + f * dt_s / parameters["mass_kg"])
        for v, f in zip(velocity, force_N, strict=True)
    ]


def runtime_provenance(binary=None):
    """Identity of the package actually launched (installed or separately built)."""
    import holoocean

    _, _, package_config = resolve_binary(binary)
    config = json.loads(package_config.read_text(encoding="utf-8"))
    modules = ["agents.py", "environments.py", "command.py", "sensors.py", "packagemanager.py"]
    client_root = Path(holoocean.__file__).parent
    identity = package_identity(binary)
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "holoocean_version": importlib.metadata.version("holoocean"),
        "client_root": str(client_root),
        "client_file_sha256": {name: file_hash(client_root / name) for name in modules},
        "client_install_origin": importlib.metadata.distribution("holoocean").read_text(
            "direct_url.json"
        ),
        **identity,
        "package_version": config["version"],
        "package_worlds": [world["name"] for world in config["worlds"]],
        "source_binary_build_identity": (
            "separate build: see build manifest"
            if identity["build_manifest_path"]
            else "not established by package version or behavioral conformance"
        ),
    }


def classify(scale, references_verified, source):
    """Do not select A/B/C when force-reference prerequisites are unresolved."""
    if not references_verified or not math.isfinite(scale):
        return "INCONCLUSIVE"
    if math.isclose(scale, 1, rel_tol=0.05):
        return "CASE A" if source["explicit_drag_unit_conversion"] else "CASE B"
    if math.isclose(scale, 0.01, rel_tol=0.05) or math.isclose(scale, 100, rel_tol=0.05):
        return "CASE C"
    return "INCONCLUSIVE"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--binary", type=Path, help="Optional separate build; never modifies a binary"
    )
    parser.add_argument("--output", type=Path, default=Path("logs/drag_audit/source_audit.json"))
    args = parser.parse_args()
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "holoenergy_repository": git_info(Path(__file__).resolve().parents[1]),
        "source": source_parameters(args.source_dir),
        "runtime": runtime_provenance(args.binary),
        "scope": "physics implementation verification, not physical vehicle validation",
    }
    write_json(args.output, result)
    print(f"Source/binary provenance: {args.output}")


if __name__ == "__main__":
    main()
