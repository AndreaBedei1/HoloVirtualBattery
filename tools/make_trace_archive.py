"""Build a Zenodo-ready archive of the final 100 Hz traces (brief section 38). Nothing is uploaded.

The archive contains every ``logs/final/full/*.trace.jsonl.gz`` named by a committed final summary,
a MANIFEST.json and a README. For each trace the manifest records:
- the SHA256 of the gzip file and of its decompressed content (the latter is the value recorded
  in the summary);
- the run label, commit and dirty flag;
- the configuration SHA256 and the backend binary SHA256.
A trace whose content hash does not match its summary is refused.

    uv run python tools/make_trace_archive.py [--output dist/holoenergy_final_traces.zip]
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "experiments/results/final/native"
FULL = ROOT / "logs/final/full"

README = """HoloEnergy final native runs: 100 Hz traces
=============================================

Per-tick traces (JSON lines, gzip) of the 36 final native runs. They were produced from a clean
commit on HoloOcean 2.3.0 rebuilt with the drag-units patch, at 100 Hz. Each run's summary and
0.1 s trace are in the HoloEnergy repository under experiments/results/final/native/.

Verification: for each entry in MANIFEST.json, the SHA256 of the decompressed trace must equal
`content_sha256`, which is also the value stored in the run's summary (traces.full_per_tick).
experiments/verify_final_energy.py recomputes every reported energy from these traces.

The patched HoloOcean binary itself is not redistributed. Its SHA256 is recorded per run.
docs/holoocean_patched_build.md gives the source patch, the HoloOcean and Unreal commits, the
compiler and the build recipe.
"""


def entries():
    for summary_path in sorted(FINAL.glob("*/*.summary.json")):
        s = json.loads(summary_path.read_text(encoding="utf-8"))
        label = s["spec"]["label"]
        trace = FULL / f"{label}.trace.jsonl.gz"
        raw = trace.read_bytes()
        content = hashlib.sha256(gzip.decompress(raw)).hexdigest()
        expected = s["traces"]["full_per_tick"]["content_sha256"]
        if content != expected:
            raise SystemExit(f"{trace}: content SHA256 {content} != summary {expected}")
        yield (
            trace,
            {
                "run": label,
                "group": s["spec"]["group"],
                "file": trace.name,
                "gzip_sha256": hashlib.sha256(raw).hexdigest(),
                "content_sha256": content,
                "bytes": len(raw),
                "commit": s["provenance"]["git"].get("commit"),
                "dirty": s["provenance"]["git"].get("dirty"),
                "config_sha256": s.get("config_sha256"),
                "backend_binary_sha256": s["provenance"]["backend"].get("binary_sha256"),
                "summary": f"experiments/results/final/native/{s['spec']['group']}/{summary_path.name}",
            },
        )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=ROOT / "dist/holoenergy_final_traces.zip")
    args = parser.parse_args(argv)
    items = list(entries())
    manifest = {
        "description": "HoloEnergy final native runs, 100 Hz traces",
        "runs": len(items),
        "commits": sorted({m["commit"] for _, m in items}),
        "files": [m for _, m in items],
        "license_note": "generated simulation data; HoloOcean binary not included",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, meta in items:
            archive.write(path, f"traces/{meta['file']}")
        archive.writestr("MANIFEST.json", json.dumps(manifest, indent=2) + "\n")
        archive.writestr("README.txt", README)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        f"{len(items)} traces -> {args.output} ({args.output.stat().st_size / 1e6:.1f} MB) sha256 {digest}"
    )


if __name__ == "__main__":
    main()
