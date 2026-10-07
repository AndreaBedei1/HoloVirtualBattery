"""Campaign archive: layout, deterministic compression and suite verdicts (synthetic)."""

import gzip
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "archive_verified_backend", ROOT / "tools/archive_verified_backend.py"
)
archive = importlib.util.module_from_spec(spec)
spec.loader.exec_module(archive)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_archive_layout_and_deterministic_compression(tmp_path):
    src = tmp_path / "logs"
    write(src / "drag_x/raw.jsonl", '{"step": 0}\n')
    write(src / "drag_x/report.json", "{}")
    write(src / "energy/run.jsonl", '{"tick": 0}\n')
    write(src / "energy/run.jsonl.metadata.json", '{"profiles": {}}')
    write(src / "energy/nested/metrics.json", "{}")
    write(src / "campaign.json", "[]")
    write(src / "console.log", "done\n")
    first = archive.archive(src, tmp_path / "a")
    second = archive.archive(src, tmp_path / "b")
    assert first == second
    for name in ("drag_x/raw.jsonl.gz", "energy/run.jsonl.metadata.json.gz"):
        assert (tmp_path / "a" / name).read_bytes() == (tmp_path / "b" / name).read_bytes()
        assert first[name]["raw_sha256"] == archive.sha(src / name[: -len(".gz")])
    with gzip.open(tmp_path / "a/drag_x/raw.jsonl.gz", "rt", encoding="utf-8") as handle:
        assert handle.read() == '{"step": 0}\n'
    # Full per-tick logs are hashed, not copied; nested reports and console logs are kept.
    assert first["energy/run.jsonl"] == {"local_only_sha256": archive.sha(src / "energy/run.jsonl")}
    assert not (tmp_path / "a/energy/run.jsonl").exists()
    assert (tmp_path / "a/energy/nested/metrics.json").is_file()
    assert (tmp_path / "a/run_logs/console.log").is_file()
    assert (tmp_path / "a/campaign.json").is_file()


def drag_report(case, scale, velocities):
    checks = (
        "neutral_zero_motion_below_1e_6_m_s",
        "angular_motion_below_1e_4_rad_s",
        "no_collisions",
        "quadratic_doubling_ratios_near_4",
    )
    return {
        "result": {
            "case": case,
            "observed_expected_scale_mean": scale,
            "max_thrust_reference_error_N": 6e-7,
            "max_gravity_error_m_s2": 7e-7,
            "checks": dict.fromkeys(checks, True),
            "drag_families": {"signed_axes_and_yaw": {"first_pulse_scale_mean": scale}},
        },
        "records": [
            {"case": "current_x_0.1", "ticks_per_sec": 100, "trial": 0, "velocity_m_s": velocities}
        ],
    }


def control_entry(tmp_path, rebuilt_velocity):
    src = tmp_path / f"logs_{rebuilt_velocity}"
    reports = {
        "original": drag_report("CASE C", 0.01, [1e-4, 0.0, 0.0]),
        "rebuilt": drag_report("CASE C", 0.01, [rebuilt_velocity, 0.0, 0.0]),
        "patched": drag_report("CASE A", 1.0, [1e-2, 0.0, 0.0]),
    }
    for build, report in reports.items():
        write(src / f"drag_{build}/report.json", json.dumps(report))
    items = {item["item"]: item for item in archive.suite(src)}
    return items["control rebuild reproduces official binary"]


def test_bit_identical_control_rebuild_passes(tmp_path):
    identical = control_entry(tmp_path, 1e-4)
    assert identical["values"]["max_velocity_difference_m_s"] == 0.0
    assert identical["status"] == "PASS"
    assert control_entry(tmp_path, 2e-4)["status"] == "FAIL"


def test_missing_campaign_outputs_fail_instead_of_passing(tmp_path):
    items = {item["item"]: item for item in archive.suite(tmp_path)}
    for name in (
        "drag BEFORE (official 2.3.0)",
        "control rebuild reproduces official binary",
        "HoloEnergy derating, patched",
        "dashboard, patched",
        "clean shutdown",
    ):
        assert items[name]["status"] == "FAIL"
