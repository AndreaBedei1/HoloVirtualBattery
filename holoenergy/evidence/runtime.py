"""Attribute every predicted Wh to the evidence grade of the parameters that produced it."""

from __future__ import annotations

import math

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
    import importlib.resources
    import json

    path = (record.dataset or {}).get("path")
    if not path or not path.endswith(".json"):
        return None
    try:
        data = json.loads(importlib.resources.files("holoenergy").joinpath(path).read_text())
    except (FileNotFoundError, OSError, ValueError):
        return None
    return data.get("voltage_tables")


def _graded(registry, entry):
    if not isinstance(entry, dict) or entry.get("record") is None:
        return "D", None
    record = registry.get(entry["record"])
    if not record.configured:
        return "D", record.id
    return cap_grade(record.grade, entry.get("relation", "exact")), record.id


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
        self.stale_links = self._check_links(config)
        self.vehicle_relation = evidence.get("vehicle_relation")
        self.double_counting_policy = evidence.get("double_counting", "warn")
        if self.double_counting_policy not in ("warn", "error"):
            from .._validation import ConfigurationError

            raise ConfigurationError("evidence.double_counting must be warn or error")
        self.actuators = list(propulsion.ids)
        self.devices, self.bounds, self.records = {}, {}, {}
        self.unconfigured, self.legacy_unlinked = [], []
        capabilities = {}
        for name, item in payload.components.items():
            grades = getattr(item, "state_grades", None)
            if grades is None:
                self.legacy_unlinked.append(name)
                grades = {}
            self.devices[name] = dict(grades)
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
            stale.append(f"stale evidence link: {kind} -> {record_id} ({why}); graded D")

        if self.battery_loss_record:
            record = self.registry.get(self.battery_loss_record)
            actual = (config.get("battery") or {}).get("internal_resistance_ohm")
            if not _matches(record, actual):
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
        if self.propulsion_record:
            record = self.registry.get(self.propulsion_record)
            tables = _dataset_tables(record)
            propulsion = config.get("propulsion") or {}
            models = propulsion.get("thrusters") or [propulsion.get("thruster")]
            if tables is not None and any(
                not isinstance(m, dict) or m.get("voltage_tables") != tables for m in models
            ):
                drop("propulsion", record.id, "actuator tables differ from the record's dataset")
        return stale

    def add_external(self, grades, capabilities=(), owner=None):
        """Register an attached load source; returns new double-counting warnings."""
        for device, states in (grades or {}).items():
            self.devices[device] = dict(states)
        before = dict(self.double_counting)
        owner = owner or ", ".join(sorted(grades or {})) or "external source"
        for capability in capabilities or ():
            self.capabilities.setdefault(capability, []).append(owner)
        self._update_double_counting()
        return [
            f"possible double counting: '{cap}' provided by {', '.join(names)}"
            for cap, names in self.double_counting.items()
            if before.get(cap) != names
        ]

    def warnings(self):
        result = [
            f"possible double counting: '{cap}' provided by {', '.join(names)}"
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
            return self.propulsion_grade
        if device == "hotel_constant":
            return self.hotel_grade
        return self.devices.get(device, {}).get(state, "D")

    def summarize(self, device_state_energy_Wh, category_energy_Wh):
        by_grade = {g: 0.0 for g in GRADES}
        upper_bound_Wh = 0.0
        for device, states in device_state_energy_Wh.items():
            for state, wh in states.items():
                by_grade[self.grade(device, state)] += wh
                if self.bounds.get(device, {}).get(state) == "upper_bound":
                    upper_bound_Wh += wh
        by_grade[self.converter_grade] += category_energy_Wh.get("converters", 0.0)
        by_grade[self.battery_loss_grade] += category_energy_Wh.get("battery_losses", 0.0)
        result = coverage(by_grade)
        total = result["total_Wh"]
        result.update(
            upper_bound_energy_Wh=upper_bound_Wh,
            upper_bound_share_percent=100 * upper_bound_Wh / total if total else 0.0,
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
        return result
