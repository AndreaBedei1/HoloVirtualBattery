"""Machine-readable audit of every scientific parameter used by the final experiment set.

The parameter list is derived from the configurations the final experiments actually load
(experiments/run_native_campaign.layout_config with the final layouts, suites and battery
fidelities; the modem profiles of the communication experiments) plus the registry records
used by the backend verification and the external comparison. Configuration values that
are not linked to an evidence record (placeholders, assumptions such as an ideal converter)
are listed explicitly as grade D rows instead of being omitted.

    uv run python tools/build_parameter_audit.py [--output-dir data/evidence]

Outputs final_parameter_audit.csv, .json and .md (paper-ready compact table).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_native_campaign import layout_config  # noqa: E402

from holoenergy.catalog import modem_profile  # noqa: E402
from holoenergy.evidence import RELATION_MAX_GRADE, cap_grade, default_registry  # noqa: E402

# Final experiment set (docs/paper/FINAL_EXPERIMENTS.md).
EXPERIMENTS = {
    "EXP1": "backend implementation verification (stock vs patched drag)",
    "EXP2": "component verification (T200, selected sensors and modems)",
    "EXP3": "actuator layout 4/6/8 and controllability",
    "EXP4": "thruster orientation",
    "EXP5": "environmental current: station keeping and transit",
    "EXP6": "sensor/compute payload",
    "EXP7": "communication (acoustic, optical, relay)",
    "EXP8": "battery fidelity L0 vs L1",
    "EXP9": "external literature comparison (BlueROV2 drag)",
    "EXP10": "uncertainty and sensitivity",
}
CONFIGS = {
    # (layout, mapping, suite, fidelity): experiments using that configuration
    ("L8-HV", "direct", None, "L1"): ["EXP3", "EXP4", "EXP5", "EXP7", "EXP8", "EXP10"],
    ("L6-STD", "wrench_equivalent", None, "L1"): ["EXP3"],
    ("L8-HV", "direct", "S0-propulsion-only", "L1"): ["EXP6"],
    ("L8-HV", "direct", "S5-inspection", "L1"): ["EXP6", "EXP10"],
    ("L8-HV", "direct", "S6-ai-vision", "L1"): ["EXP6"],
    ("L8-HV", "direct", None, "L0"): ["EXP8"],
}
MODEMS = {
    "evologics-s2cm-18-34-1000m": ["EXP2", "EXP7"],
    "hydromea-luma250lp-max": ["EXP2", "EXP7"],
}
STATIC = {
    "holoocean_bluerov2.drag_coefficient": ["EXP1", "EXP9"],
    "holoocean_bluerov2.drag_area": ["EXP1", "EXP9"],
    "holoocean_bluerov2.water_density": ["EXP1", "EXP9"],
    "holoocean_bluerov2.mass": ["EXP1"],
    "holoocean_bluerov2.linear_damping": ["EXP1", "EXP9"],
    "holoocean_bluerov2.thruster_clamp": ["EXP3", "EXP4", "EXP5"],
    "holoocean_bluerov2.actuator_geometry": ["EXP3", "EXP4", "EXP5"],
    "bluerov2_standard.restrained_inline_load_head_on": ["EXP9", "EXP10"],
    "bluerov2_standard.restrained_equivalent_drag_area": ["EXP9"],
    "bluerov2_heavy.translational_damping_identified": ["EXP9", "EXP10"],
    # EXP10 part 2: acoustic modem settings and interface variant (sensitivity only).
    "evologics_s2cm_18_34.tx_2000m": ["EXP10"],
    "evologics_s2cm_18_34.tx_3500m": ["EXP10"],
    "evologics_s2cm_18_34.tx_max": ["EXP10"],
    "evologics_s2cm_18_34.ethernet_interface_adder": ["EXP10"],
    "evologics_s2cm_18_34.bitrate": ["EXP10"],
    "bluerov2_heavy.translational_damping_wu2018": ["EXP9"],
}
# Records whose value enters through interpolation of a table/curve.
INTERPOLATED = {"bluerobotics_t200.static_force_power_curve", "bluerobotics_4s_18ah.ocv_curve"}
# Records applied outside the condition they were measured in (declared, not silent).
DOMAIN_NOTES = {
    "bluerobotics_t200.static_force_power_curve": "static (bollard) data applied with inflow "
    "from current and vehicle motion: outside the measured condition (relation representative)",
    "bluerobotics_4s_18ah.dc_resistance_cell_derived": "cell DCIR scaled to 4S6P; excludes "
    "interconnects and wiring (lower bound for the pack)",
}
COLUMNS = [
    "parameter_id",
    "subsystem",
    "component",
    "quantity",
    "value",
    "unit",
    "lower_bound",
    "upper_bound",
    "bound_type",
    "upper_bound_only",
    "source_id",
    "source",
    "doi_url",
    "page",
    "section",
    "table",
    "figure",
    "equation",
    "operating_conditions",
    "relation",
    "evidence_grade",
    "applied_relation",
    "effective_grade",
    "status",
    "used_in",
    "used_as",
    "interpolated",
    "extrapolated",
    "uncertainty",
    "notes",
]


def subsystem_of(record, used_as=""):
    q = (record.quantity if record else "") + " " + used_as
    comp = record.component if record else ""
    if any(k in comp for k in ("t200", "thruster")) or "thrust" in q:
        return "propulsion"
    if "4s_18ah" in comp or "battery" in used_as:
        return "battery"
    if comp.startswith("holoocean") or "drag" in q or "damping" in q or "restrain" in q:
        return "vehicle/hydrodynamics"
    if any(k in comp for k in ("evologics", "hydromea", "modem", "subnero", "sonardyne")):
        return "communications"
    if any(k in comp for k in ("rpi", "raspberry", "jetson", "navigator")):
        return "compute"
    if "thermal" in used_as:
        return "battery thermal"
    if "converter" in used_as or "bec" in comp:
        return "power conversion"
    return "sensors"


def source_fields(registry, record):
    names, links = [], []
    for sid in record.sources:
        s = registry.sources.get(sid)
        if s is None:
            continue
        who = (
            (s.authors[0].split()[-1] + (" et al." if len(s.authors) > 1 else ""))
            if s.authors
            else (s.publisher or "")
        )
        names.append(f"{who} {s.year or ''}: {s.title}".strip())
        links.append(f"doi:{s.doi}" if s.doi else (s.url or ""))
    return "; ".join(record.sources), " | ".join(names), " | ".join(x for x in links if x)


def worst(relations):
    """Most restrictive relation under which a record is applied (lowest grade cap)."""
    order = sorted(RELATION_MAX_GRADE, key=lambda k: RELATION_MAX_GRADE[k])
    return max(relations, key=order.index) if relations else "exact"


def record_row(registry, record_id, used_in, used_as, applied=("exact",)):
    r = registry.get(record_id)
    # Review A-03: the printed relation is the stricter of the record's own relation and the
    # relation of every link through which it is applied.
    relation = worst(set(applied) | {r.relation})
    sid, names, links = source_fields(registry, r)
    loc = r.location or {}
    unc = r.uncertainty if r.uncertainty else ""
    if isinstance(unc, (dict, list)):
        unc = json.dumps(unc, default=str)
    cond = r.conditions or {}
    return {
        "parameter_id": r.id,
        "subsystem": subsystem_of(r, used_as),
        "component": r.component,
        "quantity": r.quantity,
        "value": r.value
        if r.value is not None
        else ("dataset: " + r.dataset["path"] if r.dataset else None),
        "unit": r.unit,
        "lower_bound": r.value_min,
        "upper_bound": r.value_max,
        "bound_type": r.bound,
        # Only for powers: a limit (max current, max temperature) is not an energy bound.
        "upper_bound_only": (r.unit in ("W", "mW", "kW"))
        and (r.bound == "upper_bound" or "value_max" in used_as),
        "source_id": sid,
        "source": names,
        "doi_url": links,
        "page": loc.get("page"),
        "section": loc.get("section") or loc.get("line"),
        "table": loc.get("table"),
        "figure": loc.get("figure"),
        "equation": loc.get("equation"),
        "operating_conditions": json.dumps(cond, default=str) if cond else "",
        "relation": r.relation,
        "evidence_grade": r.grade,
        "applied_relation": relation,
        "effective_grade": cap_grade(r.grade, relation) if r.status == "configured" else "D",
        "status": r.status,
        "used_in": ";".join(sorted(set(used_in))),
        "used_as": used_as,
        "interpolated": r.id in INTERPOLATED,
        "extrapolated": False,
        "uncertainty": unc,
        "notes": " ".join(x for x in (DOMAIN_NOTES.get(r.id, ""), (r.notes or "").strip()) if x)[
            :600
        ],
    }


def config_row(
    pid, subsystem, component, value, unit, used_in, used_as, notes, relation="user", grade="D"
):
    return {
        "parameter_id": pid,
        "subsystem": subsystem,
        "component": component,
        "quantity": used_as,
        "value": json.dumps(value) if isinstance(value, (list, dict)) else value,
        "unit": unit,
        "lower_bound": None,
        "upper_bound": None,
        "bound_type": "placeholder/assumption",
        "upper_bound_only": False,
        "source_id": "",
        "source": "configuration value without an evidence record",
        "doi_url": "",
        "page": None,
        "section": None,
        "table": None,
        "figure": None,
        "equation": None,
        "operating_conditions": "",
        "relation": relation,
        "evidence_grade": grade,
        "applied_relation": relation,
        "effective_grade": grade,
        "status": "unlinked",
        "used_in": ";".join(sorted(set(used_in))),
        "used_as": used_as,
        "interpolated": False,
        "extrapolated": False,
        "uncertainty": "",
        "notes": notes,
    }


def collect():
    registry = default_registry()
    uses = {}  # record id -> (experiments, used_as, applied relations)
    extra = {}  # config parameter id -> row

    def use(record_id, exps, how, relation="exact"):
        if record_id is None:
            return
        e, h, rel = uses.setdefault(record_id, (set(), set(), set()))
        e.update(exps)
        h.add(how)
        rel.add(relation)

    for (layout, mapping, suite, fidelity), exps in CONFIGS.items():
        config, _ = layout_config(layout, mapping, suite=suite, fidelity=fidelity)
        ev = config.get("evidence", {})
        for key in ("propulsion", "battery_losses", "converters", "hotel_constant"):
            entry = ev.get(key)
            if isinstance(entry, dict) and entry.get("record"):
                use(
                    entry["record"],
                    exps,
                    f"vehicle evidence: {key}",
                    entry.get("relation", "exact"),
                )
        if layout == "L8-HV":
            use("holoocean_bluerov2.actuator_geometry", exps, "actuator geometry (simulator-exact)")
        battery = config["battery"]
        linked = (battery.get("metadata") or {}).get("evidence", {})
        for field, rid in linked.items():
            use(rid, exps, f"battery.{field}")
        for field in (
            "capacity_temperature_curve",
            "resistance_temperature_curve",
            "max_current_temperature_curve",
        ):
            if field in battery:
                extra.setdefault(
                    f"config:battery.{field}",
                    config_row(
                        f"config:battery.{field}",
                        "battery",
                        "bluerobotics_4s_18ah",
                        battery[field],
                        "-",
                        exps,
                        f"battery.{field}",
                        "identity curve: no temperature dependence modelled (placeholder, not a measurement)",
                    ),
                )
        thermal = config["thermal"]
        tmeta = thermal.get("metadata") or {}
        for field, rid in (tmeta.get("evidence") or {}).items():
            use(rid, exps, f"thermal.{field}")
        for field in tmeta.get("placeholders", []):
            if field in thermal:
                extra.setdefault(
                    f"config:thermal.{field}",
                    config_row(
                        f"config:thermal.{field}",
                        "battery thermal",
                        "bluerobotics_4s_18ah",
                        thermal[field],
                        {"thermal_capacity_J_per_C": "J/K", "cooling_coeff_W_per_C": "W/K"}.get(
                            field, "degC"
                        ),
                        exps,
                        f"thermal.{field}",
                        "placeholder (no enclosure thermal test); affects temperature and thermal derating only",
                    ),
                )
        conv = config.get("converters", {})
        cmeta = conv.get("metadata") or {}
        for field, rid in (cmeta.get("evidence") or {}).items():
            use(rid, exps, f"converters.{field} (record unconfigured; value 1.0 used)")
        for field in ("propulsion_efficiency", "payload_efficiency", "hotel_efficiency"):
            if field in conv:
                extra.setdefault(
                    f"config:converters.{field}",
                    config_row(
                        f"config:converters.{field}",
                        "power conversion",
                        "bluerov2",
                        conv[field],
                        "1",
                        exps,
                        f"converters.{field}",
                        "assumption: no conversion loss modelled (T200 data include ESC losses; 5 V supply losses unknown)",
                    ),
                )
        hotel = config.get("hotel_load", {})
        if "constant_W" in hotel:
            extra.setdefault(
                "config:hotel_load.constant_W",
                config_row(
                    "config:hotel_load.constant_W",
                    "auxiliaries",
                    "bluerov2",
                    hotel["constant_W"],
                    "W",
                    exps,
                    "hotel_load.constant_W",
                    "no unlisted hotel load; Fathom-X tether interface and ESC standby are unconfigured components (no published power)",
                ),
            )
        for comp in config["components"]:
            for state, spec in (comp.get("states") or {}).items():
                if isinstance(spec, dict) and spec.get("evidence"):
                    how = f"{comp['name']}.{state}" + (
                        f" (use {spec['use']})" if spec.get("use") else ""
                    )
                    use(spec["evidence"], exps, how, comp.get("relation", "exact"))
    for key, exps in MODEMS.items():
        profile = modem_profile(key)
        for state, spec in profile.get("states", {}).items():
            if isinstance(spec, dict) and spec.get("evidence"):
                how = f"modem {key}.{state}" + (f" (use {spec['use']})" if spec.get("use") else "")
                use(spec["evidence"], exps, how, profile.get("relation", "exact"))
    for rid, exps in STATIC.items():
        use(rid, exps, "backend / external comparison")
    rows = [
        record_row(registry, rid, sorted(e), "; ".join(sorted(h)), rel)
        for rid, (e, h, rel) in sorted(uses.items())
    ]
    rows += [extra[k] for k in sorted(extra)]
    return rows, registry


def write(rows, registry, out):
    out.mkdir(parents=True, exist_ok=True)
    with (out / "final_parameter_audit.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    meta = {
        "registry_version": registry.version,
        "experiments": EXPERIMENTS,
        "parameters": len(rows),
        "by_grade": {g: sum(r["evidence_grade"] == g for r in rows) for g in "ABCD"},
        "by_effective_grade": {g: sum(r["effective_grade"] == g for r in rows) for g in "ABCD"},
        "upper_bound_only": sum(bool(r["upper_bound_only"]) for r in rows),
        "unconfigured_or_unlinked": sum(r["status"] in ("unconfigured", "unlinked") for r in rows),
        "rows": rows,
    }
    (out / "final_parameter_audit.json").write_text(
        json.dumps(meta, indent=2, default=str) + "\n", encoding="utf-8"
    )
    lines = [
        "# Final parameter audit (paper table)",
        "",
        "Generated by `tools/build_parameter_audit.py`; full columns in the CSV/JSON. Grade = evidence",
        "grade after the relation cap; UB = value is a published maximum (energy is an upper bound).",
        "",
        f"Parameters: {meta['parameters']} (effective grade A {meta['by_effective_grade']['A']}, "
        f"B {meta['by_effective_grade']['B']}, C {meta['by_effective_grade']['C']}, "
        f"D {meta['by_effective_grade']['D']}); upper-bound-only powers {meta['upper_bound_only']}; "
        f"unconfigured or unlinked {meta['unconfigured_or_unlinked']}.",
        "",
        "| Parameter | Subsystem | Value | Unit | Applied relation | Grade | UB | Source | Used in |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        value = r["value"]
        if r["lower_bound"] is not None or r["upper_bound"] is not None:
            value = f"{r['lower_bound']}-{r['upper_bound']}" if value in (None, "") else value
        src = (r["source"] or "")[:70]
        lines.append(
            f"| `{r['parameter_id']}` | {r['subsystem']} | {value} | {r['unit'] or ''} | {r['applied_relation']} | "
            f"{r['effective_grade']} | {'yes' if r['upper_bound_only'] else ''} | {src} | {r['used_in']} |"
        )
    (out / "final_parameter_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return meta


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output-dir", type=Path, default=ROOT / "data/evidence")
    args = parser.parse_args(argv)
    warnings.simplefilter("ignore", UserWarning)
    rows, registry = collect()
    meta = write(rows, registry, args.output_dir)
    print({k: v for k, v in meta.items() if k != "rows" and k != "experiments"})


if __name__ == "__main__":
    main()
