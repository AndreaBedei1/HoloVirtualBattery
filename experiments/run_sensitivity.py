"""EXP10: sensitivity of propulsion energy to defensible alternatives (no invented ranges).

Part 1 (drag model). Mission energy is dominated by propulsion, and propulsion follows the
hydrodynamic load of the simulated vehicle, which is not validated. For steady station
keeping in a head-on current U the required surge force is evaluated with three published,
mutually inconsistent descriptions of BlueROV2 surge resistance (all from the evidence
registry): HoloOcean 2.3.0 literals (1/2 rho Cd A U^2), the mean restrained load measured on
a standard BlueROV2 (Gabl et al. 2021, linear interpolation of Table 1 means, no refit), and
the damping identified on a BlueROV2 Heavy (von Benzon et al. 2022, X_u U + X_uu U^2, used
only within its identified range <= 0.72 m/s). Each force is allocated on the simulator-exact
8-thruster layout within the native clamp and converted to electrical power with the T200
tables at a fixed bus voltage; the result is propulsion power and energy per 60 s.

Part 2 (component ranges). One-at-a-time variation of the parameters whose published
evidence gives a range (min-max) on the final inspection transit is reported by the
EnergyReport interval of each final run (holoenergy.uncertainty); parameters with only a
maximum (e.g. modem receive/listen power) stay open and are listed, never given an assumed
lower value.

    uv run python experiments/run_sensitivity.py [--output experiments/results/final/sensitivity.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_offline_campaign import NATIVE, t200_power  # noqa: E402

from holoenergy.allocation import ThrustAllocator  # noqa: E402
from holoenergy.evidence import default_registry  # noqa: E402

VOLTAGE_V = 15.5  # fixed bus voltage inside the T200 table range (same as offline E4)
CLAMP_N = 28.75  # holoocean_bluerov2.thruster_clamp
CURRENTS = (0.2, 0.4, 0.5, 0.6, 0.8)
WINDOW_S = 60.0


def dataset(registry, record_id):
    path = registry.get(record_id).dataset["path"]
    return json.loads(files("holoenergy").joinpath(path).read_text(encoding="utf-8"))


def drag_models(registry):
    rho = registry.get("holoocean_bluerov2.water_density").si()
    cd = registry.get("holoocean_bluerov2.drag_coefficient").si()
    area = registry.get("holoocean_bluerov2.drag_area").si()
    gabl = sorted(
        (r["speed_m_s"], r["force_N"])
        for r in dataset(registry, "bluerov2_standard.restrained_inline_load_head_on")["rows"]
    )
    # Average the repeated runs at the same speed; keep the measured zero (residual) point.
    by_speed = {}
    for u, f in gabl:
        by_speed.setdefault(u, []).append(f)
    gabl = sorted((u, sum(v) / len(v)) for u, v in by_speed.items())
    vb = dataset(registry, "bluerov2_heavy.translational_damping_identified")["coefficients"]

    def holoocean(u):
        return 0.5 * rho * cd * area * u * u, "in range"

    def gabl_interp(u):
        if u > gabl[-1][0] or u < gabl[0][0]:
            return None, "outside measured range"
        for (u0, f0), (u1, f1) in zip(gabl, gabl[1:], strict=False):
            if u0 <= u <= u1:
                return max(0.0, f0 + (f1 - f0) * (u - u0) / (u1 - u0)), "interpolated"
        return None, "outside measured range"

    def von_benzon(u):
        note = "in identified range" if u <= 0.72 else "extrapolated beyond 0.72 m/s"
        return vb["X_u_N_s_per_m"] * u + vb["X_uu_N_s2_per_m2"] * u * u, note

    return {
        "HoloOcean 2.3.0 literals": holoocean,
        "Gabl et al. 2021 restrained load (standard BlueROV2)": gabl_interp,
        "von Benzon et al. 2022 identified damping (Heavy)": von_benzon,
    }


def part1(registry):
    allocator = ThrustAllocator(NATIVE)
    lower, upper = [-CLAMP_N] * allocator.n, [CLAMP_N] * allocator.n
    rows = []
    for name, model in drag_models(registry).items():
        for u in CURRENTS:
            force, note = model(u)
            if force is None:
                rows.append(
                    {"drag_model": name, "current_m_s": u, "surge_force_N": None, "note": note}
                )
                continue
            result = allocator.allocate([force, 0, 0, 0, 0, 0], lower=lower, upper=upper)
            power = t200_power(result.forces_N, VOLTAGE_V)
            rows.append(
                {
                    "drag_model": name,
                    "current_m_s": u,
                    "surge_force_N": force,
                    "feasible_within_clamp": result.residual_norm < 1e-6,
                    "allocation_residual_N": result.residual_norm,
                    "propulsion_power_W": power,
                    "propulsion_Wh_per_60s": power * WINDOW_S / 3600,
                    "note": note,
                }
            )
    ref = {r["current_m_s"]: r for r in rows if r["drag_model"].startswith("HoloOcean")}
    for r in rows:
        base = ref.get(r["current_m_s"])
        if r.get("propulsion_power_W") is not None and base and base.get("propulsion_power_W"):
            r["ratio_to_holoocean"] = r["propulsion_power_W"] / base["propulsion_power_W"]
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/final/sensitivity.json"
    )
    args = parser.parse_args(argv)
    registry = default_registry()
    out = {
        "voltage_V": VOLTAGE_V,
        "native_clamp_N": CLAMP_N,
        "window_s": WINDOW_S,
        "part1_drag_model": part1(registry),
        "scope": "steady station keeping in head-on current, simulator-exact 8T layout; "
        "electrical model T200 static tables (grade B); no model is a validated BlueROV2 Heavy",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    for r in out["part1_drag_model"]:
        p = r.get("propulsion_power_W")
        print(
            f"{r['drag_model'][:30]:30s} U={r['current_m_s']:.1f} F={r['surge_force_N'] if r['surge_force_N'] is None else round(r['surge_force_N'], 1)} "
            f"P={'-' if p is None else round(p, 1)} W ratio={round(r.get('ratio_to_holoocean', float('nan')), 3)} {r['note']}"
        )


if __name__ == "__main__":
    main()
