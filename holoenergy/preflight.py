"""Scientific pre-flight check of a robot configuration (and optionally a mission).

``preflight(config, mission=None, mode="energy-only")`` builds the same energy model a run would
build (energy-only backend, no simulator) and returns:

* ``errors`` - configurations HoloEnergy cannot run, in plain language with a suggested fix and
  the technical message kept separately;
* ``issues`` - things that do not block a run but change how its result may be read (unknown or
  grade-D values, proxies, upper bounds, open uncertainty sides, supply-voltage mismatches,
  unverified converters, double counting, stale links, dynamics evidence, backend status).

Nothing is blocked beyond ``errors``: exploratory engineering runs stay possible.
"""

from __future__ import annotations

import copy
import re

from ._validation import ConfigurationError

BACKEND_STATUS = {
    "energy-only": {
        "status": "no dynamics",
        "message": "Propulsion follows the prescribed thrust of each phase; no vehicle dynamics.",
    },
    "holoocean": {
        "status": "backend check required",
        "message": "Run tools/check_holoocean_backend.py first: HoloOcean 2.3.0 as released "
        "applies the drag term at 0.01x; the patched build passes (EXP1).",
    },
    "holoocean+desert": {
        "status": "backend check required",
        "message": "As HoloOcean, plus a DESERT session observed by the modem adapter "
        "(manage_engine=False on a non-default port).",
    },
}

_HINTS = (
    (
        re.compile(r"incompatible with the actuator voltage domain"),
        "The battery's nominal voltage lies outside the voltages at which the actuator tables "
        "were measured.",
        "Choose an actuator model measured at this pack voltage, or another battery.",
    ),
    (
        re.compile(r"is on rail '([^']+)', which is not configured"),
        "A component is assigned to a supply rail that does not exist.",
        "Add the rail in the Rails section or move the component to an existing rail.",
    ),
    (
        re.compile(r"null power requires status unconfigured|has no value"),
        "A component state has no defensible power value.",
        "Supply a measured value with its source, or mark the component unconfigured (it is "
        "then excluded from the bus and reported as incomplete).",
    ),
    (
        re.compile(r"must be thrusters or wrench"),
        "The actuation mode is not recognised.",
        "Use 'wrench' (6-axis command, allocated to the actuators) or 'thrusters'.",
    ),
    (
        re.compile(r"actuator (\S+) at ([\d.]+) V"),
        "An actuator cannot be evaluated at full thrust over the battery's voltage range.",
        "Use an actuator table that covers the whole pack voltage range or set its "
        "voltage_policy to table_voltage (reported as a scientific warning).",
    ),
)


def humanize(exc):
    """Plain-language error with a suggested fix; the technical message stays available."""
    text = str(exc)
    for pattern, summary, fix in _HINTS:
        if pattern.search(text):
            return {"summary": summary, "fix": fix, "technical": text}
    return {"summary": text[:1].upper() + text[1:], "fix": None, "technical": text}


def _issue(kind, subject, message, severity="interpretation", **extra):
    return {"kind": kind, "subject": subject, "message": message, "severity": severity, **extra}


def _evidence_issues(emap):
    issues = []
    for row in emap.unconfigured:
        issues.append(
            _issue(
                "unknown",
                row["component"],
                f"{row['component']} has no defensible power value and is excluded "
                "from the bus: the estimate is low by an unknown amount.",
            )
        )
    for device, states in sorted(emap.devices.items()):
        relation = emap.relations.get(device, "exact")
        for state, grade in sorted(states.items()):
            if state == "OFF":
                continue
            bound = emap.bounds.get(device, {}).get(state)
            record = emap.records.get(device, {}).get(state)
            if grade == "D":
                issues.append(
                    _issue(
                        "grade_D",
                        f"{device}.{state}",
                        f"{device} {state}: user value or placeholder without "
                        "published evidence (grade D).",
                    )
                )
            if bound == "upper_bound":
                issues.append(
                    _issue(
                        "upper_bound",
                        f"{device}.{state}",
                        f"{device} {state}: the published maximum is used; the "
                        "estimate is biased upward.",
                    )
                )
            if record is None and grade != "D":
                issues.append(
                    _issue(
                        "open_interval",
                        f"{device}.{state}",
                        f"{device} {state}: no evidence range; its uncertainty "
                        "is open on both sides.",
                    )
                )
        if relation == "proxy":
            issues.append(
                _issue(
                    "proxy",
                    device,
                    f"{device}: evidence from a different but related device or condition (proxy).",
                )
            )
    for name, info in sorted(emap.supply_mismatches.items()):
        issues.append(
            _issue("supply_voltage", name, emap.supply_message(name, info), severity="attention")
        )
    for rail, ok in sorted(emap.rails_in_use().items()):
        if not ok and emap.rail_energy_candidates(rail):
            issues.append(_issue("converter", f"{rail} rail", emap._rail_text(rail)))
    for capability, names in sorted(emap.double_counting.items()):
        issues.append(
            _issue(
                "double_counting",
                capability,
                f"'{capability}' is provided by {', '.join(names)}: a double count "
                "if they are the same physical device.",
                severity="attention",
            )
        )
    for text in emap.stale_links:
        issues.append(
            _issue(
                "stale_link",
                text.split("->")[0].replace("stale evidence link:", "").strip(),
                text[:1].upper() + text[1:] + ".",
            )
        )
    for aid in emap.voltage_independent_actuators:
        issues.append(
            _issue(
                "actuator_range",
                aid,
                f"{aid}: outside its measured voltages the actuator table is read at "
                "the nearest measured voltage (power assumed voltage-independent).",
            )
        )
    if emap.ocv_grade == "D":
        issues.append(
            _issue(
                "battery",
                "battery OCV",
                "Battery OCV curve is a placeholder (grade D): terminal voltage and "
                "voltage-dependent actuator power inherit it.",
            )
        )
    elif emap.ocv_grade == "C":
        issues.append(
            _issue(
                "battery",
                "battery OCV",
                "Battery OCV curve is a proxy (grade C), e.g. a cell-level table "
                "scaled to the pack.",
            )
        )
    if emap.battery_loss_grade in ("C", "D"):
        issues.append(
            _issue(
                "battery",
                "battery resistance",
                f"Battery resistance is grade {emap.battery_loss_grade}: losses "
                "and voltage sag are approximate.",
            )
        )
    return issues


def _dynamics_issue(emap, mode):
    dyn = emap.dynamics or {}
    if mode == "energy-only":
        return _issue(
            "dynamics",
            "dynamics",
            "Energy-only mode: thrust is prescribed per phase, not produced by vehicle dynamics.",
            severity="info",
        )
    status = dyn.get("status") or dyn.get("source") or "unknown"
    return _issue(
        "dynamics",
        "dynamics",
        f"Dynamics evidence: {status}. Propulsion energy follows the simulator's drag "
        "and is not physically validated.",
        status=status,
    )


def preflight(config, *, mission=None, mode="energy-only"):
    """Check ``config`` (mapping, YAML path or RobotEnergyProfile) before a run."""
    from . import EnergyAwareEnv
    from .config import load_config
    from .mission import MODE_SCOPE, MODES, Mission

    if mode not in MODES:
        raise ConfigurationError(f"mode must be one of {MODES}")
    result = {
        "mode": mode,
        "ok": True,
        "errors": [],
        "issues": [],
        "backend": BACKEND_STATUS[mode],
        "scope": MODE_SCOPE[mode],
        "environment": [],
    }
    try:
        if hasattr(config, "to_config"):
            config = config.to_config()
        resolved = (
            load_config(path=config)
            if isinstance(config, str)
            else load_config(data=copy.deepcopy(config))
        )
        from .analysis.replay import ReplayBackend

        backend = ReplayBackend(resolved)
        with EnergyAwareEnv(
            backend, config=resolved, control_contract=backend.energy_action_contract
        ) as env:
            emap = env.evidence_map
            result["issues"] = _evidence_issues(emap)
            result["issues"].append(_dynamics_issue(emap, mode))
            low, high = emap.bus_voltage_range
            result["bus_voltage_V"] = [low, high]
            if mission is not None:
                if isinstance(mission, dict):
                    mission = Mission.from_mapping(mission)
                mission.commands(resolved)  # schedule errors surface here
                result["environment"] = mission.environment_effects(mode)
                result["mission_duration_s"] = mission.duration_s
    except (ConfigurationError, ValueError, TypeError, KeyError) as exc:
        result["ok"] = False
        result["errors"].append(humanize(exc))
    order = {"attention": 0, "interpretation": 1, "info": 2}
    result["issues"].sort(key=lambda i: (order.get(i["severity"], 3), i["kind"], i["subject"]))
    result["counts"] = {
        "errors": len(result["errors"]),
        "attention": sum(i["severity"] == "attention" for i in result["issues"]),
        "interpretation": sum(i["severity"] == "interpretation" for i in result["issues"]),
    }
    return result
