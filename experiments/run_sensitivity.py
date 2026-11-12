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

Part 2 (acoustic modem settings, review D-01/A-05). The communication energy of the final
cross-layer runs is recomputed from the recorded per-state durations for every published
S2C M 18/34 transmit setting (2.8 / 8 / 35 / 55 W), for the RS-232 and the Ethernet interface
(+0.5 W in every powered state) and for two airtime bases: the DESERT PHY as simulated and the
device bitrate (13.9 kbit/s, payload bits only, the saved TX time moved to LISTEN). The share is
taken against the run's terminal energy with the communication term replaced; the change in
battery loss is neglected (first order) and DC/DC conversion from the 24 V modem supply is not
modelled (no published converter efficiency).

Part 3 (allocator). Steady drag wrenches (HoloOcean literals; head-on, sway and oblique 45 deg
currents of 0.5 m/s) are allocated on each final layout with the three implemented methods
(pseudoinverse, redistributed least squares, power-weighted IRLS on the T200 tables) and
converted to electrical power. Component one-at-a-time ranges are reported by the EnergyReport
interval of each final run (holoenergy.uncertainty), not here.

Part 4 (drag anisotropy, review B-04). HoloOcean applies one isotropic C_D A. The registry's
identified BlueROV2 Heavy damping (von Benzon et al. 2022) is anisotropic (Y_vv/X_uu = 1.54,
Z_ww/X_uu = 1.35). Steady station keeping at 0.2 and 0.5 m/s (inside the identified range) is
allocated on every final layout under both force laws to check whether the layout and current
direction ranking found with HoloOcean drag survives; the identified model is used only as a
published alternative, not as a validated description of the simulated body.

    uv run python experiments/run_sensitivity.py [--crosslayer experiments/results/final/crosslayer.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from importlib.resources import files
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_offline_campaign import (  # noqa: E402
    HOLOOCEAN_DRAG,
    NATIVE,
    T200,
    VON_BENZON,
    layouts,
    t200_bounds,
    t200_power,
)

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


S2C_TX = (
    "evologics_s2cm_18_34.tx_1000m",
    "evologics_s2cm_18_34.tx_2000m",
    "evologics_s2cm_18_34.tx_3500m",
    "evologics_s2cm_18_34.tx_max",
)
S2C_RX = "evologics_s2cm_18_34.rx"
S2C_ETHERNET = "evologics_s2cm_18_34.ethernet_interface_adder"
S2C_BITRATE = "evologics_s2cm_18_34.bitrate"


def part2(registry, crosslayer_path):
    if not crosslayer_path.exists():
        return {"skipped": f"{crosslayer_path} not found (run run_crosslayer.py first)"}
    results = json.loads(crosslayer_path.read_text(encoding="utf-8")).get("results", {})
    rx_w = registry.get(S2C_RX).si()
    eth_w = registry.get(S2C_ETHERNET).si()
    device_bps = registry.get(S2C_BITRATE).si()
    rows = []
    for strategy, res in results.items():
        if "error" in res:
            continue
        interfaces = (res.get("network") or {}).get("vehicle_metrics", {}).get("interfaces", {})
        acoustic = [i for i in interfaces.values() if i.get("medium") == "acoustic"]
        if not acoustic:
            continue
        mission = res["mission"]
        rest = mission["terminal_Wh"] - mission["communications_Wh"]
        for iface in acoustic:
            dur = iface["state_duration_s"]
            for airtime in ("DESERT PHY as simulated", "device bitrate (payload bits only)"):
                simulated = airtime.startswith("DESERT")
                tx_s = dur["TX"] if simulated else iface["tx_bits"] / device_bps
                listen_s = dur["LISTEN"] + (dur["TX"] - tx_s)
                for interface, extra in (("RS-232", 0.0), ("Ethernet", eth_w)):
                    for record in S2C_TX:
                        tx_w = registry.get(record).si()
                        energy_Wh = (
                            (tx_w + extra) * tx_s + (rx_w + extra) * (dur["RX"] + listen_s)
                        ) / 3600
                        rows.append(
                            {
                                "strategy": strategy,
                                "airtime": airtime,
                                "interface": interface,
                                "tx_record": record,
                                "tx_W": tx_w,
                                "rx_listen_W": rx_w + extra,
                                "tx_s": tx_s,
                                "rx_listen_s": dur["RX"] + listen_s,
                                "communication_Wh": energy_Wh,
                                "share_of_terminal": energy_Wh / (rest + energy_Wh),
                                "as_simulated": simulated
                                and interface == "RS-232"
                                and record == S2C_TX[0],
                            }
                        )
    shares = [r["share_of_terminal"] for r in rows]
    return {
        "rows": rows,
        "share_min": min(shares) if shares else None,
        "share_max": max(shares) if shares else None,
        "notes": [
            "RX/LISTEN is the published upper bound (<0.8 W, RS-232); no lower value is assumed",
            "tx_max (55 W) is an upper bound ('max. available')",
            "battery-loss change and 24 V DC/DC conversion are not modelled",
        ],
    }


def part3(voltage=VOLTAGE_V, current=0.5):
    k = 0.5 * HOLOOCEAN_DRAG["rho"] * HOLOOCEAN_DRAG["cd"] * HOLOOCEAN_DRAG["area"]
    f = k * current * current
    s = 2**-0.5
    cases = {
        "head-on": [f, 0, 0, 0, 0, 0],
        "sway": [0, f, 0, 0, 0, 0],
        "oblique 45 deg": [f * s, f * s, 0, 0, 0, 0],
    }
    final = ("L8-HV", "L6-STD", "L4-H45", "L4-2H2V", "L8-VEC30")
    rows = []
    for name, (acts, _desc, grade) in layouts().items():
        if name not in final:
            continue
        lo, hi = t200_bounds(len(acts), voltage)
        power_functions = [
            (lambda x, a=a, b=b: T200.power(min(max(x, a), b), voltage))
            for a, b in zip(lo, hi, strict=True)
        ]
        for case, tau in cases.items():
            per_method = {}
            for method in ThrustAllocator.METHODS:
                result = ThrustAllocator(acts, method=method).allocate(
                    tau,
                    lower=lo,
                    upper=hi,
                    power_functions=power_functions if method == "power_irls" else None,
                )
                per_method[method] = {
                    "propulsion_power_W": t200_power(result.forces_N, voltage),
                    "residual_N": result.residual_norm,
                    "feasible": result.residual_norm < 1e-6,
                }
            ref = per_method["redistributed"]["propulsion_power_W"]
            for method, r in per_method.items():
                rows.append(
                    {
                        "layout": name,
                        "geometry_grade": grade,
                        "case": case,
                        "current_m_s": current,
                        "method": method,
                        **r,
                        "ratio_to_redistributed": r["propulsion_power_W"] / ref if ref else None,
                    }
                )
    return rows


FINAL_LAYOUTS = ("L8-HV", "L6-STD", "L4-H45", "L4-2H2V", "L8-VEC30")


ANGLE_LAYOUTS = ("L8-HV-a30", "L8-HV-a60")  # EXP4 horizontal-angle variants


def part4(voltage=VOLTAGE_V, currents=(0.2, 0.5)):
    k = 0.5 * HOLOOCEAN_DRAG["rho"] * HOLOOCEAN_DRAG["cd"] * HOLOOCEAN_DRAG["area"]
    vb = VON_BENZON

    def isotropic(v):
        # HoloOcean: F = 1/2 rho Cd A |v| v (vector law, one C_D A for every direction).
        speed = sum(c * c for c in v) ** 0.5
        return [k * speed * c for c in v]

    def anisotropic(v):
        # von Benzon et al. 2022: diagonal damping, per body axis, no cross terms.
        out = []
        for c, (lin, quad) in zip(
            v, (("X_u", "X_uu"), ("Y_v", "Y_vv"), ("Z_w", "Z_ww")), strict=True
        ):
            out.append(vb[f"{lin}_N_s_per_m"] * c + vb[f"{quad}_N_s2_per_m2"] * abs(c) * c)
        return out

    s = 2**-0.5
    rows = []
    for law_name, law in (
        ("HoloOcean isotropic", isotropic),
        ("von Benzon 2022 anisotropic", anisotropic),
    ):
        for u in currents:
            cases = {
                case: [*law(v), 0, 0, 0]
                for case, v in (
                    ("head-on", (u, 0, 0)),
                    ("sway", (0, u, 0)),
                    ("oblique 45 deg", (u * s, u * s, 0)),
                    ("heave", (0, 0, u)),
                )
            }
            for name, (acts, _desc, grade) in layouts().items():
                if name not in FINAL_LAYOUTS + ANGLE_LAYOUTS:
                    continue
                lo, hi = t200_bounds(len(acts), voltage)
                allocator = ThrustAllocator(acts)
                for case, tau in cases.items():
                    result = allocator.allocate(tau, lower=lo, upper=hi)
                    rows.append(
                        {
                            "drag_law": law_name,
                            "current_m_s": u,
                            "case": case,
                            "layout": name,
                            "geometry_grade": grade,
                            "required_force_N": sum(x * x for x in tau[:3]) ** 0.5,
                            "feasible": result.residual_norm < 1e-6,
                            "residual_N": result.residual_norm,
                            "propulsion_power_W": t200_power(result.forces_N, voltage),
                        }
                    )
    # Rank layouts per (law, current, case) among feasible ones; compare rankings across laws.
    rankings = {}
    for r in rows:
        if r["feasible"]:
            key = (r["drag_law"], r["current_m_s"], r["case"])
            rankings.setdefault(key, []).append((r["propulsion_power_W"], r["layout"]))

    def tiered(entries, rel=1e-6):
        # Layouts whose power differs by less than rel form one tier (e.g. layouts that use
        # the same four horizontal thrusters); a ranking is a list of tiers.
        tiers = []
        for power, name in sorted(entries):
            if tiers and abs(power - tiers[-1][0]) <= rel * max(abs(power), 1.0):
                tiers[-1][1].append(name)
            else:
                tiers.append((power, [name]))
        return [sorted(names) for _, names in tiers]

    order = {k: tiered(v) for k, v in rankings.items()}
    comparison = []
    for u in currents:
        for case in ("head-on", "sway", "oblique 45 deg", "heave"):
            iso = order.get(("HoloOcean isotropic", u, case))
            ani = order.get(("von Benzon 2022 anisotropic", u, case))
            comparison.append(
                {
                    "current_m_s": u,
                    "case": case,
                    "ranking_isotropic": iso,
                    "ranking_anisotropic": ani,
                    "same_ranking": iso == ani,
                }
            )
    # Direction dependence per layout: sway / head-on power ratio under each law.
    power = {
        (r["drag_law"], r["current_m_s"], r["layout"], r["case"]): r["propulsion_power_W"]
        for r in rows
        if r["feasible"]
    }
    direction = []
    for u in currents:
        for name in FINAL_LAYOUTS + ANGLE_LAYOUTS:
            entry = {"current_m_s": u, "layout": name}
            for law in ("HoloOcean isotropic", "von Benzon 2022 anisotropic"):
                head, sway = power.get((law, u, name, "head-on")), power.get((law, u, name, "sway"))
                entry[f"sway_over_head_on {law}"] = sway / head if head and sway else None
            direction.append(entry)
    return {"rows": rows, "ranking_comparison": comparison, "direction_ratio": direction}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--output", type=Path, default=ROOT / "experiments/results/final/sensitivity.json"
    )
    parser.add_argument(
        "--crosslayer", type=Path, default=ROOT / "experiments/results/final/crosslayer.json"
    )
    args = parser.parse_args(argv)
    registry = default_registry()
    out = {
        "voltage_V": VOLTAGE_V,
        "native_clamp_N": CLAMP_N,
        "window_s": WINDOW_S,
        "part1_drag_model": part1(registry),
        "part2_acoustic_modem": part2(registry, args.crosslayer),
        "part3_allocator": part3(),
        "part4_drag_anisotropy": part4(),
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
    p2 = out["part2_acoustic_modem"]
    if "rows" in p2:
        print(f"acoustic share range {p2['share_min']:.4f}-{p2['share_max']:.4f}")
    else:
        print(p2["skipped"])
    for r in out["part3_allocator"]:
        print(
            f"{r['layout']:9s} {r['case']:15s} {r['method']:13s} "
            f"P={r['propulsion_power_W']:7.2f} W ratio={r['ratio_to_redistributed'] or float('nan'):.4f} "
            f"res={r['residual_N']:.1e}"
        )
    for c in out["part4_drag_anisotropy"]["ranking_comparison"]:
        print(
            f"U={c['current_m_s']} {c['case']:15s} same={c['same_ranking']} "
            f"iso={c['ranking_isotropic']} ani={c['ranking_anisotropic']}"
        )
    for d in out["part4_drag_anisotropy"]["direction_ratio"]:
        print("dir", d)


if __name__ == "__main__":
    main()
