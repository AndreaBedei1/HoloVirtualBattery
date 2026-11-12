"""Definitive HoloOcean 2.3.0 sensor -> electrical-load table (paper table + CSV).

Every sensor of the HoloOcean 2.3.0 registry (holoenergy.sensor_policy) is classified as
physical, derived/processed, simulator ground truth, host debug/rendering, or physical but
unmapped; for physical sensors the packaged representative component profiles are listed
with their states, power values, evidence grades and upper-bound flags.

    uv run python tools/build_sensor_table.py [--output-dir docs/paper/tables]
"""

from __future__ import annotations

import argparse
import csv
import json
from importlib.resources import files
from pathlib import Path

import yaml

from holoenergy import sensor_policy as sp
from holoenergy.catalog import profile_reference
from holoenergy.evidence import cap_grade, default_registry

ROOT = Path(__file__).resolve().parents[1]
CLASS = {
    "state": "simulator ground truth",
    "host": "debug/rendering (host side)",
    "derived": "derived/processed",
    "physical": "physical sensor",
    "unmapped": "physical sensor, no default device",
}
NOTES = {
    "PressureSensor": "contact pressure on the agent (ground truth), not a depth sensor; depth uses DepthSensor",
    "DepthSensor": "depth from pressure; mapped to a pressure transducer",
    "BSTSensor": "bathymetry/salinity/temperature (CTD-like)",
    "AcousticBeaconSensor": "HoloOcean's own acoustic messaging; electrical energy comes from the modem profile through the communication adapter (DESERT runs use their own PHY)",
    "OpticalModemSensor": "optical messaging; electrical energy from the optical modem profile",
    "GPSSensor": "fixes only near the surface in HoloOcean; device power applies whenever the receiver is powered",
}


def component_states(key):
    path = profile_reference(key, "component").removeprefix("package:")
    data = yaml.safe_load(
        files("holoenergy").joinpath("profiles", path).read_text(encoding="utf-8")
    )
    return data


def describe_profile(key, registry):
    if key.startswith("communications adapter"):
        return [
            {
                "profile": key,
                "state": "TX/RX/LISTEN/SLEEP",
                "power_W": "per modem profile",
                "grade": "see modem table",
                "upper_bound": "",
            }
        ]
    data = component_states(key)
    relation = data.get("relation", "exact")
    out = []
    for state, spec in (data.get("states") or {}).items():
        if isinstance(spec, dict) and spec.get("evidence"):
            r = registry.get(spec["evidence"])
            use = spec.get("use", "value")
            value = getattr(r, use) if r.configured else None
            if value is None and r.configured and r.value_min is not None:
                value = f"{r.value_min}-{r.value_max}"
            ub = (
                r.bound == "upper_bound"
                or use == "value_max"
                or data.get("active_is_upper_bound", False)
            )
            out.append(
                {
                    "profile": key,
                    "state": state,
                    "power_W": value if r.configured else "unconfigured",
                    "grade": cap_grade(r.grade, relation) if r.configured else "D",
                    "upper_bound": "yes" if ub and r.configured else "",
                    "record": r.id,
                }
            )
        else:
            out.append(
                {
                    "profile": key,
                    "state": state,
                    "power_W": spec,
                    "grade": "D",
                    "upper_bound": "",
                    "record": "",
                }
            )
    return out


def build():
    registry = default_registry()
    rows = []
    for sensor in sorted(sp.REGISTRY):
        c = sp.classify(sensor)
        kind = c["kind"]
        base = {
            "holoocean_sensor": sensor,
            "class": CLASS[kind],
            "default_behaviour": "",
            "real_world_mapping": "",
            "profile": "",
            "state": "",
            "power_W": "",
            "grade": "",
            "upper_bound": "",
            "record": "",
            "notes": NOTES.get(sensor, ""),
        }
        if kind in ("state", "host"):
            rows.append(
                base
                | {
                    "default_behaviour": "0 W (no hardware represented; attaching power is refused)",
                    "real_world_mapping": "none",
                }
            )
        elif kind == "derived":
            sensor_part, compute = sp.DERIVED[sensor]
            rows.append(
                base
                | {
                    "default_behaviour": "refused as an electrical load; configure the physical sensor + a compute workload",
                    "real_world_mapping": f"{sensor_part} + {compute}",
                }
            )
        elif kind == "unmapped":
            rows.append(
                base
                | {
                    "default_behaviour": "no load until the user configures a device",
                    "real_world_mapping": "no defensible default device",
                }
            )
        else:
            for key in sp.PHYSICAL[sensor]:
                for prof in describe_profile(key, registry):
                    rows.append(
                        base
                        | {
                            "default_behaviour": "load only if a component profile is configured",
                            "real_world_mapping": key,
                        }
                        | prof
                    )
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/paper/tables")
    args = parser.parse_args(argv)
    rows = build()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0])
    with (args.output_dir / "sensor_table.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, keys)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# HoloOcean 2.3.0 sensors and their electrical meaning",
        "",
        "Generated by `tools/build_sensor_table.py` from `holoenergy.sensor_policy` and the packaged",
        "component profiles. Grade after the profile's relation cap; UB = published maximum.",
        "",
        "| HoloOcean sensor | Class | Default | Mapping / profile | State | Power (W) | Grade | UB | Notes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        lines.append(
            f"| {r['holoocean_sensor']} | {r['class']} | {r['default_behaviour']} | {r['real_world_mapping']} | "
            f"{r['state']} | {r['power_W']} | {r['grade']} | {r['upper_bound']} | {r['notes']} |"
        )
    (args.output_dir / "sensor_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    summary = {}
    for r in rows:
        summary.setdefault(r["class"], set()).add(r["holoocean_sensor"])
    print(json.dumps({k: len(v) for k, v in summary.items()}))


if __name__ == "__main__":
    main()
