"""Run the native verified-backend campaign in a fixed order and record every command.

Campaign steps (each a separate simulator process, run sequentially):

  check       backend smoke test on every build
  drag        decisive 17-case campaign, 60/100/200 Hz x 3 repeats, on every build
  autodrag    moving vehicle in still water (13 cases), on every build
  diag20      20 Hz diagnostic of the decisive cases (expected INCONCLUSIVE references)
  timestep    20/30/40/60/100/200 Hz timestep audit with still-water drag stability
  energy      current/mission/temperature/payload study (patched) and station/mission (stock)
  demo        same mission on stock and patched builds

Builds: ``original`` (installed package), ``rebuilt`` (unpatched control build) and
``patched``. Outputs go to <output-root>/<step>_<build>; campaign.json records the
commands, start/end times and exit codes. Failing steps are recorded, not hidden.
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STEPS = ["check", "drag", "autodrag", "diag20", "timestep", "energy", "demo"]


def commands(args):
    py = args.python
    binaries = {
        "original": args.original_binary,
        "rebuilt": args.rebuilt_binary,
        "patched": args.patched_binary,
    }
    sources = {
        "original": args.before_source,
        "rebuilt": args.before_source,
        "patched": args.after_source,
    }
    out = args.output_root
    plan = []
    for build, binary in binaries.items():
        plan.append(
            (
                "check",
                build,
                [
                    py,
                    "tools/check_holoocean_backend.py",
                    "--binary",
                    binary,
                    "--source-dir",
                    sources[build],
                    "--output",
                    out / f"check_{build}.json",
                ],
            )
        )
    for build, binary in binaries.items():
        plan.append(
            (
                "drag",
                build,
                [
                    py,
                    "examples/verify_holoocean_drag_units.py",
                    "--source-dir",
                    sources[build],
                    "--binary",
                    binary,
                    "--ticks-per-sec",
                    "60",
                    "100",
                    "200",
                    "--repeats",
                    "3",
                    "--steps-per-case",
                    "8",
                    "--output-dir",
                    out / f"drag_{build}",
                ],
            )
        )
    for build, binary in binaries.items():
        plan.append(
            (
                "autodrag",
                build,
                [
                    py,
                    "examples/verify_holoocean_drag_units.py",
                    "--source-dir",
                    sources[build],
                    "--binary",
                    binary,
                    "--case-set",
                    "autodrag",
                    "--ticks-per-sec",
                    "60",
                    "100",
                    "200",
                    "--repeats",
                    "3",
                    "--steps-per-case",
                    "8",
                    "--output-dir",
                    out / f"autodrag_{build}",
                ],
            )
        )
    for build in ("original", "patched"):
        plan.append(
            (
                "diag20",
                build,
                [
                    py,
                    "examples/verify_holoocean_drag_units.py",
                    "--source-dir",
                    sources[build],
                    "--binary",
                    binaries[build],
                    "--ticks-per-sec",
                    "20",
                    "--repeats",
                    "1",
                    "--steps-per-case",
                    "8",
                    "--output-dir",
                    out / f"diag20_{build}",
                ],
            )
        )
    for build, binary in binaries.items():
        plan.append(
            (
                "timestep",
                build,
                [
                    py,
                    "tools/audit_holoocean_timestep.py",
                    "--source-dir",
                    sources[build],
                    "--binary",
                    binary,
                    "--drag-stability",
                    "--output-dir",
                    out / f"timestep_{build}",
                ],
            )
        )
    plan.append(
        (
            "energy",
            "patched",
            [
                py,
                "examples/native_current_energy_study.py",
                "--holoocean-binary",
                binaries["patched"],
                "--output-dir",
                out / "energy_patched",
                "--label",
                "patched",
            ],
        )
    )
    plan.append(
        (
            "energy",
            "original",
            [
                py,
                "examples/native_current_energy_study.py",
                "--holoocean-binary",
                binaries["original"],
                "--experiments",
                "station",
                "mission",
                "--output-dir",
                out / "energy_original",
                "--label",
                "original",
            ],
        )
    )
    plan.append(
        (
            "demo",
            "original+patched",
            [
                py,
                "examples/holoocean_before_after_demo.py",
                "--before-binary",
                binaries["original"],
                "--after-binary",
                binaries["patched"],
                "--current",
                "0.4",
                "--output-dir",
                out / "demo",
            ],
        )
    )
    return [(s, b, [str(c) for c in cmd]) for s, b, cmd in plan if s in args.steps]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--original-binary", type=Path, required=True)
    parser.add_argument("--rebuilt-binary", type=Path, required=True)
    parser.add_argument("--patched-binary", type=Path, required=True)
    parser.add_argument("--before-source", type=Path, required=True)
    parser.add_argument("--after-source", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=ROOT / "logs/verified_backend")
    parser.add_argument("--steps", nargs="+", choices=STEPS, default=STEPS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    record_path = args.output_root / "campaign.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.exists() else []
    for step, build, command in commands(args):
        print(f"== {step} [{build}]: {' '.join(command)}", flush=True)
        if args.dry_run:
            continue
        log = args.output_root / f"{step}_{build}.log"
        start = time.time()
        with log.open("w", encoding="utf-8") as handle:
            code = subprocess.run(
                command, cwd=ROOT, stdout=handle, stderr=subprocess.STDOUT
            ).returncode
        record.append(
            {
                "step": step,
                "build": build,
                "command": command,
                "started_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
                "duration_s": time.time() - start,
                "exit_code": code,
                "log": log.name,
            }
        )
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"   exit {code} in {time.time() - start:.0f} s", flush=True)


if __name__ == "__main__":
    main()
