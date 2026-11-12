"""Paper tables generated from the registry, profiles and layouts (no hand-typed numbers).

* component_sources: subsystem, model/device, source, effective evidence grade, states, use
  (derived from data/evidence/final_parameter_audit.csv; run tools/build_parameter_audit.py first)
* vehicle_profiles: profile, HoloOcean dynamic class, classification (simulator exact /
  real exact / proxy / virtual layout / design), actuators, geometry evidence, propulsion and
  battery model, status

    uv run python tools/build_paper_tables.py [--output-dir docs/paper/tables]
"""

from __future__ import annotations

import argparse
import csv
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_offline_campaign import layouts  # noqa: E402

from holoenergy.allocation import ThrustAllocator  # noqa: E402
from holoenergy.catalog import list_profiles, vehicle_config  # noqa: E402
from holoenergy.config import load_config  # noqa: E402

GRADE_ORDER = "ABCD"


def write(out, name, rows, title, note):
    out.mkdir(parents=True, exist_ok=True)
    keys = list(rows[0])
    with (out / f"{name}.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, keys)
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        f"# {title}",
        "",
        note,
        "",
        "| " + " | ".join(keys) + " |",
        "| " + " | ".join("---" for _ in keys) + " |",
    ]
    lines += ["| " + " | ".join(str(r[k]) for k in keys) + " |" for r in rows]
    (out / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def component_sources():
    audit = ROOT / "data/evidence/final_parameter_audit.csv"
    rows = list(csv.DictReader(audit.open(encoding="utf-8")))
    groups = {}
    for r in rows:
        if r["status"] == "unlinked":
            continue
        key = (r["subsystem"], r["component"])
        g = groups.setdefault(
            key,
            {
                "states": set(),
                "grades": set(),
                "sources": set(),
                "ub": False,
                "use": set(),
                "unconf": False,
            },
        )
        how = r["used_as"].split(";")[0]
        g["states"].add(how.split(".")[-1].split(" ")[0] if "." in how else r["quantity"])
        g["grades"].add(r["effective_grade"])
        if r["source"]:
            g["sources"].add(r["source"].split(":")[0].strip())
        g["ub"] |= r["upper_bound_only"] == "True"
        g["use"].update(x for x in r["used_in"].split(";") if x)
        g["unconf"] |= r["status"] == "unconfigured"
    table = []
    for (subsystem, component), g in sorted(groups.items()):
        grades = sorted(g["grades"], key=GRADE_ORDER.index)
        table.append(
            {
                "Subsystem": subsystem,
                "Model/device": component,
                "Source": "; ".join(sorted(g["sources"]))[:90] or "none (unconfigured)",
                "Evidence": "-".join(dict.fromkeys([grades[0], grades[-1]]))
                + (" (upper bound)" if g["ub"] else "")
                + (" (gap)" if g["unconf"] else ""),
                "States/quantities": ", ".join(sorted(g["states"]))[:80],
                "Use": ", ".join(sorted(g["use"], key=lambda e: int(e[3:]))),
            }
        )
    return table


CLASSES = {
    "bluerov2-heavy": (
        "BlueROV2",
        "simulator exact (geometry, clamp, mass, drag literals of the HoloOcean agent); representative of a physical Heavy",
    ),
    "bluerov2-standard": (
        "BlueROV2 body",
        "virtual layout: 6T role-exact, vertical positions proxy (C), wrench-equivalent on the Heavy body",
    ),
    "torpedo-remus-like": (
        "TorpedoAUV",
        "proxy: REMUS-derived electrical models on a generic body",
    ),
    "torpedo-tethys-like": (
        "TorpedoAUV",
        "proxy: Tethys-derived electrical models on a generic body",
    ),
    "torpedo-autosub-like": (
        "TorpedoAUV",
        "proxy: Autosub LR6000-derived electrical models on a generic body",
    ),
    "hovering-mares-like": (
        "HoveringAUV",
        "proxy: MARES-derived electrical models on a generic body",
    ),
}


def battery_label(battery):
    if "capacity_Ah" in battery:
        return f"{battery.get('model')} {battery['capacity_Ah']} Ah"
    return f"{battery.get('model')} {battery.get('capacity_Wh')} Wh"


def vehicle_profiles():
    warnings.simplefilter("ignore", UserWarning)
    meta = list_profiles()["vehicles"]
    table = []
    for name, (body, cls) in CLASSES.items():
        config = load_config(data=vehicle_config(name))
        ev = config.get("evidence", {})
        thr = config["propulsion"].get("thruster") or config["propulsion"]["thrusters"][0]
        table.append(
            {
                "Profile": name,
                "HoloOcean body": body,
                "Classification": cls,
                "Actuators": config["propulsion"]["thruster_count"],
                "Propulsion model": (thr.get("metadata") or {}).get("model", thr.get("model")),
                "Propulsion evidence": f"{(ev.get('propulsion') or {}).get('record')} ({(ev.get('propulsion') or {}).get('relation')})",
                "Battery": battery_label(config["battery"]),
                "Catalog relation": meta[name]["relation"],
            }
        )
    for name, (geometry, description, grade) in layouts().items():
        if (
            name in ("L8-HV", "L6-STD")
            or name.startswith("L8-HV-a")
            and name not in ("L8-HV-a30", "L8-HV-a60")
        ):
            continue
        rank = ThrustAllocator(geometry).rank
        table.append(
            {
                "Profile": f"layout {name}",
                "HoloOcean body": "BlueROV2 body",
                "Classification": f"virtual design layout (geometry grade {grade}), wrench-equivalent; {description}",
                "Actuators": len(geometry),
                "Propulsion model": "T200",
                "Propulsion evidence": "bluerobotics_t200.static_force_power_curve (representative)",
                "Battery": "rint 18.0 Ah",
                "Catalog relation": f"design, rank {rank}",
            }
        )
    return table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/paper/tables")
    args = parser.parse_args(argv)
    write(
        args.output_dir,
        "component_sources",
        component_sources(),
        "Component sources (paper table)",
        "Generated by `tools/build_paper_tables.py` from the final parameter audit; Evidence = effective grade range after relation caps.",
    )
    write(
        args.output_dir,
        "vehicle_profiles",
        vehicle_profiles(),
        "Vehicle profiles and layouts (paper table)",
        "Generated by `tools/build_paper_tables.py`. No profile is a validated model of a physical vehicle.",
    )
    print("ok")


if __name__ == "__main__":
    main()
