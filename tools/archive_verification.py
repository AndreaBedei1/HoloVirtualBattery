"""Archive simulator/software evidence summaries and log hashes, never physical validation."""

import argparse
import json
from pathlib import Path

from holoenergy.analysis.metrics import summarize
from holoenergy.provenance import file_hash, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--logs-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runs = []
    for path in (
        sorted(args.logs_dir.rglob("energy.jsonl"))
        + sorted(args.logs_dir.rglob("sonar_*.jsonl"))
        + sorted(args.logs_dir.rglob("motion_derating_*.jsonl"))
    ):
        metadata_path = path.with_suffix(path.suffix + ".metadata.json")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if file_hash(path) != metadata["output_dataset_sha256"]:
            raise ValueError(f"Log/sidecar hash mismatch: {path}")
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        runs.append(
            {
                "path": str(path).replace("\\", "/"),
                "log_sha256": file_hash(path),
                "sidecar_sha256": file_hash(metadata_path),
                "run_id": metadata["run_id"],
                "created_utc": metadata["created_utc"],
                "git": metadata["git"],
                "holoenergy_version": metadata["holoenergy_version"],
                "holoocean_version": metadata["holoocean_version"],
                "package_source_sha256": metadata.get("package_source_sha256"),
                "configuration_sha256": metadata["resolved_config_sha256"],
                "profile_sha256": metadata["profile_sha256"],
                "placeholders": metadata["placeholders"],
                "scenario": metadata["scenario"],
                "metrics": summarize(rows),
            }
        )
    report_path = args.logs_dir / "holoocean/integration_report.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    for key in ("derated", "accounting_only"):
        report[key].pop("provenance", None)
    write_json(
        args.output,
        {
            "evidence_kind": "software/native simulator verification",
            "physical_energy_validation": False,
            "integration_report_sha256": file_hash(report_path),
            "native_integration": report,
            "runs": runs,
        },
    )
    print(f"Archived {len(runs)} traceable software runs: {args.output}")


if __name__ == "__main__":
    main()
