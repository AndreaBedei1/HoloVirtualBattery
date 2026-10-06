"""Offline comparison, sensitivity, measured-map import and held-out evaluation CLI."""

import argparse
import json
from pathlib import Path

from ..config import load_config
from ..provenance import write_json
from .calibration import apply_battery_maps, battery_maps
from .datasets import verify_manifest
from .evaluation import evaluate_files
from .replay import compare_models, read_mission
from .sensitivity import study


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    for command in ("compare", "sensitivity"):
        p = subs.add_parser(command)
        p.add_argument("--config", type=Path, required=True)
        p.add_argument("--mission", type=Path, required=True)
        p.add_argument("--output-dir", type=Path, required=True)
        p.add_argument("--reserve-soc", type=float)
        if command == "sensitivity":
            p.add_argument("--specification", type=Path, required=True)
    p = subs.add_parser("import-battery")
    p.add_argument("csv", type=Path)
    p.add_argument(
        "--manifest", type=Path, required=True, help="Registered parameter-identification inputs"
    )
    p.add_argument("--output", type=Path, required=True)
    p.add_argument(
        "--base-config", type=Path, help="Optional resolved config for a complete battery profile"
    )
    p.add_argument("--capacity-csv", type=Path)
    p.add_argument("--current-csv", type=Path)
    p.add_argument("--reference-capacity-ah", type=float)
    p.add_argument("--reference-current-a", type=float)
    p.add_argument("--protocol", help="Characterization protocol/run reference")
    p = subs.add_parser("verify-manifest")
    p.add_argument("manifest", type=Path)
    p = subs.add_parser("evaluate")
    p.add_argument("--predicted", type=Path, required=True)
    p.add_argument("--measured", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument(
        "--role",
        choices=["parameter_identification", "model_selection", "final_validation"],
        default="final_validation",
    )
    p.add_argument(
        "--columns", type=Path, help="JSON mapping canonical column -> measured CSV column"
    )
    p.add_argument("--alignment", choices=["exact", "linear"], default="exact")
    p.add_argument(
        "--predicted-sample-kind",
        choices=["instantaneous", "interval_mean"],
        default="interval_mean",
    )
    p.add_argument(
        "--measured-sample-kind",
        choices=["instantaneous", "interval_mean"],
        default="instantaneous",
    )
    p.add_argument("--reserve-soc", type=float)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command in ("compare", "sensitivity"):
            config = load_config(args.config)
            mission = read_mission(args.mission, config["simulation"]["dt_s"])
            kwargs = {"reserve_soc": args.reserve_soc, "input_path": args.mission}
            if args.command == "compare":
                compare_models(config, mission, args.output_dir, **kwargs)
            else:
                spec = json.loads(args.specification.read_text(encoding="utf-8"))
                study(config, mission, spec, args.output_dir, **kwargs)
            print(f"Saved offline energy-only study: {args.output_dir}; mission completion unknown")
        elif args.command == "import-battery":
            result = battery_maps(
                args.csv,
                capacity_path=args.capacity_csv,
                current_path=args.current_csv,
                reference_capacity_Ah=args.reference_capacity_ah,
                reference_current_A=args.reference_current_a,
                protocol=args.protocol,
                manifest_path=args.manifest,
            )
            if args.base_config:
                result = apply_battery_maps(load_config(args.base_config)["battery"], result)
            write_json(args.output, result)
            print(f"Imported user measurements: {args.output}; independent validation pending")
        elif args.command == "verify-manifest":
            result = verify_manifest(args.manifest)
            print(f"Verified {len(result['runs'])} distinct runs; hash {result['manifest_sha256']}")
        elif args.command == "evaluate":
            result = evaluate_files(
                args.predicted,
                args.measured,
                manifest_path=args.manifest,
                run_id=args.run_id,
                role=args.role,
                measured_columns=None
                if args.columns is None
                else json.loads(args.columns.read_text(encoding="utf-8")),
                alignment=args.alignment,
                predicted_sample_kind=args.predicted_sample_kind,
                measured_sample_kind=args.measured_sample_kind,
                reserve_soc=args.reserve_soc,
            )
            write_json(args.output, result)
            print(f"Saved {args.role} metrics: {args.output}")
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Study failed: {exc}\n")


if __name__ == "__main__":
    main()
