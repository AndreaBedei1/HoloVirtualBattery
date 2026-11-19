"""Hardware library: compact, evidence-backed cards for the packaged real components.

Every number on a card is read from the packaged profile and its evidence records; this module
adds no values. Display names come from ``profiles/hardware_index.yaml`` (names only). The card
keeps two questions apart (brief: energy hardware vs simulated sensor):

* ``energy_model`` - is the device's electrical consumption modelled (``available``) or not
  (``unconfigured``: no defensible published power)?
* ``simulation`` - which HoloOcean sensor, if any, produces data for it. ``None`` is valid: the
  electrical load is still modelled, the measurement is not simulated.
"""

from __future__ import annotations

from functools import lru_cache
from importlib.resources import files

import yaml

from .catalog import BATTERIES, actuators, components, modems
from .config import _read
from .evidence import GRADES, cap_grade, default_registry

SOURCE_LABELS = {
    "journal_article": "Peer-reviewed paper",
    "conference_paper": "Peer-reviewed paper",
    "thesis": "Thesis",
    "manufacturer_datasheet": "Manufacturer datasheet",
    "manufacturer_dataset": "Manufacturer dataset",
    "manufacturer_web": "Manufacturer web page",
    "dataset": "Experimental dataset",
    "user": "User value",
    "simulator_source": "Simulator source",
    "standard": "Standard",
    "derived": "Derived",
}
CATEGORY_OF = {
    "components": None,
    "actuators": "propulsion",
    "batteries": "battery",
    "modems": "communications",
}


def _profiles():
    return files("holoenergy").joinpath("profiles")


@lru_cache(maxsize=1)
def _index():
    return yaml.safe_load(_profiles().joinpath("hardware_index.yaml").read_text(encoding="utf-8"))


def _worst(grades):
    grades = [g for g in grades if g in GRADES]
    return max(grades, key=GRADES.index) if grades else None


def _source_summary(registry, record):
    out = []
    for sid in record.sources:
        try:
            src = registry.source(sid)
        except Exception:  # noqa: BLE001 - an unknown source id is reported, not hidden
            out.append({"id": sid, "kind": "unknown", "title": None})
            continue
        out.append(
            {
                "id": src.id,
                "kind": SOURCE_LABELS.get(src.type, src.type),
                "title": src.title,
                "doi": src.doi,
                "url": src.url,
                "year": src.year,
            }
        )
    return out


def _state_row(registry, relation, state, spec):
    """One power state from a profile entry: evidence reference or explicit user number."""
    row = {
        "state": state,
        "power_W": None,
        "min_W": None,
        "max_W": None,
        "bound": None,
        "grade": None,
        "record": None,
        "relation": relation,
    }
    if isinstance(spec, dict) and "evidence" in spec:
        record = registry.get(spec["evidence"])
        use = spec.get("use", "value")
        row.update(record=record.id, grade=cap_grade(record.grade, relation), unit=record.unit)
        if record.configured:
            row["power_W"] = record.si(use) if getattr(record, use) is not None else None
            row["min_W"] = record.si("value_min") if record.value_min is not None else None
            row["max_W"] = record.si("value_max") if record.value_max is not None else None
            row["bound"] = (
                record.bound
                if use == "value"
                else ("upper_bound" if use == "value_max" else "lower_bound")
            )
        return row
    power = spec.get("power_W") if isinstance(spec, dict) else spec
    if power is not None:
        row.update(power_W=float(power), grade="D", bound="user")
    return row


def _component_card(key, path, registry):
    data = _read(_profiles().joinpath(*path.split("/")))
    meta = _index().get("components", {}).get(key, {})
    relation = data.get("relation", "exact")
    states = [_state_row(registry, relation, s, v) for s, v in (data.get("states") or {}).items()]
    powers = [x for r in states for x in (r["min_W"], r["max_W"], r["power_W"]) if x]
    status = data.get("status", "configured")
    return {
        "id": key,
        "kind": "component",
        "category": data.get("category", "sensors"),
        "type": meta.get("type", data.get("category", "sensors")),
        "manufacturer": meta.get("manufacturer"),
        "model": meta.get("model", key),
        "profile_name": data.get("name"),
        "supply_V": data.get("supply_V"),
        "states": states,
        "power_range_W": [min(powers), max(powers)] if powers else None,
        "grade": _worst([r["grade"] for r in states]) if status == "configured" else None,
        "relation": relation,
        "upper_bound": any(r["bound"] == "upper_bound" for r in states),
        "energy_model": "available" if status == "configured" and states else "unconfigured",
        "simulation": data.get("simulation_sensor"),
        "includes": data.get("includes", []),
        "sources": _sources(registry, states),
        "notes": _comment(path),
    }


def _modem_card(key, path, registry):
    data = _read(_profiles().joinpath(*path.split("/")))
    meta = _index().get("modems", {}).get(key, {})
    relation = data.get("relation", "exact")
    states = [_state_row(registry, relation, s, v) for s, v in (data.get("states") or {}).items()]
    powers = [x for r in states for x in (r["min_W"], r["max_W"], r["power_W"]) if x]
    return {
        "id": key,
        "kind": "modem",
        "category": "communications",
        "type": meta.get("type", f"{data.get('medium', '')} modem".strip()),
        "manufacturer": meta.get("manufacturer"),
        "model": meta.get("model", key),
        "medium": data.get("medium"),
        "supply_V": data.get("supply_V"),
        "states": states,
        "power_range_W": [min(powers), max(powers)] if powers else None,
        "grade": _worst([r["grade"] for r in states]),
        "relation": relation,
        "upper_bound": any(r["bound"] == "upper_bound" for r in states),
        "energy_model": "available" if states else "unconfigured",
        "simulation": "DESERT network events (holo_desert adapter)",
        "sources": _sources(registry, states),
        "notes": _comment(path),
    }


def _actuator_card(key, path, registry):
    data = _read(_profiles().joinpath(*path.split("/")))
    meta = _index().get("actuators", {}).get(key, {})
    md = data.get("metadata") or {}
    record_id = (
        (md.get("evidence") or {}).get("tables") if isinstance(md.get("evidence"), dict) else None
    )
    grade = None
    if record_id and record_id in registry.records:
        grade = registry.get(record_id).grade
    return {
        "id": key,
        "kind": "actuator",
        "category": "propulsion",
        "type": meta.get("type", "Thruster"),
        "manufacturer": meta.get("manufacturer", md.get("manufacturer")),
        "model": meta.get("model", md.get("model", key)),
        "supply_V": None,
        "operational_domain": md.get("operational_domain"),
        "status": md.get("status"),
        "grade": grade,
        "relation": data.get("relation", md.get("relation")),
        "energy_model": "available",
        "simulation": "HoloOcean thruster command (force, N)",
        "sources": [],
        "notes": _comment(path) or md.get("assumptions"),
    }


def _battery_card(key, path, registry):
    data = _read(_profiles().joinpath(*path.split("/")))
    meta = _index().get("batteries", {}).get(key, {})
    evidence = ((data.get("metadata") or {}).get("evidence")) or {}
    fields = []
    for name in (
        "capacity_Ah",
        "nominal_voltage_V",
        "cutoff_voltage_V",
        "max_current_A",
        "internal_resistance_ohm",
        "ocv_curve",
        "capacity_Wh",
    ):
        if name not in data:
            continue
        record_id = evidence.get(name)
        grade = None
        if record_id and record_id in registry.records:
            grade = registry.get(record_id).grade
        value = data[name]
        fields.append(
            {
                "field": name,
                "value": None if name == "ocv_curve" else value,
                "points": len(value) if name == "ocv_curve" else None,
                "record": record_id,
                "grade": grade or "D",
            }
        )
    return {
        "id": key,
        "kind": "battery",
        "category": "battery",
        "type": meta.get("type", "Battery"),
        "manufacturer": meta.get("manufacturer"),
        "model": meta.get("model", key),
        "chemistry": data.get("chemistry"),
        "cells": data.get("cells"),
        "model_kind": data.get("model"),
        "fields": fields,
        "grade": _worst([f["grade"] for f in fields]),
        "energy_model": "available",
        "simulation": None,
        "sources": [],
        "notes": _comment(path),
    }


def _sources(registry, states):
    seen, out = set(), []
    for row in states:
        if not row.get("record"):
            continue
        for src in _source_summary(registry, registry.get(row["record"])):
            if src["id"] not in seen:
                seen.add(src["id"])
                out.append(src)
    return out


def _comment(path):
    text = _profiles().joinpath(*path.split("/")).read_text(encoding="utf-8")
    lines = [line[1:].strip() for line in text.splitlines() if line.startswith("#")]
    return " ".join(lines) or None


def hardware_library(registry=None):
    """All packaged hardware as compact cards (components, modems, actuators, batteries)."""
    registry = registry or default_registry()
    cards = [_component_card(k, p, registry) for k, p in components().items()]
    cards += [_modem_card(k, p, registry) for k, p in modems().items()]
    cards += [_actuator_card(k, p, registry) for k, p in actuators().items()]
    cards += [_battery_card(k, BATTERIES[k], registry) for k in BATTERIES]
    return cards


def hardware_detail(kind, key, registry=None):
    """One card plus the full evidence records behind it (source, location, conditions)."""
    registry = registry or default_registry()
    card = next(
        (c for c in hardware_library(registry) if c["kind"] == kind and c["id"] == key), None
    )
    if card is None:
        raise KeyError(f"unknown {kind} {key!r}")
    record_ids = [r["record"] for r in card.get("states", []) if r.get("record")]
    record_ids += [f["record"] for f in card.get("fields", []) if f.get("record")]
    records = []
    for rid in dict.fromkeys(record_ids):
        if rid in registry.records:
            rec = registry.get(rid).to_dict()
            rec["source_details"] = _source_summary(registry, registry.get(rid))
            records.append(rec)
    return {**card, "records": records}


def library_counts(cards=None):
    """Counts used in the final report: by kind/category, evidence kind and bound."""
    cards = cards if cards is not None else hardware_library()
    out = {
        "total": len(cards),
        "by_kind": {},
        "by_type": {},
        "paper": 0,
        "datasheet": 0,
        "upper_bound_or_proxy": 0,
        "unconfigured": 0,
    }
    for c in cards:
        out["by_kind"][c["kind"]] = out["by_kind"].get(c["kind"], 0) + 1
        out["by_type"][c["type"]] = out["by_type"].get(c["type"], 0) + 1
        kinds = {s["kind"] for s in c.get("sources", [])}
        out["paper"] += "Peer-reviewed paper" in kinds
        out["datasheet"] += bool(
            kinds & {"Manufacturer datasheet", "Manufacturer web page", "Manufacturer dataset"}
        )
        out["upper_bound_or_proxy"] += bool(c.get("upper_bound") or c.get("relation") == "proxy")
        out["unconfigured"] += c.get("energy_model") == "unconfigured"
    return out
