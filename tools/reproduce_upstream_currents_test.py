"""Reproduce HoloOcean's own test_currents_underwater on a second agent (HoveringAUV).

Upstream ``client/tests/scenarios/test_currents.py`` (v2.3.0) asserts a first-tick
DynamicsSensor acceleration of 0.06320982 m/s² for a 1 m/s current on HoveringAUV
at 60 Hz in the TestWorlds package. This script runs the same sequence (reset, set
current, one tick) in the installed Ocean package (SimpleUnderwater; TestWorlds is
not installed here) on any build and compares the measured acceleration with the
upstream constant and with the source SI equation:

    a = 0.5 * rho * Cd * A * u^2 / m * (1 - c * dt)     (UE ether drag after the step)

HoveringAUV literals from the v2.3.0 source: m = 31.02 kg, Cd = 0.8, A = 0.5 m²,
linear damping c = 1 s⁻¹, rho = 997 kg/m³. Native only, no HoloEnergy import.
"""

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.audit_holoocean_drag import git_info, runtime_provenance, write_json  # noqa: E402
from tools.holoocean_backend import make_env  # noqa: E402

TPS = 60
UPSTREAM_EXPECTED = 0.06320982
PARAMS = {"mass_kg": 31.02, "drag_coefficient": 0.8, "area_m2": 0.5, "density_kg_m3": 997.0}
DAMPING_PER_S = 1.0


def si_expected(u):
    k = 0.5 * PARAMS["density_kg_m3"] * PARAMS["drag_coefficient"] * PARAMS["area_m2"]
    return k * u * u / PARAMS["mass_kg"] * (1 - DAMPING_PER_S / TPS)


def scenario():
    return {
        "name": "upstream currents test reproduction",
        "package_name": "Ocean",
        "world": "SimpleUnderwater",
        "main_agent": "auv0",
        "ticks_per_sec": TPS,
        "frames_per_sec": False,
        "agents": [
            {
                "agent_name": "auv0",
                "agent_type": "HoveringAUV",
                "sensors": [
                    {
                        "sensor_type": "DynamicsSensor",
                        "configuration": {"UseCOM": True, "UseRPY": False},
                    }
                ],
                "control_scheme": 0,
                "location": [0, 0, -10],
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", type=Path, help="Package executable; default installed Ocean")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    with make_env(scenario(), TPS, args.binary) as env:
        env.reset()
        null = env.tick()["DynamicsSensor"][:3].astype(float).tolist()
        rows.append({"current_m_s": [0, 0, 0], "acceleration_m_s2": null})
        for axis in range(3):
            current = [0, 0, 0]
            current[axis] = 1
            env.reset()
            env.set_ocean_currents("auv0", current)
            accel = env.tick()["DynamicsSensor"][:3].astype(float).tolist()
            rows.append({"current_m_s": current, "acceleration_m_s2": accel})
    expected = si_expected(1.0)
    measured = [r["acceleration_m_s2"][i] for i, r in enumerate(rows[1:])]
    result = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "second-agent implementation check; not vehicle validation",
        "holoenergy_repository": git_info(ROOT),
        "runtime": runtime_provenance(args.binary),
        "parameters": PARAMS | {"linear_damping_per_s": DAMPING_PER_S, "ticks_per_sec": TPS},
        "upstream_expected_m_s2": UPSTREAM_EXPECTED,
        "si_expected_m_s2": expected,
        "upstream_value_over_si": UPSTREAM_EXPECTED / expected,
        "rows": rows,
        "measured_over_si": [m / expected for m in measured],
        "measured_over_upstream": [m / UPSTREAM_EXPECTED for m in measured],
        "null_current_max_abs_m_s2": max(abs(a) for a in rows[0]["acceleration_m_s2"]),
    }
    write_json(args.output, result)
    print(
        f"SI expected {expected:.6f} m/s^2, upstream test {UPSTREAM_EXPECTED} m/s^2; "
        f"measured/SI {[round(x, 6) for x in result['measured_over_si']]}"
    )


if __name__ == "__main__":
    main()
