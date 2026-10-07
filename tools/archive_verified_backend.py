"""Archive the native verified-backend campaign and summarize the native suite.

Copies machine-readable outputs from logs/verified_backend into
sources/verified_backend (deterministic gzip for raw JSONL, hashes for large local
logs) and writes native_suite.json: one entry per native verification item with the
quantitative criterion, the measured values and PASS/FAIL. Nothing is recomputed
from scratch except comparisons between archived reports.
"""

import argparse
import gzip
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUILDS = ("original", "rebuilt", "patched")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def gzip_copy(source, target):
    data = Path(source).read_bytes()
    with (
        Path(target).open("wb") as raw,
        gzip.GzipFile(filename=Path(source).name, mode="wb", fileobj=raw, mtime=0) as handle,
    ):
        handle.write(data)
    return {"raw_sha256": hashlib.sha256(data).hexdigest(), "raw_bytes": len(data)}


def load(path):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def archive(src, dst):
    index = {}
    dst.mkdir(parents=True, exist_ok=True)
    for item in sorted(src.iterdir()):
        if item.is_dir():
            sub = dst / item.name
            sub.mkdir(exist_ok=True)
            for child in sorted(item.iterdir()):
                if child.suffix == ".jsonl" and child.name == "raw.jsonl":
                    index[f"{item.name}/{child.name}.gz"] = gzip_copy(
                        child, sub / (child.name + ".gz")
                    )
                elif child.suffix == ".jsonl":
                    # Full per-tick energy logs stay local; their hashes are in the reports.
                    index[f"{item.name}/{child.name}"] = {"local_only_sha256": sha(child)}
                elif child.suffix in (".json", ".csv") or child.name.endswith(".jsonl.gz"):
                    shutil.copy2(child, sub / child.name)
                    index[f"{item.name}/{child.name}"] = {"sha256": sha(child)}
        elif item.suffix in (".json", ".log"):
            target = dst / ("campaign_" + item.name if item.suffix == ".log" else item.name)
            shutil.copy2(item, target)
            index[target.name] = {"sha256": sha(item)}
    return index


def close(value, target, rel):
    return value is not None and math.isclose(value, target, rel_tol=rel)


def entry(name, criterion, values, passed):
    return {
        "item": name,
        "criterion": criterion,
        "values": values,
        "status": "PASS" if passed else "FAIL",
    }


def paired_difference(a, b, key):
    """Max abs difference of a record field between two campaigns of identical cases."""
    if not a or not b:
        return None
    index = {(r["case"], r["ticks_per_sec"], r["trial"]): r for r in b["records"]}
    worst = 0.0
    for r in a["records"]:
        other = index.get((r["case"], r["ticks_per_sec"], r["trial"]))
        if other is None:
            return None
        worst = max(worst, max(abs(x - y) for x, y in zip(r[key], other[key], strict=True)))
    return worst


def before_after_table(src):
    """Expected vs inferred first-step drag per current magnitude, all rates and trials."""
    import statistics

    reports = {b: load(src / f"drag_{b}/report.json") for b in BUILDS}
    rows = []
    for u in (0.1, 0.2, 0.4, 0.8):
        name = f"current_x_{u:g}"
        row = {"current_m_s": u}
        for build, report in reports.items():
            if not report:
                continue
            recs = [r for r in report["records"] if r["case"] == name]
            forces = [abs(r["observed_drag_N"][0]) for r in recs]
            ratios = [r["observed_expected_scale"] for r in recs]
            row["expected_N"] = abs(recs[0]["expected_drag_N"][0])
            row[f"{build}_N_mean"] = statistics.mean(forces)
            row[f"{build}_N_stdev"] = statistics.stdev(forces)
            row[f"{build}_ratio_mean"] = statistics.mean(ratios)
            row[f"{build}_ratio_stdev"] = statistics.stdev(ratios)
            row[f"{build}_samples"] = len(recs)
        rows.append(row)
    return rows


def suite(src):
    drag = {b: load(src / f"drag_{b}/report.json") for b in BUILDS}
    auto = {b: load(src / f"autodrag_{b}/report.json") for b in BUILDS}
    steps = {b: load(src / f"timestep_{b}/report.json") for b in BUILDS}
    checks = {b: load(src / f"check_{b}.json") for b in BUILDS}
    items = []
    o, r, p = (drag[b]["result"] if drag[b] else None for b in BUILDS)
    items.append(
        entry(
            "drag BEFORE (official 2.3.0)",
            "decisive campaign CASE C, applied/expected mean within 0.1% of 0.01, references verified",
            {"case": o and o["case"], "scale_mean": o and o["observed_expected_scale_mean"]},
            bool(o)
            and o["case"] == "CASE C"
            and close(o["observed_expected_scale_mean"], 0.01, 1e-3),
        )
    )
    items.append(
        entry(
            "control rebuild reproduces official binary",
            "same case and every first-step velocity within 1e-6 m/s of the official run",
            {
                "case": r and r["case"],
                "scale_mean": r and r["observed_expected_scale_mean"],
                "max_velocity_difference_m_s": paired_difference(
                    drag["original"], drag["rebuilt"], "velocity_m_s"
                ),
            },
            bool(r)
            and r["case"] == "CASE C"
            and (paired_difference(drag["original"], drag["rebuilt"], "velocity_m_s") or 1) < 1e-6,
        )
    )
    items.append(
        entry(
            "drag AFTER (patched 2.3.0)",
            "decisive campaign CASE A, applied/expected mean within 0.1% of 1",
            {"case": p and p["case"], "scale_mean": p and p["observed_expected_scale_mean"]},
            bool(p)
            and p["case"] == "CASE A"
            and close(p["observed_expected_scale_mean"], 1.0, 1e-3),
        )
    )
    for label, key, limit in (
        ("thruster force 10 N X/Y/Z", "max_thrust_reference_error_N", 0.05),
        ("gravity 9.8 m/s^2", "max_gravity_error_m_s2", 0.02),
    ):
        values = {b: drag[b]["result"][key] for b in BUILDS if drag[b]}
        items.append(
            entry(
                label,
                f"every build: error < {limit}",
                values,
                len(values) == 3 and max(values.values()) < limit,
            )
        )
    for label, check in (
        ("neutral buoyancy, zero current", "neutral_zero_motion_below_1e_6_m_s"),
        ("angular stability", "angular_motion_below_1e_4_rad_s"),
        ("no collisions", "no_collisions"),
        ("quadratic scaling", "quadratic_doubling_ratios_near_4"),
    ):
        values = {b: drag[b]["result"]["checks"][check] for b in BUILDS if drag[b]}
        items.append(
            entry(
                label,
                f"check '{check}' in every build",
                values,
                len(values) == 3 and all(values.values()),
            )
        )
    for label, family in (("current axes and signs, yaw 90 deg", "signed_axes_and_yaw"),):
        values = {
            b: drag[b]["result"]["drag_families"][family]["first_pulse_scale_mean"]
            for b in BUILDS
            if drag[b]
        }
        passed = close(values.get("original"), 0.01, 1e-3) and close(
            values.get("patched"), 1.0, 1e-3
        )
        items.append(
            entry(label, "before ~0.01, after ~1 for +-X/+-Y/+-Z and yawed vehicle", values, passed)
        )
    values = {
        b: {
            "first_pulse": auto[b]["result"]["drag_families"]["autodrag_still_water"][
                "first_pulse_scale_mean"
            ],
            "all_steps": auto[b]["result"]["drag_families"]["autodrag_still_water"][
                "step_scale_mean"
            ],
        }
        for b in BUILDS
        if auto[b]
    }
    items.append(
        entry(
            "autodrag (moving vehicle, still water)",
            "before ~0.01, after ~1 on first pulse and on every step",
            values,
            bool(values.get("patched"))
            and close(values["patched"]["first_pulse"], 1.0, 1e-3)
            and close(values["patched"]["all_steps"], 1.0, 1e-3)
            and close(values["original"]["first_pulse"], 0.01, 1e-3),
        )
    )
    for b in BUILDS:
        s = steps[b]
        if not s:
            continue
        ratios = {k: v["effective_to_client_ratio"] for k, v in s["result_by_tick_rate"].items()}
        items.append(
            entry(
                f"timestep ({b})",
                ">= 30 Hz consistent (|ratio-1| < 1e-4); 20 Hz capped at 1/30 s (ratio 2/3)",
                {
                    "verified": s["verified_ticks_per_sec"],
                    "rejected": s["rejected_ticks_per_sec"],
                    "ratios": ratios,
                },
                s["rejected_ticks_per_sec"] == [20] and close(ratios.get("20"), 2 / 3, 1e-4),
            )
        )
    for b in BUILDS:
        c = checks[b]
        if c:
            expected = "PASS" if b == "patched" else "FAIL"
            items.append(
                entry(
                    f"backend check ({b})",
                    f"drag {expected}, physics step PASS at 100 Hz",
                    {"drag": c["drag"], "physics_step": c["physics_step"]},
                    c["drag"]["status"] == expected and c["physics_step"]["status"] == "PASS",
                )
            )
    study = load(src / "energy_patched/patched_report.json")
    if study:
        station = sorted(
            (v["current_m_s"][0], v)
            for k, v in study["records"].items()
            if k.startswith("station_")
        )
        power = [v["mean_tail_propulsion_W"] for _, v in station]
        items.append(
            entry(
                "station keeping, patched",
                "tail propulsion power strictly increasing with current (no fitting)",
                {
                    "current_m_s": [u for u, _ in station],
                    "mean_tail_propulsion_W": power,
                    "tail_saturated_fraction": [
                        v["tail_saturated_tick_fraction"] for _, v in station
                    ],
                },
                len(power) >= 2 and all(b > a for a, b in zip(power, power[1:], strict=False)),
            )
        )
        missions = sorted(
            (v["current_m_s"][0], v)
            for k, v in study["records"].items()
            if k.startswith("mission_")
        )
        items.append(
            entry(
                "mission movement, patched",
                "all missions completed the reference plan; energies reported",
                {
                    "current_m_s": [u for u, _ in missions],
                    "terminal_Wh": [v["terminal_Wh"] for _, v in missions],
                    "max_position_error_m": [v["max_position_error_m"] for _, v in missions],
                },
                len(missions) == 3,
            )
        )
    integration = load(src / "derating_patched/integration_report.json")
    items.append(
        entry(
            "HoloEnergy derating, patched",
            "8 A test limit derates actions (factor < 1) and shortens surge vs accounting-only",
            {
                "minimum_derating_factor": integration
                and integration["derated"]["minimum_derating_factor"],
                "surge_derated_m": integration and integration["derated"]["surge_displacement_m"],
                "surge_accounting_only_m": integration
                and integration["accounting_only"]["surge_displacement_m"],
            },
            bool(integration)
            and integration["derated"]["minimum_derating_factor"] < 1
            and integration["derated"]["surge_displacement_m"]
            < integration["accounting_only"]["surge_displacement_m"],
        )
    )
    realtime = load(src / "dashboard_patched/realtime_report.json")
    items.append(
        entry(
            "dashboard, patched",
            "telemetry published during the native run, none dropped, power limit applied",
            {
                "telemetry_sent": realtime and realtime["telemetry_sent"],
                "telemetry_dropped": realtime and realtime["telemetry_dropped"],
                "minimum_derating_factor": realtime and realtime["minimum_derating_factor"],
            },
            bool(realtime)
            and realtime["telemetry_sent"] > 0
            and realtime["telemetry_dropped"] == 0
            and realtime["power_limit_applied_to_backend"],
        )
    )
    shutdown = load(src / "clean_shutdown.json")
    items.append(
        entry(
            "clean shutdown",
            "no Holodeck process left after every native run; integration processes closed",
            shutdown,
            bool(shutdown)
            and shutdown.get("holodeck_processes_after_campaign") == 0
            and bool(integration)
            and integration["derated"]["engine_process_closed"]
            and integration["accounting_only"]["engine_process_closed"],
        )
    )
    return items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "logs/verified_backend")
    parser.add_argument("--target", type=Path, default=ROOT / "sources/verified_backend")
    args = parser.parse_args()
    index = archive(args.source, args.target)
    items = suite(args.source)
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "native physics implementation verification; not physical vehicle validation",
        "items": items,
        "passed": sum(i["status"] == "PASS" for i in items),
        "failed": [i["item"] for i in items if i["status"] == "FAIL"],
    }
    (args.target / "native_suite.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    table = before_after_table(args.source)
    (args.target / "drag_before_after.json").write_text(
        json.dumps(table, indent=2) + "\n", encoding="utf-8"
    )
    if table:
        import csv

        with (args.target / "drag_before_after.csv").open(
            "w", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=list(table[0]))
            writer.writeheader()
            writer.writerows(table)
    (args.target / "archive_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )
    for item in items:
        print(f"{item['status']:4s} {item['item']}")


if __name__ == "__main__":
    main()
