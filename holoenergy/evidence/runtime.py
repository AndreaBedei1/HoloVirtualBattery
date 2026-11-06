"""Attribute every predicted Wh to the evidence grade of the parameters that produced it."""

from __future__ import annotations

from . import GRADES, cap_grade, coverage, default_registry


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
        self.vehicle_relation = evidence.get("vehicle_relation")
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
        self.double_counting = {
            cap: names for cap, names in sorted(capabilities.items()) if len(names) > 1
        }
        self.external = {}

    def add_external(self, grades):
        for device, states in (grades or {}).items():
            self.devices[device] = dict(states)

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
