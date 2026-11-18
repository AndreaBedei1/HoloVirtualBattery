"""Same-mission comparison with existing energy-modelling approaches (brief section 21).

Neither tool can be executed here, so their published model structures are reproduced
mathematically on the final HoloEnergy missions. This is a model comparison, not tool execution,
and not an accuracy ranking (no measured energy exists):

* **PSM (Danielis et al. 2021).** Constant power per subsystem state, no propulsion physics.
  The paper gives no propulsion powers, so the state powers (moving, manoeuvre, hover) are
  calibrated on the calm-water transit, which is the best case for this structure. Modem: TX 2.8 W
  up to 1 km, "Active" below 1 W (taken at 1 W) for every other time, TX time = message bits /
  13.9 kbit/s (Danielis Fig. 2, Table 2).
* **Gazebo/UUV Simulator style.** A constant ``power_load`` per thruster while it is commanded
  (consumption not effort-dependent, Gazebo Sim battery documentation), calibrated on the same
  calm transit (mean power per active thruster).
* **HoloEnergy.** The final native runs.

For each mission the script reports the propulsion energy of each approach, which components
each approach includes, and whether it can represent station keeping in current.

    uv run python experiments/run_tool_comparison.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "experiments/results/final"
HOTEL_W = (
    5.75  # navigator 0.75 + companion computer 3.9 + camera 1.1 W (final runs, default avionics)
)
STATES = {
    "moving": ("accelerate", "transit_out", "return_accelerate", "return_transit"),
    "manoeuvre": ("stop", "yaw", "return_stop"),
    "hover": ("hold_start", "hold_turn", "hold_end", "station"),
}
DANIELIS = {"tx_W": 2.8, "active_W": 1.0, "bitrate_bps": 13_900}  # Danielis 2021 Fig. 2, Table 2
MISSIONS = {
    "transit calm": ("EXP5", "EXP5-transit-c0"),
    "transit 0.2 m/s": ("EXP5", "EXP5-transit-c0.2"),
    "transit 0.4 m/s": ("EXP5", "EXP5-transit-c0.4"),
    "station calm": ("EXP5", "EXP5-station-c0"),
    "station 0.2 m/s head-on": ("EXP3", "EXP3-L8-HV-headon0.2"),
    "station 0.5 m/s head-on": ("EXP3", "EXP3-L8-HV-headon0.5"),
}


def load(group, label):
    return json.loads((FINAL / f"native/{group}/{label}.summary.json").read_text(encoding="utf-8"))


def state_of(phase):
    for state, phases in STATES.items():
        if phase in phases:
            return state
    return "hover"


def phase_propulsion(summary):
    """Propulsion energy and duration per mission phase (terminal minus the constant hotel)."""
    out = {}
    for phase, row in summary["metrics"]["phase_energy_Wh"].items():
        duration = row["duration_s"]
        out[phase] = (row["terminal_energy_Wh"] - HOTEL_W * duration / 3600, duration)
    return out


def calibrate(calm):
    """PSM state powers and the Gazebo per-thruster power_load from the calm transit."""
    energy, time = {}, {}
    for phase, (wh, s) in phase_propulsion(calm).items():
        state = state_of(phase)
        energy[state] = energy.get(state, 0.0) + wh
        time[state] = time.get(state, 0.0) + s
    psm = {state: 3600 * energy[state] / time[state] for state in energy}
    horizontals = [k for k in calm["summary"]["device_energy_Wh"] if k.startswith("H")]
    # Same "commanded" definition as in the evaluation, so the calibration mission is
    # reproduced exactly (best case for this structure).
    commanded_s = sum(s for wh, s in phase_propulsion(calm).values() if wh > 1e-9)
    propulsion_Wh = calm["metrics"]["category_energy_Wh"]["propulsion"]
    power_load = 3600 * propulsion_Wh / commanded_s / len(horizontals)
    return psm, power_load, len(horizontals)


def compare(psm, power_load, n_active):
    rows = []
    for name, (group, label) in MISSIONS.items():
        s = load(group, label)
        phases = phase_propulsion(s)
        holo = s["metrics"]["category_energy_Wh"]["propulsion"]
        psm_Wh = sum(psm[state_of(p)] * dur / 3600 for p, (_, dur) in phases.items())
        commanded_s = sum(dur for p, (wh, dur) in phases.items() if wh > 1e-9)
        gazebo_Wh = n_active * power_load * commanded_s / 3600
        rows.append(
            {
                "mission": name,
                "run": label,
                "holoenergy_propulsion_Wh": holo,
                "psm_propulsion_Wh": psm_Wh,
                "gazebo_style_propulsion_Wh": gazebo_Wh,
                "psm_over_holoenergy": psm_Wh / holo if holo > 1e-9 else None,
                "gazebo_over_holoenergy": gazebo_Wh / holo if holo > 1e-9 else None,
            }
        )
    return rows


def communication():
    cross = json.loads((FINAL / "crosslayer.json").read_text(encoding="utf-8"))
    res = cross["results"]["direct"]
    iface = next(iter(res["network"]["vehicle_metrics"]["interfaces"].values()))
    duration = res["mission"]["duration_s"]
    tx_s = iface["tx_bits"] / DANIELIS["bitrate_bps"]
    psm = (DANIELIS["tx_W"] * tx_s + DANIELIS["active_W"] * (duration - tx_s)) / 3600
    return {
        "holoenergy_modem_Wh": res["network"]["vehicle_modem_Wh_on_bus"],
        "holoenergy_basis": "DESERT PHY airtime (4.8 kbit/s); TX 2.8 W; RX/LISTEN 0.8 W upper bound",
        "psm_modem_Wh": psm,
        "psm_basis": "airtime bits/13.9 kbit/s; TX 2.8 W; Active 1 W (paper: below 1 W)",
        "tx_bits": iface["tx_bits"],
        "duration_s": duration,
    }


CAPABILITIES = {
    "thruster effort": (
        "yes: allocation + T200 tables per tick",
        "no: state power",
        "no: constant power_load while commanded",
    ),
    "station keeping in current": (
        "yes: effort follows the current",
        "no: hover power is current-independent",
        "partly: on/off only, magnitude-independent",
    ),
    "battery voltage coupling": (
        "yes: L1 Rint, voltage-dependent tables, derating",
        "no",
        "yes: linear battery; loads constant",
    ),
    "communication energy": (
        "yes: PHY events from DESERT",
        "yes: modem state machine",
        "no (not in the battery plugin)",
    ),
    "evidence per parameter": ("yes", "no (handbook values, not cited per parameter)", "no"),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=FINAL / "tool_comparison.json")
    args = parser.parse_args(argv)
    calm = load("EXP5", "EXP5-transit-c0")
    psm, power_load, n_active = calibrate(calm)
    out = {
        "kind": "model comparison (published model structures reproduced), not tool execution",
        "calibration": {
            "mission": "EXP5-transit-c0",
            "psm_state_power_W": psm,
            "gazebo_power_load_W_per_thruster": power_load,
            "active_thrusters": n_active,
        },
        "propulsion": compare(psm, power_load, n_active),
        "communication": communication(),
        "capabilities": {
            k: dict(zip(("HoloEnergy", "PSM (Danielis)", "Gazebo/UUV style"), v, strict=True))
            for k, v in CAPABILITIES.items()
        },
    }
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(out["calibration"], indent=1))
    for r in out["propulsion"]:
        print(
            f"{r['mission']:26s} holo {r['holoenergy_propulsion_Wh']:.4f} psm {r['psm_propulsion_Wh']:.4f} "
            f"gazebo {r['gazebo_style_propulsion_Wh']:.4f}"
        )
    print(out["communication"])


if __name__ == "__main__":
    main()
