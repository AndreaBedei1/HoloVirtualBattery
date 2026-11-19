"""JSON API behind the HoloEnergy web application.

Every value the browser shows is computed here by the same Python package a script would use:
the hardware library (:mod:`holoenergy.hardware`), configuration loading and the scientific
pre-flight check (:mod:`holoenergy.preflight`), energy-only missions
(:func:`holoenergy.mission.run_scenario`) and evidence-aware decisions
(:mod:`holoenergy.decision`). The browser holds documents (robot and mission mappings, the same
YAML schema as the files) and renders results; it holds no energy model.
"""

from __future__ import annotations

import copy
import json
import re
import time
from pathlib import Path

import yaml

from .._validation import ConfigurationError

MAX_STEPS = 200_000
SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


class ApiError(Exception):
    def __init__(self, status, payload):
        super().__init__(payload.get("summary", "error"))
        self.status = status
        self.payload = payload


def _plain(value):
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float) and value != value:  # NaN is not JSON
        return None
    return value


def _require_mapping(body, key):
    value = body.get(key)
    if not isinstance(value, dict):
        raise ApiError(
            400,
            {
                "summary": f"'{key}' must be an object",
                "fix": None,
                "technical": f"missing or invalid {key}",
            },
        )
    return value


def catalog():
    from ..catalog import list_profiles
    from ..hardware import hardware_library, library_counts

    cards = hardware_library()
    return {"cards": cards, "counts": library_counts(cards), "profiles": list_profiles()}


def catalog_item(kind, key):
    from ..hardware import hardware_detail

    try:
        return hardware_detail(kind, key)
    except KeyError as exc:
        raise ApiError(404, {"summary": str(exc), "fix": None, "technical": str(exc)}) from exc


TEMPLATES = {
    "bluerov2-heavy": {
        "label": "BlueROV2 Heavy (HoloOcean, 8 x T200)",
        "robot": {
            "profile": "package:vehicles/bluerov2_heavy_holoocean.yaml",
            "battery": {"profile": "package:batteries/bluerobotics_4s18ah_v2.yaml"},
        },
    },
    "four-thruster-rov": {
        "label": "Custom 4-thruster ROV (T200, user battery)",
        "robot": {
            "allow_placeholders": True,
            "vehicle": {"name": "custom 4-thruster ROV"},
            "simulation": {"dt_s": 0.1},
            "environment": {"water_temperature_C": 15.0},
            "battery": {"profile": "package:batteries/bluerobotics_4s18ah_30q_proxy.yaml"},
            "thermal": {"model": "isothermal", "initial_temperature_C": 15.0},
            "actuators": [
                {
                    "id": "H1",
                    "position_m": [0.2, -0.12, 0.0],
                    "direction": [1, 0, 0],
                    "profile": "package:actuators/bluerobotics_t200.yaml",
                },
                {
                    "id": "H2",
                    "position_m": [0.2, 0.12, 0.0],
                    "direction": [1, 0, 0],
                    "profile": "package:actuators/bluerobotics_t200.yaml",
                },
                {
                    "id": "V1",
                    "position_m": [0.0, -0.15, 0.05],
                    "direction": [0, 0, 1],
                    "profile": "package:actuators/bluerobotics_t200.yaml",
                },
                {
                    "id": "V2",
                    "position_m": [0.0, 0.15, 0.05],
                    "direction": [0, 0, 1],
                    "profile": "package:actuators/bluerobotics_t200.yaml",
                },
            ],
            "actuation": {
                "action_mode": "thrusters",
                "allocation": {"method": "redistributed"},
                "backend": {"mapping": "direct", "backend_index": [0, 1, 2, 3]},
            },
            "rails": [{"name": "pack", "kind": "direct"}, {"name": "5V", "output_V": 5.0}],
            "components": [
                {
                    "profile": "package:components/raspberry_pi_4b.yaml",
                    "name": "companion_computer",
                    "rail": "5V",
                },
                {
                    "profile": "package:components/bluerobotics_lowlight_usb_camera.yaml",
                    "name": "camera",
                    "rail": "5V",
                },
                {
                    "profile": "package:components/waterlinked_dvl_a50.yaml",
                    "name": "dvl",
                    "rail": "pack",
                },
            ],
            "hotel_load": {"constant_W": 0.0},
            "evidence": {
                "propulsion": {
                    "record": "bluerobotics_t200.static_force_power_curve",
                    "relation": "representative",
                },
                "battery_losses": {
                    "record": "bluerobotics_4s_18ah.dc_resistance_cell_derived",
                    "relation": "proxy",
                },
            },
        },
    },
}

DEFAULT_MISSION = {
    "schema_version": 1,
    "name": "inspection",
    "phases": [
        {"name": "startup", "duration_s": 30},
        {"name": "transit", "duration_s": 120, "propulsion": {"thrust_N": [10, 10, 0, 0]}},
        {
            "name": "inspection",
            "duration_s": 300,
            "propulsion": {"thrust_N": [2, 2, 3, 3]},
            "action": "hold station and image the target",
        },
        {"name": "return", "duration_s": 120, "propulsion": {"thrust_N": [10, 10, 0, 0]}},
    ],
}


def templates():
    return {
        "robots": {k: {"label": v["label"], "robot": v["robot"]} for k, v in TEMPLATES.items()},
        "mission": DEFAULT_MISSION,
    }


def _resolve(robot):
    from ..config import load_config

    return load_config(data=copy.deepcopy(robot))


def robot_summary(body):
    """Actuators, components, rails and battery of a robot document, as the model resolves them."""
    robot = _require_mapping(body, "robot")
    from ..mission import actuator_count

    try:
        config = _resolve(robot)
    except (ConfigurationError, ValueError) as exc:
        from ..preflight import humanize

        raise ApiError(422, humanize(exc)) from exc
    battery = config.get("battery") or {}
    geometry = config.get("actuators") or (config.get("actuation") or {}).get("geometry") or []
    return {
        "name": (config.get("vehicle") or {}).get("name"),
        "dt_s": (config.get("simulation") or {}).get("dt_s"),
        "action_mode": (config.get("actuation") or {}).get("action_mode", "thrusters"),
        "actuator_count": actuator_count(config),
        "actuators": [
            {"id": a.get("id"), "position_m": a.get("position_m"), "direction": a.get("direction")}
            for a in geometry
        ],
        "components": [
            {
                "name": c.get("name"),
                "category": c.get("category", "sensors"),
                "states": sorted((c.get("states") or {}).keys()) + ["OFF"],
                "rail": c.get("rail"),
                "status": c.get("status", "configured"),
                "simulation_sensor": c.get("simulation_sensor"),
                "device": c.get("device"),
            }
            for c in config.get("components") or []
        ],
        "rails": config.get("rails") or [],
        "battery": {
            k: battery.get(k)
            for k in (
                "model",
                "nominal_voltage_V",
                "capacity_Ah",
                "capacity_Wh",
                "cutoff_voltage_V",
                "max_current_A",
                "chemistry",
            )
        },
    }


def preflight_check(body):
    from ..preflight import preflight

    robot = _require_mapping(body, "robot")
    mission = body.get("mission")
    return preflight(robot, mission=mission, mode=body.get("mode", "energy-only"))


def to_yaml(body):
    kind = body.get("kind")
    if kind not in ("robot", "mission"):
        raise ApiError(
            400, {"summary": "kind must be robot or mission", "fix": None, "technical": str(kind)}
        )
    document = _require_mapping(body, "document")
    if kind == "mission":
        from ..mission import Mission

        try:
            document = Mission.from_mapping(document).to_mapping()
        except ConfigurationError as exc:
            from ..preflight import humanize

            raise ApiError(422, humanize(exc)) from exc
    return {"yaml": yaml.safe_dump(_plain(document), sort_keys=False)}


def import_document(body):
    text = body.get("text")
    if not isinstance(text, str) or len(text) > 2_000_000:
        raise ApiError(
            400,
            {
                "summary": "text must be a YAML or JSON document under 2 MB",
                "fix": None,
                "technical": "invalid text",
            },
        )
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ApiError(
            422,
            {
                "summary": "The file is not valid YAML or JSON.",
                "fix": "Check indentation and quoting.",
                "technical": str(exc),
            },
        ) from exc
    if not isinstance(data, dict):
        raise ApiError(
            422,
            {
                "summary": "The file must contain a mapping at the top level.",
                "fix": None,
                "technical": type(data).__name__,
            },
        )
    kind = "mission" if "phases" in data else "robot"
    if kind == "mission":
        from ..mission import Mission

        try:
            data = Mission.from_mapping(data).to_mapping()
        except ConfigurationError as exc:
            from ..preflight import humanize

            raise ApiError(422, humanize(exc)) from exc
    return {"kind": kind, "document": data}


def _series(rows, limit=600):
    step = max(1, len(rows) // limit)
    keys = (
        "time_s",
        "soc",
        "voltage_V",
        "current_A",
        "power_total_W",
        "power_propulsion_W",
        "power_payload_W",
        "power_hotel_W",
        "power_conversion_loss_W",
        "derating_factor",
    )
    picked = rows[::step]
    if rows and picked[-1] is not rows[-1]:
        picked.append(rows[-1])
    return {k: [r.get(k) for r in picked] for k in keys}


def run_energy_only(body, runs_dir):
    """Energy-only run; the report is saved next to other runs for Compare."""
    from ..config import load_config
    from ..mission import Mission, run_scenario
    from ..preflight import humanize, preflight

    robot = _require_mapping(body, "robot")
    mission_doc = _require_mapping(body, "mission")
    label = SAFE_NAME.sub("-", str(body.get("label") or mission_doc.get("name") or "run"))[:60]
    try:
        mission = Mission.from_mapping(mission_doc)
        config = load_config(data=copy.deepcopy(robot))
        steps = mission.duration_s / config["simulation"]["dt_s"]
        if steps > MAX_STEPS:
            raise ConfigurationError(
                f"the mission has {steps:.0f} steps; the web runner accepts at most {MAX_STEPS} "
                "(use run_scenario from Python for longer missions)"
            )
        check = preflight(robot, mission=mission_doc, mode="energy-only")
        if not check["ok"]:
            raise ApiError(422, check["errors"][0])
        run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + label
        out = Path(runs_dir) / run_id
        report = run_scenario(config, mission, out)
    except ConfigurationError as exc:
        raise ApiError(422, humanize(exc)) from exc
    rows = [
        json.loads(line)
        for line in (out / "energy.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    rows = [r for r in rows if "time_s" in r]
    data = report.to_dict()
    data["label"] = label
    data["mission"] = mission.to_mapping()
    data["robot"] = robot
    data["mode"] = "energy-only"
    (Path(runs_dir) / f"{run_id}.json").write_text(
        json.dumps(_plain(data), default=str), encoding="utf-8"
    )
    return {
        "run_id": run_id,
        "report": _plain(data),
        "series": _series(rows),
        "preflight": check,
        "environment": mission.environment_effects("energy-only"),
    }


def list_runs(runs_dir):
    from .server import compare_reports

    return compare_reports(runs_dir)


def load_run(runs_dir, name):
    path = Path(runs_dir) / SAFE_NAME.sub("-", name)
    if path.suffix != ".json" or not path.is_file():
        raise ApiError(404, {"summary": "run not found", "fix": None, "technical": name})
    return json.loads(path.read_text(encoding="utf-8"))


def compare(body, runs_dir):
    """Nominal, evidence-aware and strict comparison of two saved runs (A vs B)."""
    from ..decision import compare_energy

    a = load_run(runs_dir, str(body.get("a", "")))
    b = load_run(runs_dir, str(body.get("b", "")))
    rows = []
    for label, min_grade in (("evidence-aware", None), ("strict (grade A or B only)", "B")):
        result = compare_energy(a, b, min_grade=min_grade)
        rows.append({"policy": label, **_plain(result.to_dict())})
    na, nb = a["terminal_energy_Wh"], b["terminal_energy_Wh"]
    return {
        "a": {
            "label": a.get("label"),
            "terminal_energy_Wh": na,
            "soc_final": a.get("soc_final"),
            "evidence": (a.get("evidence") or {}).get("share_percent"),
        },
        "b": {
            "label": b.get("label"),
            "terminal_energy_Wh": nb,
            "soc_final": b.get("soc_final"),
            "evidence": (b.get("evidence") or {}).get("share_percent"),
        },
        "nominal": {
            "difference_Wh": na - nb,
            "difference_percent": 100 * (na - nb) / nb if nb else None,
            "lower": "a" if na < nb else "b" if nb < na else "tie",
        },
        "policies": rows,
        "same_mission": a.get("mission") == b.get("mission"),
    }


def custom_component(body):
    """User hardware with provenance: the grade follows the source type (Python rule)."""
    from ..preflight import humanize
    from ..robot import user_component

    states = body.get("states")
    if not isinstance(states, dict) or not states:
        raise ApiError(
            400,
            {
                "summary": "Give at least one state with its power in W.",
                "fix": None,
                "technical": "states missing",
            },
        )
    try:
        parsed = {
            str(k).upper(): (None if v in (None, "") else float(v)) for k, v in states.items()
        }
        return user_component(
            str(body.get("name", "")).strip(),
            body.get("category", "sensors"),
            parsed,
            source_type=body.get("source_type", "unknown"),
            citation=body.get("citation"),
            locator=body.get("locator"),
            rail=body.get("rail") or None,
            supply_V=body.get("supply_V") or None,
        )
    except (ConfigurationError, ValueError) as exc:
        raise ApiError(422, humanize(exc)) from exc
