"""``holoenergy`` command line (secondary to the Python API).

holoenergy profiles                         list named vehicle/battery/component/modem profiles
holoenergy evidence <id|component|profile>  provenance rows for a record, component or vehicle
holoenergy validate <config.yaml|profile>   load a configuration and report its readiness
holoenergy run <mission.yaml>               replay a recorded actuator trace -> EnergyReport
holoenergy compare <a.json> <b.json> ...    structured comparison of EnergyReports
holoenergy audit-sensors <SensorType> ...   electrical meaning of HoloOcean sensors
holoenergy check-backend [--binary EXE]     run tools/check_holoocean_backend.py (launches HoloOcean)
"""

from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path


def _print(value):
    print(json.dumps(value, indent=2, default=str))


def _config_for(target):
    from .catalog import VEHICLES, vehicle_config
    from .config import load_config

    if target in VEHICLES:
        return load_config(data=vehicle_config(target))
    return load_config(target)


def cmd_profiles(args):
    from .catalog import list_profiles

    _print(list_profiles())


def cmd_evidence(args):
    from .catalog import VEHICLES
    from .evidence import default_registry

    registry = default_registry()
    if args.target in registry.records:
        _print(registry.table([args.target]))
        return
    if args.target in VEHICLES:
        from .env_wrapper import EnergyAwareEnv

        class _Null:
            def step(self, action):
                return {}

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            env = EnergyAwareEnv(
                _Null(),
                vehicle_profile=args.target,
                overrides={
                    "logging": {"enabled": False},
                    "power_manager": {"apply_derating_to_actions": False},
                },
            )
        ids = sorted(
            {r for states in env.evidence_map.records.values() for r in states.values()}
            | {
                x
                for x in (env.evidence_map.propulsion_record, env.evidence_map.battery_loss_record)
                if x
            }
        )
        _print({"profile": args.target, "warnings": env.warnings, "records": registry.table(ids)})
        return
    rows = [r for r in registry.table() if r["component"] == args.target]
    if not rows:
        print(
            f"No evidence record, component or vehicle profile named {args.target!r}",
            file=sys.stderr,
        )
        return 2
    _print(rows)


def cmd_validate(args):
    from .env_wrapper import EnergyAwareEnv

    class _Null:
        def step(self, action):
            return {}

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        config = _config_for(args.target)
        config.setdefault("logging", {})["enabled"] = False
        config.setdefault("power_manager", {})["apply_derating_to_actions"] = False
        env = EnergyAwareEnv(_Null(), config=config)
    _print(
        {
            "target": args.target,
            "fidelity_level": env.config["fidelity_level"],
            "actuators": env.propulsion.count,
            "actuation": env.actuation.describe(),
            "components": sorted(env.payload.components),
            "unconfigured_components": env.evidence_map.unconfigured,
            "double_counting": env.evidence_map.double_counting,
            "warnings": env.warnings + [str(w.message) for w in caught],
            "ready": not env.evidence_map.unconfigured,
        }
    )


def cmd_run(args):
    """Mission file: {vehicle_profile|config, trace: CSV(time_s, action JSON[, phase]), output}."""
    import csv

    import yaml

    from .env_wrapper import EnergyAwareEnv

    mission = yaml.safe_load(Path(args.mission).read_text(encoding="utf-8"))
    base = Path(args.mission).resolve().parent

    class _Replay:
        def step(self, action):
            return {}

    overrides = {
        "logging": {"enabled": False},
        "power_manager": {"apply_derating_to_actions": False},
    }
    overrides.update(mission.get("overrides", {}))
    if "dt_s" in mission:
        overrides.setdefault("simulation", {})["dt_s"] = mission["dt_s"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        env = EnergyAwareEnv(
            _Replay(),
            vehicle_profile=mission.get("vehicle_profile"),
            components=mission.get("components"),
            overrides=overrides,
        )
    with (base / mission["trace"]).open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("phase"):
                env.energy.mark_phase(row["phase"])
            env.step(json.loads(row["action"]))
    report = env.energy.report()
    out = Path(args.output or mission.get("output", "energy_report.json"))
    report.write_json(out)
    print(report.text())
    print(f"report: {out}")


def cmd_compare(args):
    from .report import compare_runs

    _print(compare_runs(*args.reports))


def cmd_audit(args):
    from .sensor_policy import classify

    _print({s: classify(s) for s in args.sensors})


def cmd_check_backend(args):
    tool = Path(__file__).resolve().parents[1] / "tools" / "check_holoocean_backend.py"
    if not tool.exists():
        print(
            "tools/check_holoocean_backend.py is only available in a source checkout",
            file=sys.stderr,
        )
        return 2
    import subprocess

    command = [sys.executable, str(tool)] + (["--binary", args.binary] if args.binary else [])
    return subprocess.call(command)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="holoenergy", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("profiles").set_defaults(func=cmd_profiles)
    p = sub.add_parser("evidence")
    p.add_argument("target")
    p.set_defaults(func=cmd_evidence)
    p = sub.add_parser("validate")
    p.add_argument("target")
    p.set_defaults(func=cmd_validate)
    p = sub.add_parser("run")
    p.add_argument("mission")
    p.add_argument("--output")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("compare")
    p.add_argument("reports", nargs="+")
    p.set_defaults(func=cmd_compare)
    p = sub.add_parser("audit-sensors")
    p.add_argument("sensors", nargs="+")
    p.set_defaults(func=cmd_audit)
    p = sub.add_parser("check-backend")
    p.add_argument("--binary")
    p.set_defaults(func=cmd_check_backend)
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
