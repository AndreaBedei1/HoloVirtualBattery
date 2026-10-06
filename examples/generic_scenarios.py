"""Same effort history with explicit battery, water and payload variations."""

import argparse
import copy
from pathlib import Path

from my_vehicle_energy_demo import my_vehicle_config

from holoenergy.analysis.replay import run_mission
from holoenergy.config import load_config
from holoenergy.provenance import write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=600)
    parser.add_argument("--output-dir", type=Path, default=Path("logs/generic_scenarios"))
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    base = my_vehicle_config()
    # Supplied demonstration maps, not chemistry-wide coefficients.
    base["battery"]["resistance_temperature_curve"] = [[0, 2], [25, 1]]
    base["battery"]["metadata"]["assumptions"] = "Synthetic supplied temperature map"
    variants = {"baseline": base}
    for name in (
        "water_4C",
        "water_25C",
        "battery_15Ah",
        "neutral_payload_5kg",
        "dense_payload_5kg",
        "electrical_payload_18W",
    ):
        variants[name] = copy.deepcopy(base)
    variants["water_4C"]["environment"]["water_temperature_C"] = 4
    variants["water_25C"]["environment"]["water_temperature_C"] = 25
    variants["battery_15Ah"]["battery"]["capacity_Ah"] = 15
    for name, volume in (("neutral_payload_5kg", 0.005), ("dense_payload_5kg", 0.001)):
        variants[name]["vehicle"]["payload"] = {
            "mass_kg": 5,
            "displaced_volume_m3": volume,
            "position_m": [0.1, 0, 0],
        }
    variants["electrical_payload_18W"]["components"].append(
        {"name": "added_scientific_sensor", "active_W": 18}
    )
    commands = [{"action": [5] * 6, "phase": "inspection"} for _ in range(args.steps)]
    records = {}
    for name, config in variants.items():
        run_mission(load_config(data=config), commands, args.output_dir / name)
        import json

        summary = json.loads(
            (args.output_dir / name / "energy.jsonl.summary.json").read_text(encoding="utf-8")
        )
        final = json.loads(
            (args.output_dir / name / "energy.jsonl").read_text(encoding="utf-8").splitlines()[-1]
        )
        records[name] = {
            "summary": summary,
            "final_soc": final["soc"],
            "battery_temperature_C": final["battery_temperature_C"],
            "voltage_V": final["voltage_V"],
            "vehicle_dynamics_status": final["vehicle_dynamics_status"],
        }
    baseline = records["baseline"]
    for name in ("neutral_payload_5kg", "dense_payload_5kg"):
        assert (
            records[name]["summary"]["terminal_energy_Wh"]
            == baseline["summary"]["terminal_energy_Wh"]
        )
        assert records[name]["vehicle_dynamics_status"] == "descriptive_only_not_applied"
    assert records["battery_15Ah"]["final_soc"] < baseline["final_soc"]
    assert (
        records["water_4C"]["battery_temperature_C"] < records["water_25C"]["battery_temperature_C"]
    )
    assert (
        records["water_4C"]["summary"]["category_energy_Wh"]["battery_losses"]
        > records["water_25C"]["summary"]["category_energy_Wh"]["battery_losses"]
    )
    report = {
        "evidence_kind": "synthetic configured models; not physical validation",
        "current_comparison": "Separate native_station_keeping.py uses actual native currents",
        "physical_payload_boundary": "Replay has no dynamics; mass/volume changes are descriptive and intentionally cannot alter energy for identical effort",
        "records": records,
    }
    write_json(args.output_dir / "scenario_report.json", report)
    print(f"Verified {len(records)} same-effort scenarios: {args.output_dir}")


if __name__ == "__main__":
    main()
