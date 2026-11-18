"""Attribute every predicted Wh to the evidence grade of the parameters that produced it."""

from __future__ import annotations

import math

from .._validation import ConfigurationError
from . import GRADES, cap_grade, coverage, default_registry


def _matches(record, actual):
    """Does a configured number still equal (or lie inside) the linked record?"""
    if actual is None:
        return True
    try:
        actual = float(actual)
    except (TypeError, ValueError):
        return False
    point = record.si("value")
    if point is not None:
        return math.isclose(actual, point, rel_tol=1e-9, abs_tol=1e-12)
    low, high = record.si("value_min"), record.si("value_max")
    if low is None and high is None:
        return True  # dataset-backed record: checked by the caller
    return (low is None or actual >= low - 1e-12) and (high is None or actual <= high + 1e-12)


def _dataset_tables(record):
    """(key, tables) of an actuator dataset: JSON voltage_tables or YAML force_power_tables."""
    import importlib.resources
    import json

    import yaml

    path = (record.dataset or {}).get("path")
    if not path or not path.endswith((".json", ".yaml", ".yml")):
        return None
    from pathlib import Path

    try:
        local = Path(path)
        # Packaged datasets are package-relative; a user's own dataset may be an absolute path.
        source = (
            local if local.is_absolute() else importlib.resources.files("holoenergy").joinpath(path)
        )
        text = source.read_text(encoding="utf-8")
        data = json.loads(text) if path.endswith(".json") else yaml.safe_load(text)
    except (FileNotFoundError, OSError, ValueError, yaml.YAMLError):
        return None
    if not isinstance(data, dict):
        return None
    for key in ("voltage_tables", "force_power_tables"):
        if key in data:
            return key, data[key]
    return None


DYNAMICS_SOURCES = (
    "simulator_literal",  # coefficients of the simulator's own model (exact for the simulator)
    "published_measurement",  # measured on a physical vehicle (e.g. restrained load in a basin)
    "identified_model",  # model identified from vehicle data
    "proxy",  # a different vehicle or condition
    "unsupported",
)
DYNAMICS_CONSISTENCY = ("consistent", "weak", "conflicting", "not_assessed")
DYNAMICS_VALIDATION = ("validated", "partial", "absent")


def _dynamics_evidence(entry, registry):
    """Evidence for the physical (dynamics) model, kept apart from the electrical grades
    (review I-03): one label each for source, external consistency and validation."""
    from .._validation import ConfigurationError, keys

    entry = dict(entry or {})
    keys(
        entry,
        {"source", "records", "external_consistency", "validation", "notes"},
        "evidence.dynamics",
    )
    source = entry.get("source", "unsupported")
    consistency = entry.get("external_consistency", "not_assessed")
    validation = entry.get("validation", "absent")
    for value, allowed, name in (
        (source, DYNAMICS_SOURCES, "source"),
        (consistency, DYNAMICS_CONSISTENCY, "external_consistency"),
        (validation, DYNAMICS_VALIDATION, "validation"),
    ):
        if value not in allowed:
            raise ConfigurationError(f"evidence.dynamics.{name} must be one of {allowed}")
    records = list(entry.get("records") or [])
    for record_id in records:
        registry.get(record_id)  # every cited record must exist
    return {
        "source": source,
        "records": records,
        "external_consistency": consistency,
        "validation": validation,
        "notes": entry.get("notes"),
    }


def _actuator_ids(propulsion):
    count = propulsion.get("thruster_count") or len(propulsion.get("thrusters") or [])
    return list(propulsion.get("actuator_ids") or [f"T{i + 1}" for i in range(count)])


def _actuator_models(propulsion):
    ids = _actuator_ids(propulsion)
    models = propulsion.get("thrusters")
    return list(models) if models else [propulsion.get("thruster")] * len(ids)


def _graded(registry, entry):
    if not isinstance(entry, dict) or entry.get("record") is None:
        return "D", None
    record = registry.get(entry["record"])
    if not record.configured:
        return "D", record.id
    return cap_grade(record.grade, entry.get("relation", "exact")), record.id


def _bus_voltage_range(battery):
    """Range of the bus voltage the pack can present: [cutoff, maximum OCV] (L1) or the
    nominal voltage (L0). (None, None) when the battery does not state it."""
    nominal = battery.get("nominal_voltage_V")
    curve = battery.get("ocv_curve") or []
    voltages = [float(p[1]) for p in curve if isinstance(p, (list, tuple)) and len(p) == 2]
    if battery.get("model") == "rint" and voltages:
        cutoff = battery.get("cutoff_voltage_V")
        low = float(cutoff) if cutoff is not None else min(voltages)
        return (low, max(voltages))
    if nominal is not None:
        return (float(nominal), float(nominal))
    return (None, None)


class EvidenceMap:
    """Evidence grade per device/state plus category-level grades for losses."""

    def __init__(self, config, payload, propulsion, registry=None):
        self.registry = registry or default_registry()
        evidence = config.get("evidence", {}) or {}
        self.propulsion_grade, self.propulsion_record = _graded(
            self.registry, evidence.get("propulsion")
        )
        self.battery_loss_grade, self.battery_loss_record = _graded(
            self.registry, evidence.get("battery_losses")
        )
        self.converter_grade, self.converter_record = _graded(
            self.registry, evidence.get("converters")
        )
        self.hotel_grade, self.hotel_record = _graded(self.registry, evidence.get("hotel_constant"))
        self.category_relations = {
            category: (evidence.get(category) or {}).get("relation")
            for category in ("battery_losses", "converters")
        }
        self.vehicle_relation = evidence.get("vehicle_relation")
        self.dynamics = _dynamics_evidence(evidence.get("dynamics"), self.registry)
        battery = config.get("battery") or {}
        ocv_record = ((battery.get("metadata") or {}).get("evidence") or {}).get("ocv_curve")
        self.bus_voltage_model = battery.get("model")
        self.ocv_record = ocv_record
        if battery.get("model") == "rint":
            self.ocv_grade = (
                _graded(self.registry, {"record": ocv_record, "relation": "exact"})[0]
                if ocv_record
                else "D"
            )
        else:
            self.ocv_grade = None  # L0: nominal voltage, no OCV curve
        self.propulsion_relation = (evidence.get("propulsion") or {}).get("relation")
        self.stale_links = self._check_links(config)
        (
            self.actuator_grades,
            self.actuator_records,
            self.actuator_relations,
        ) = self._actuator_links(config, list(propulsion.ids))
        self.double_counting_policy = evidence.get("double_counting", "warn")
        if self.double_counting_policy not in ("warn", "error"):
            from .._validation import ConfigurationError

            raise ConfigurationError("evidence.double_counting must be warn or error")
        self.actuators = list(propulsion.ids)
        self.devices, self.bounds, self.records, self.relations = {}, {}, {}, {}
        self.used_powers = {}
        converters = config.get("converters") or {}
        self.efficiencies = {
            "propulsion": float(converters.get("propulsion_efficiency", 1.0)),
            "payload": float(converters.get("payload_efficiency", 1.0)),
            "hotel": float(converters.get("hotel_efficiency", 1.0)),
        }
        self.unconfigured, self.legacy_unlinked = [], []
        capabilities = {}
        for name, item in payload.components.items():
            grades = getattr(item, "state_grades", None)
            if grades is None:
                self.legacy_unlinked.append(name)
                grades = {}
            self.devices[name] = dict(grades)
            self.relations[name] = getattr(item, "relation", "exact")
            self.used_powers[name] = dict(getattr(item, "state_powers", {}) or {})
            self.bounds[name] = dict(getattr(item, "state_bounds", {}))
            self.records[name] = dict(getattr(item, "state_evidence", {}))
            if getattr(item, "status", "configured") == "unconfigured":
                self.unconfigured.append(
                    {"component": name, "device": getattr(item, "device", None)}
                )
            for capability in getattr(item, "includes", []):
                capabilities.setdefault(capability, []).append(name)
        self.capabilities = capabilities
        self._update_double_counting()
        self.external = {}
        self.voltage_independent_actuators = [
            aid
            for aid, model in zip(propulsion.ids, propulsion.thrusters, strict=True)
            if getattr(model, "voltage_policy", "measured") == "table_voltage"
        ]
        self.rail_verified = self._rail_verification(config, converters)
        self.bus_voltage_range = _bus_voltage_range(battery)
        self.supply_mismatches = self._supply_mismatches(payload)

    def _rail_verification(self, config, converters):
        """Whether the converter efficiency of the payload and hotel rails rests on evidence.

        A rail charged at efficiency 1.0 without a configured record has its conversion loss
        unmodelled: the energy of its loads is then a lower bound (open upper side). The
        propulsion rail is not checked: actuator tables give battery-side (ESC input) power.
        """
        linked = ((converters.get("metadata") or {}).get("evidence")) or {}
        verified = {}
        for rail in ("payload", "hotel"):
            record_id = linked.get(f"{rail}_efficiency")
            has_evidence = bool(self.converter_record) and self.converter_grade != "D"
            if record_id is not None and record_id in self.registry.records:
                has_evidence = has_evidence or self.registry.get(record_id).configured
            # An efficiency below 1 is a modelled (if user-graded) loss, not an open side.
            verified[rail] = has_evidence or self.efficiencies[rail] < 1.0
        return verified

    def _supply_mismatches(self, payload):
        """Components whose declared supply domain does not contain the bus voltage range and
        that no converter component declares to serve."""
        served = {
            name for item in payload.components.values() for name in getattr(item, "serves", [])
        }
        low, high = self.bus_voltage_range
        result = {}
        for name, item in payload.components.items():
            supply = getattr(item, "supply_V", None)
            if supply is None or low is None or name in served:
                continue
            if low < supply[0] - 1e-9 or high > supply[1] + 1e-9:
                result[name] = {"supply_V": list(supply), "bus_V": [low, high]}
        return result

    def _update_double_counting(self):
        self.double_counting = {
            cap: names for cap, names in sorted(self.capabilities.items()) if len(names) > 1
        }
        if self.double_counting and self.double_counting_policy == "error":
            from .._validation import ConfigurationError

            raise ConfigurationError(
                "double counting rejected (evidence.double_counting: error): "
                + "; ".join(f"'{c}' by {', '.join(n)}" for c, n in self.double_counting.items())
            )

    def _check_links(self, config):
        """Drop evidence links whose record no longer describes the configured value.

        A profile links e.g. battery losses to a resistance record; a user override of
        ``battery.internal_resistance_ohm`` (or of the actuator tables, hotel load or
        converter efficiencies) makes that link stale. The energy is then graded D (user)
        and a warning names the link, instead of crediting the record's grade.
        """
        stale = []

        def drop(kind, record_id, why):
            setattr(self, f"{kind}_grade", "D")
            setattr(self, f"{kind}_record", None)
            if kind == "propulsion":
                self.propulsion_relation = "user"
            stale.append(f"stale evidence link: {kind} -> {record_id} ({why}); graded D")

        if self.battery_loss_record:
            record = self.registry.get(self.battery_loss_record)
            battery = config.get("battery") or {}
            actual = battery.get("internal_resistance_ohm")
            curve = battery.get("resistance_temperature_curve") or []
            if battery.get("resistance_soc_temperature_curves"):
                drop("battery_loss", record.id, "resistance SOC/temperature map not in the record")
            elif any(abs(float(p[1]) - 1.0) > 1e-12 for p in curve):
                drop("battery_loss", record.id, "resistance temperature factors not in the record")
            elif not _matches(record, actual):
                drop("battery_loss", record.id, f"internal_resistance_ohm={actual}")
        if self.hotel_record:
            record = self.registry.get(self.hotel_record)
            actual = (config.get("hotel_load") or {}).get("constant_W")
            if not _matches(record, actual):
                drop("hotel", record.id, f"hotel_load.constant_W={actual}")
        if self.converter_record:
            record = self.registry.get(self.converter_record)
            for key, actual in (config.get("converters") or {}).items():
                if key.endswith("_efficiency") and not _matches(record, actual):
                    drop("converter", record.id, f"converters.{key}={actual}")
                    break
        self.propulsion_mismatch_ids = []
        if self.propulsion_record:
            record = self.registry.get(self.propulsion_record)
            found = _dataset_tables(record)
            propulsion = config.get("propulsion") or {}
            ids = _actuator_ids(propulsion)
            own = set((config.get("evidence") or {}).get("actuators") or {})
            if found is not None:
                key, tables = found
                models = _actuator_models(propulsion)
                differ = [
                    aid
                    for aid, m in zip(ids, models, strict=True)
                    if aid not in own and (not isinstance(m, dict) or m.get(key) != tables)
                ]
                if differ and len(differ) == len([a for a in ids if a not in own]):
                    drop(
                        "propulsion", record.id, "actuator tables differ from the record's dataset"
                    )
                elif differ:
                    # Review H2: only the actuators that do not match lose the link.
                    self.propulsion_mismatch_ids = differ
                    stale.append(
                        f"stale evidence link: propulsion -> {record.id} for {', '.join(differ)} "
                        "(their tables differ from the record's dataset); those actuators graded D"
                    )
        return stale

    def _actuator_links(self, config, ids):
        """Per-actuator evidence (``evidence.actuators: {id: {record, relation}}``), falling back
        to the shared ``evidence.propulsion`` link."""
        links = (config.get("evidence") or {}).get("actuators") or {}
        unknown = sorted(set(links) - set(ids))
        if unknown:
            from .._validation import ConfigurationError

            raise ConfigurationError(f"evidence.actuators names unknown actuators {unknown}")
        models = dict(zip(ids, _actuator_models(config.get("propulsion") or {}), strict=True))
        grades, records, relations = {}, {}, {}
        for aid in ids:
            if aid in links:
                grade, record_id = _graded(self.registry, links[aid])
                relation = links[aid].get("relation", "exact")
                found = _dataset_tables(self.registry.get(record_id)) if record_id else None
                model = models.get(aid)
                if found is not None and (
                    not isinstance(model, dict) or model.get(found[0]) != found[1]
                ):
                    self.stale_links.append(
                        f"stale evidence link: actuator {aid} -> {record_id} (tables differ "
                        "from the record's dataset); graded D"
                    )
                    grade, record_id, relation = "D", None, "user"
            elif aid in self.propulsion_mismatch_ids:
                grade, record_id, relation = "D", None, "user"
            else:
                grade, record_id = self.propulsion_grade, self.propulsion_record
                relation = self.propulsion_relation
            grades[aid], records[aid], relations[aid] = grade, record_id, relation
        return grades, records, relations

    def efficiency_for(self, device):
        """Converter efficiency of the rail that serves ``device``."""
        if device in self.actuators:
            return self.efficiencies["propulsion"] or 1.0
        if device == "hotel_constant":
            return self.efficiencies["hotel"] or 1.0
        return self.efficiencies["payload"] or 1.0

    def update_grades(self, grades, relations=None, bounds=None):
        """Grades/relations/bounds of devices an attached source created after attach()."""
        for device, states in (grades or {}).items():
            self.devices[device] = dict(states)
        for device, relation in (relations or {}).items():
            self.relations[device] = relation
        for device, states in (bounds or {}).items():
            self.bounds[device] = dict(states)

    def add_external(self, grades, capabilities=(), owner=None, relations=None, bounds=None):
        """Register an attached load source; returns new double-counting warnings.

        A source rejected by ``double_counting: error`` leaves no trace (state rolled back).
        """
        saved = (
            {k: dict(v) for k, v in self.devices.items()},
            {k: list(v) for k, v in self.capabilities.items()},
            dict(self.relations),
            {k: dict(v) for k, v in self.bounds.items()},
            dict(self.double_counting),
        )
        before = dict(self.double_counting)
        try:
            self.update_grades(grades, relations, bounds)
            owner = owner or ", ".join(sorted(grades or {})) or "external source"
            for capability in capabilities or ():
                self.capabilities.setdefault(capability, []).append(owner)
            self._update_double_counting()
        except ConfigurationError:
            (
                self.devices,
                self.capabilities,
                self.relations,
                self.bounds,
                self.double_counting,
            ) = saved
            raise
        return [
            f"possible double counting: '{cap}' provided by {', '.join(names)} (a double count if these entries describe the same physical device; two real loads if they are separate devices)"
            for cap, names in self.double_counting.items()
            if before.get(cap) != names
        ]

    def warnings(self):
        result = [
            f"possible double counting: '{cap}' provided by {', '.join(names)} (a double count if these entries describe the same physical device; two real loads if they are separate devices)"
            for cap, names in self.double_counting.items()
        ]
        result += [
            f"incomplete configuration: {u['component']} ({u['device']}) has no defensible "
            "power and is excluded from the electrical bus"
            for u in self.unconfigured
        ]
        result += list(self.stale_links)
        return result

    def grade(self, device, state):
        if device in self.actuators:
            return self.actuator_grades.get(device, self.propulsion_grade)
        if device == "hotel_constant":
            return self.hotel_grade
        return self.devices.get(device, {}).get(state, "D")

    def _voltage_dependence(self, device_state_energy_Wh, category_energy_Wh):
        """Energy whose value depends on the bus voltage and therefore on the OCV curve.

        Thruster power tables are voltage dependent and battery losses depend on the pack
        voltage; with a placeholder (grade D) OCV curve this energy inherits that weakness,
        which the per-parameter grade of the thruster record does not show.
        """
        if self.ocv_grade is None:
            propulsion = sum(
                sum(states.values())
                for device, states in device_state_energy_Wh.items()
                if device in self.actuators
            )
            return {
                "bus_voltage": "nominal (L0)",
                "voltage_dependent_energy_Wh": propulsion,
                "note": "thruster power evaluated at the pack's nominal voltage (no OCV curve)",
            }
        propulsion = sum(
            sum(states.values())
            for device, states in device_state_energy_Wh.items()
            if device in self.actuators
        )
        losses = category_energy_Wh.get("battery_losses", 0.0)
        return {
            "bus_voltage": "L1 OCV(SOC) - I R",
            "ocv_record": self.ocv_record,
            "ocv_grade": self.ocv_grade,
            "voltage_dependent_energy_Wh": propulsion + losses,
            "note": "propulsion and battery-loss energy depend on the bus voltage; "
            + (
                "the OCV curve is a placeholder (grade D)"
                if self.ocv_grade == "D"
                else f"OCV curve grade {self.ocv_grade}"
            ),
        }

    def summarize(self, device_state_energy_Wh, category_energy_Wh):
        by_grade = {g: 0.0 for g in GRADES}
        upper_bound_Wh = proxy_Wh = 0.0
        flagged = {}  # (kind, subject) -> [energy_Wh, states]
        for device, states in device_state_energy_Wh.items():
            relation = (
                self.actuator_relations.get(device, self.propulsion_relation)
                if device in self.actuators
                else self.relations.get(device)
            )
            for state, wh in states.items():
                grade = self.grade(device, state)
                by_grade[grade] += wh
                kinds = []
                if self.bounds.get(device, {}).get(state) == "upper_bound":
                    upper_bound_Wh += wh
                    kinds.append("upper_bound_only")
                if relation == "proxy":
                    proxy_Wh += wh
                    kinds.append("proxy")
                if grade == "D":
                    kinds.append("grade_D")
                for kind in kinds if wh > 0 else ():
                    entry = flagged.setdefault((kind, device), [0.0, set()])
                    entry[0] += wh
                    entry[1].add(state)
        by_grade[self.converter_grade] += category_energy_Wh.get("converters", 0.0)
        by_grade[self.battery_loss_grade] += category_energy_Wh.get("battery_losses", 0.0)
        result = coverage(by_grade)
        total = result["total_Wh"]
        result.update(
            upper_bound_energy_Wh=upper_bound_Wh,
            upper_bound_share_percent=100 * upper_bound_Wh / total if total else 0.0,
            proxy_energy_Wh=proxy_Wh,
            voltage_dependence=self._voltage_dependence(device_state_energy_Wh, category_energy_Wh),
            proxy_share_percent=100 * proxy_Wh / total if total else 0.0,
            stale_evidence_links=list(self.stale_links),
            upper_bound_meaning=(
                "energy computed from published maxima/upper bounds: the true value is "
                "expected to be lower, so these shares bias the prediction upward"
            ),
            propulsion_record=self.propulsion_record,
            battery_loss_record=self.battery_loss_record,
            vehicle_relation=self.vehicle_relation,
            unconfigured_components=list(self.unconfigured),
            legacy_components_without_evidence=list(self.legacy_unlinked),
            double_counting_warnings=self.warnings()[: len(self.double_counting)],
            excluded_from_coverage=(
                "vehicle hydrodynamics (simulator-owned, not validated) and unconfigured loads"
            ),
        )
        propulsion_Wh = sum(
            sum(states.values())
            for device, states in device_state_energy_Wh.items()
            if device in self.actuators
        )
        result["dynamics_evidence"] = {
            **self.dynamics,
            "dependent_energy_Wh": propulsion_Wh,
            "dependent_share_percent": 100 * propulsion_Wh / total if total else None,
            "meaning": "energy whose value follows the dynamics model (the thrust demand); "
            "the grade shares above describe the electrical models only",
        }
        result["scientific_warnings"] = self._scientific_warnings(
            flagged, category_energy_Wh, total
        ) + self._domain_warnings(device_state_energy_Wh, total)
        return result

    def rail_energy_Wh(self, device_state_energy_Wh):
        """Energy drawn through the payload and hotel rails."""
        rails = {"payload": 0.0, "hotel": 0.0}
        for device, states in device_state_energy_Wh.items():
            if device in self.actuators:
                continue
            rails["hotel" if device == "hotel_constant" else "payload"] += sum(states.values())
        return rails

    def _domain_warnings(self, device_state_energy_Wh, total):
        """Structured warnings for unmodelled conversion (review D-09) and actuator tables
        read outside their measured voltage range."""
        out = []
        if self.voltage_independent_actuators:
            energy = sum(
                sum(device_state_energy_Wh.get(a, {}).values())
                for a in self.voltage_independent_actuators
            )
            out.append(
                {
                    "kind": "voltage_independent_table",
                    "subject": ", ".join(self.voltage_independent_actuators),
                    "states": [],
                    "energy_Wh": energy,
                    "share_percent": 100 * energy / total if total else None,
                    "effect": "actuator power read at the nearest measured table voltage when "
                    "the bus is outside it (power assumed independent of bus voltage there)",
                }
            )
        for name, info in sorted(self.supply_mismatches.items()):
            energy = sum(device_state_energy_Wh.get(name, {}).values())
            out.append(
                {
                    "kind": "supply_domain_mismatch",
                    "subject": name,
                    "states": [],
                    "energy_Wh": energy,
                    "share_percent": 100 * energy / total if total else None,
                    "effect": (
                        f"{name} requires {info['supply_V'][0]:g}-{info['supply_V'][1]:g} V but the "
                        f"bus spans {info['bus_V'][0]:g}-{info['bus_V'][1]:g} V; no converter is "
                        "configured, so the reported energy excludes conversion loss"
                    ),
                }
            )
        for rail, energy in self.rail_energy_Wh(device_state_energy_Wh).items():
            if energy > 0 and not self.rail_verified.get(rail, True):
                out.append(
                    {
                        "kind": "conversion_unverified",
                        "subject": f"{rail} rail",
                        "states": [],
                        "energy_Wh": energy,
                        "share_percent": 100 * energy / total if total else None,
                        "effect": "converter efficiency 1.0 without evidence: conversion loss is "
                        "not modelled and the rail's energy is a lower bound",
                    }
                )
        return out

    EFFECTS = {
        "unknown": "excluded from the bus: the estimate is low by an unknown amount",
        "grade_D": "user value or placeholder without published evidence",
        "proxy": "evidence for a different but related device or condition",
        "upper_bound_only": "published maximum used as the value: biases the estimate upward",
        "supply_domain_mismatch": "device supply domain does not contain the bus voltage",
        "conversion_unverified": "conversion loss not modelled",
        "voltage_independent_table": "actuator table used outside its measured voltage range",
    }

    def _scientific_warnings(self, flagged, category_energy_Wh, total):
        """Structured, non-blocking warnings (brief section 51): what in the estimate is unknown,
        grade D, proxy or upper-bound only, with the energy it carries."""

        def item(kind, subject, energy, states=()):
            return {
                "kind": kind,
                "subject": subject,
                "states": sorted(states),
                "energy_Wh": energy,
                "share_percent": 100 * energy / total if total and energy is not None else None,
                "effect": self.EFFECTS[kind],
            }

        out = [item("unknown", u["component"], None) for u in self.unconfigured]
        out += [
            item(kind, device, wh, states)
            for (kind, device), (wh, states) in sorted(flagged.items())
        ]
        for category, grade in (
            ("battery_losses", self.battery_loss_grade),
            ("converters", self.converter_grade),
        ):
            wh = category_energy_Wh.get(category, 0.0)
            if grade == "D" and wh > 0:
                out.append(item("grade_D", category, wh))
            elif self.category_relations.get(category) == "proxy" and wh > 0:
                out.append(item("proxy", category, wh))
        if self.ocv_grade == "D":
            out.append(
                {
                    **item("grade_D", "battery OCV curve", None),
                    "effect": "bus voltage, and through it propulsion power and battery loss, "
                    "follow a placeholder OCV curve",
                }
            )
        return out
