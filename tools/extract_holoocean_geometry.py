"""Extract actuator geometry and backend constants of HoloOcean agents from C++ sources.

The output is the simulator-exact actuator layout used by HoloEnergy vehicle profiles:
positions and unit directions in the HoloOcean *client* body frame (x forward, y left,
z up, metres, origin at the centre of mass the agent uses when ``Perfect`` is true).

Derivation (HoloOcean v2.3.0, Agents/Private/<Agent>.cpp::ApplyThrusters):
  * thrusterLocations are UE units (cm) in the left-handed mesh frame; InitializeAgent
    subtracts CenterMass, which for Perfect agents is ((loc[0]+loc[2])/2 with z=loc[7].z);
  * forces are built in the client frame and converted with ConvertLinearVector(ClientToUE),
    which reverses y, hence client position = (x, -y, z) / 100;
  * BlueROV2/HoveringAUV: i<4 vertical +z; even i>=4 (1,1,0)/sqrt2; odd i>=4 (1,-1,0)/sqrt2;
  * SurfaceVessel: both thrusters along +x.
The script refuses to run when the patterns it relies on are absent.

Usage:
  python tools/extract_holoocean_geometry.py --source-dir <HoloOcean checkout> [--ref <git ref>]
"""

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "holoenergy" / "profiles" / "holoocean" / "agents_2.3.0.json"
AGENTS = "engine/Source/Holodeck/Agents"
VEC = re.compile(r"FVector\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)")


def read(source_dir, ref, rel):
    if ref:
        text = subprocess.run(
            ["git", "-C", str(source_dir), "show", f"{ref}:{rel}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    else:
        text = (Path(source_dir) / rel).read_text(encoding="utf-8")
    return text, hashlib.sha256(text.encode("utf-8")).hexdigest()


def constant(text, name):
    m = re.search(rf"const float {name}\s*=\s*([^;]+);", text)
    if not m:
        raise SystemExit(f"Constant {name} not found")
    return m.group(1).split("//")[0].strip()


def member(text, name):
    m = re.search(rf"this->{name}\s*=\s*([^;]+);", text)
    return None if not m else m.group(1).strip()


def locations(header):
    block = re.search(r"thrusterLocations\s*\{(.*?)\};", header, re.S)
    if not block:
        raise SystemExit("thrusterLocations not found")
    return [tuple(float(v) for v in m) for m in VEC.findall(block.group(1))]


def eight_thruster(name, source_dir, ref, mass_const_hint):
    header, h_sha = read(source_dir, ref, f"{AGENTS}/Public/{name}.h")
    cpp, c_sha = read(source_dir, ref, f"{AGENTS}/Private/{name}.cpp")
    for pattern in ("if (i < 4)", "i % 2 == 0", "LocalForce = FVector(0, 0, force)", "ClientToUE"):
        if pattern not in cpp:
            raise SystemExit(f"{name}: expected pattern {pattern!r} missing; geometry rule invalid")
    if not re.search(r"bool Perfect = true", header):
        raise SystemExit(f"{name}: Perfect default is not true; centre of mass rule invalid")
    loc = locations(header)
    if len(loc) != 8:
        raise SystemExit(f"{name}: expected 8 thrusters")
    com = ((loc[0][0] + loc[2][0]) / 2, (loc[0][1] + loc[2][1]) / 2, loc[7][2])
    s = 1 / math.sqrt(2)
    actuators = []
    for i, (x, y, z) in enumerate(loc):
        rx, ry, rz = (x - com[0]) / 100, -(y - com[1]) / 100, (z - com[2]) / 100
        if i < 4:
            d, role = (0.0, 0.0, 1.0), "vertical"
        elif i % 2 == 0:
            d, role = (s, s, 0.0), "horizontal_vectored"
        else:
            d, role = (s, -s, 0.0), "horizontal_vectored"
        actuators.append(
            {
                "backend_index": i,
                "role": role,
                "position_m": [round(rx, 6), round(ry, 6), round(rz, 6)],
                "direction": [round(v, 12) for v in d],
            }
        )
    max_thrust = constant(header, mass_const_hint)
    return {
        "agent_type": name,
        "control_scheme_thrusters": 0,
        "actuator_count": 8,
        "per_thruster_clamp_expression": max_thrust,
        "per_thruster_clamp_N": eval_clamp(header, max_thrust),
        "mass_kg": float(member(cpp, "MassInKG")),
        "drag_coefficient": float(member(cpp, "CoefficientOfDrag")),
        "drag_area_m2": float(member(cpp, "AreaOfDrag")),
        "volume_rule": "Perfect: Volume = MassInKG / WaterDensity (neutral buoyancy)",
        "centre_of_mass_rule": "Perfect: (loc[0]+loc[2])/2 with z = loc[7].z (UE units)",
        "actuators": actuators,
        "files": {f"{AGENTS}/Public/{name}.h": h_sha, f"{AGENTS}/Private/{name}.cpp": c_sha},
    }


def eval_clamp(header, expression):
    names = dict(re.findall(r"const float (\w+)\s*=\s*([-\d.]+)\s*;", header))
    expr = expression.replace("\n", " ")
    for key, value in names.items():
        expr = re.sub(rf"\b{key}\b", value, expr)
    if not re.fullmatch(r"[\d.\s*/+-]+", expr):
        raise SystemExit(f"Cannot evaluate clamp expression {expression!r}")
    return float(eval(expr))  # noqa: S307 - digits and arithmetic only (checked above)


def surface_vessel(source_dir, ref):
    header, h_sha = read(source_dir, ref, f"{AGENTS}/Public/SurfaceVessel.h")
    cpp, c_sha = read(source_dir, ref, f"{AGENTS}/Private/SurfaceVessel.cpp")
    if "FVector LocalForce = FVector(force, 0, 0)" not in cpp:
        raise SystemExit("SurfaceVessel: thrust direction pattern missing")
    loc = locations(header)
    com = VEC.search(member(cpp, "CenterMass")).groups()
    com = tuple(float(v) for v in com)
    actuators = [
        {
            "backend_index": i,
            "role": "stern_thruster",
            "position_m": [(x - com[0]) / 100, -(y - com[1]) / 100, (z - com[2]) / 100],
            "direction": [1.0, 0.0, 0.0],
        }
        for i, (x, y, z) in enumerate(loc)
    ]
    return {
        "agent_type": "SurfaceVessel",
        "control_scheme_thrusters": 0,
        "actuator_count": len(actuators),
        "per_thruster_clamp_N": float(constant(header, "SV_MAX_THRUST")),
        "mass_kg": float(member(cpp, "MassInKG")),
        "actuators": actuators,
        "files": {
            f"{AGENTS}/Public/SurfaceVessel.h": h_sha,
            f"{AGENTS}/Private/SurfaceVessel.cpp": c_sha,
        },
    }


def torpedo(source_dir, ref):
    header, h_sha = read(source_dir, ref, f"{AGENTS}/Public/TorpedoAUV.h")
    cpp, c_sha = read(source_dir, ref, f"{AGENTS}/Private/TorpedoAUV.cpp")
    m = re.search(r"FVector thruster = FVector\(([-\d.]+),\s*([-\d.]+),\s*([-\d.]+)\)", header)
    if not m or "FVector Thrust = FVector(ThrustToApply, 0, 0)" not in cpp:
        raise SystemExit("TorpedoAUV: thruster pattern missing")
    x, y, z = (float(v) for v in m.groups())
    return {
        "agent_type": "TorpedoAUV",
        "control_scheme_thrusters": 0,
        "actuator_count": 1,
        "per_thruster_clamp_N": float(constant(header, "TAUV_MAX_THRUST")),
        "fin_limit_deg": float(constant(header, "TAUV_MAX_FIN")),
        "mass_kg": float(member(cpp, "MassInKG")),
        "drag_coefficient": float(member(cpp, "CoefficientOfDrag")),
        "drag_area_m2": float(member(cpp, "AreaOfDrag")),
        "actuators": [
            {
                "backend_index": 0,
                "role": "propeller",
                "position_m": [x / 100, -y / 100, z / 100],
                "direction": [1.0, 0.0, 0.0],
            }
        ],
        "notes": "Fins are control surfaces without an electrical model in this extraction.",
        "files": {
            f"{AGENTS}/Public/TorpedoAUV.h": h_sha,
            f"{AGENTS}/Private/TorpedoAUV.cpp": c_sha,
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--ref", help="git ref holding pristine sources (e.g. a v2.3.0 commit)")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args(argv)
    result = {
        "holoocean_version": "2.3.0",
        "source": "https://github.com/byu-holoocean/HoloOcean (v2.3.0 engine sources)",
        "source_ref": args.ref,
        "frame": "HoloOcean client body frame: x forward, y left, z up; metres; origin at agent CoM",
        "generator": "tools/extract_holoocean_geometry.py",
        "agents": {
            "BlueROV2": eight_thruster("BlueROV2", args.source_dir, args.ref, "BR_MAX_THRUST"),
            "HoveringAUV": eight_thruster(
                "HoveringAUV", args.source_dir, args.ref, "AUV_MAX_THRUST"
            ),
            "SurfaceVessel": surface_vessel(args.source_dir, args.ref),
            "TorpedoAUV": torpedo(args.source_dir, args.ref),
        },
        "scope": (
            "Simulator-exact geometry and clamps of the HoloOcean agents. They are not measured "
            "geometries of the physical vehicles the agents resemble."
        ),
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
