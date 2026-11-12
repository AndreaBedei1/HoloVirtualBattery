"""HoloEnergy v0.2 offline experiment campaign (no simulator is launched).

Inputs are the archived closed-loop HoloOcean 2.3.0 traces recorded at 100 Hz on the
drag-verified (patched) backend, decimated to 0.1 s in the archive
(sources/verified_backend/energy_patched).  Each trace stores the 8 applied BlueROV2
thruster forces, bus voltage and mission phase.  Replays are valid for quantities that
do not feed back into the dynamics (actuator layout electrical cost for the *same body
wrench history*, electrical payload, battery), never for tracking performance.

Experiments
  E0  replay fidelity: native 8T energy from the decimated archive vs the archived
      100 Hz summary (quantifies the decimation error of every replay below)
  E1  actuator layouts 4/6/8 and horizontal-thruster orientation sweep (wrench replay)
  E2  payload / compute suites on the BlueROV2 Heavy profile (EnergyAwareEnv replay)
  E3  environment: current speed vs propulsion / total energy (from E2 base suite)
  E4  external comparison: HoloOcean BlueROV2 drag vs measured restrained-ROV loads
      (Gabl et al. 2021) and the resulting station-keeping electrical power
  E5  baselines and ablations (constant power, speed-cubic, L0 vs L1, no payload)

Usage:  python experiments/run_offline_campaign.py [--output experiments/results/offline]
"""

import argparse
import csv
import gzip
import json
import math
import sys
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from holoenergy import EnergyAwareEnv, __version__  # noqa: E402
from holoenergy.allocation import (  # noqa: E402
    ActuatorGeometry,
    ThrustAllocator,
    direction_from_angles,
)
from holoenergy.catalog import vehicle_config  # noqa: E402
from holoenergy.config import load_config  # noqa: E402
from holoenergy.evidence import default_registry  # noqa: E402
from holoenergy.models.actuator import make_actuator  # noqa: E402
from holoenergy.provenance import file_hash, git_state  # noqa: E402

TRACES = ROOT / "sources" / "verified_backend" / "energy_patched"
SCENARIOS = [
    "station_0",
    "station_0.2",
    "station_0.5",
    "station_0.8",
    "mission_0",
    "mission_0.2",
    "mission_0.4",
]
AGENTS = json.loads((ROOT / "holoenergy/profiles/holoocean/agents_2.3.0.json").read_text())
NATIVE = [
    ActuatorGeometry(f"N{a['backend_index']}", tuple(a["position_m"]), tuple(a["direction"]))
    for a in AGENTS["agents"]["BlueROV2"]["actuators"]
]
NATIVE_B = ThrustAllocator(NATIVE).B
REGISTRY = default_registry()


def _value(record_id):
    return REGISTRY.get(record_id).si()


def _dataset(record_id):
    """Rows/coefficients of a dataset-backed registry record (packaged JSON)."""
    from importlib.resources import files

    path = REGISTRY.get(record_id).dataset["path"]
    return json.loads(files("holoenergy").joinpath(path).read_text(encoding="utf-8"))


# Every scientific constant comes from the evidence registry (single source of truth).
HOLOOCEAN_DRAG = {
    "rho": _value("holoocean_bluerov2.water_density"),
    "cd": _value("holoocean_bluerov2.drag_coefficient"),
    "area": _value("holoocean_bluerov2.drag_area"),
}
GABL_RECORD = "bluerov2_standard.restrained_inline_load_head_on"
GABL_2021 = [
    (row["speed_m_s"], row["force_N"])
    for row in _dataset(GABL_RECORD)["rows"]
    if row["speed_m_s"] > 0
]
GABL_ZERO_RESIDUAL_N = abs(
    next(r["force_N"] for r in _dataset(GABL_RECORD)["rows"] if r["speed_m_s"] == 0)
)
VON_BENZON = _dataset("bluerov2_heavy.translational_damping_identified")["coefficients"]
VON_BENZON_MAX_SPEED = 0.72  # identified range (von Benzon et al. 2022, Table 4)
HOLOOCEAN_MASS = _value("holoocean_bluerov2.mass")
HOLOOCEAN_DAMPING = _value("holoocean_bluerov2.linear_damping")


def t200():
    cfg = load_config(data=vehicle_config("bluerov2-heavy"))
    spec = cfg["propulsion"].get("thruster") or cfg["propulsion"]["thrusters"][0]
    return make_actuator(spec)


T200 = t200()


def load_trace(name):
    rows = [json.loads(line) for line in gzip.open(TRACES / f"{name}.trace.jsonl.gz", "rt")]
    times = [r["t_s"] for r in rows]
    dts = [times[0]] + [b - a for a, b in zip(times, times[1:], strict=False)]
    summary = json.loads((TRACES / f"{name}.jsonl.summary.json").read_text())
    return rows, dts, summary


# ------------------------------------------------------------------ layouts (E1)
S = 1 / math.sqrt(2)
HORIZ = [
    (0.1562, -0.0988, 0.0),
    (0.1562, 0.0988, 0.0),
    (-0.1562, 0.0988, 0.0),
    (-0.1562, -0.0988, 0.0),
]
VERT8 = [
    (0.12, -0.2181, 0.0809),
    (0.12, 0.2181, 0.0809),
    (-0.12, 0.2181, 0.0809),
    (-0.12, -0.2181, 0.0809),
]


def horizontals(alpha_deg, elevation_deg=(0, 0, 0, 0)):
    """Vectored horizontals: front pair point forward-inward at +/-alpha, rear pair likewise.

    alpha=45 deg reproduces the HoloOcean/BlueROV2 directions (1,+1)/sqrt2, (1,-1)/sqrt2.
    """
    az = [alpha_deg, -alpha_deg, alpha_deg, -alpha_deg]
    return [
        ActuatorGeometry(f"H{i + 1}", p, direction_from_angles(azimuth=a, elevation=e))
        for i, (p, a, e) in enumerate(zip(HORIZ, az, elevation_deg, strict=True))
    ]


def layouts():
    result = {
        "L8-HV": (
            horizontals(45)
            + [ActuatorGeometry(f"V{i + 1}", p, (0, 0, 1)) for i, p in enumerate(VERT8)],
            "BlueROV2 Heavy, HoloOcean 2.3.0 geometry (exact for the simulator)",
            "A",
        ),
        "L6-STD": (
            horizontals(45)
            + [
                ActuatorGeometry("V1", (0, -0.1105, 0.0809), (0, 0, 1)),
                ActuatorGeometry("V2", (0, 0.1105, 0.0809), (0, 0, 1)),
            ],
            "BlueROV2 Standard: role-exact, vertical y from the 2D drawing, x proxy",
            "C",
        ),
        "L4-H45": (
            horizontals(45),
            "4 vectored horizontals only (layout class of Delgado-P 2026)",
            "C",
        ),
        "L4-2H2V": (
            [
                ActuatorGeometry("H1", (-0.1562, 0.0988, 0.0), (1, 0, 0)),
                ActuatorGeometry("H2", (-0.1562, -0.0988, 0.0), (1, 0, 0)),
                ActuatorGeometry("V1", (0.12, 0.0, 0.0809), (0, 0, 1)),
                ActuatorGeometry("V2", (-0.12, 0.0, 0.0809), (0, 0, 1)),
            ],
            "2 stern horizontals + 2 centreline verticals (benchmark design)",
            "D",
        ),
        "L8-VEC30": (
            horizontals(45, (20, -20, -20, 20))
            + [
                ActuatorGeometry(f"V{i + 1}", p, direction_from_angles(azimuth=az, elevation=60))
                for i, (p, az) in enumerate(zip(VERT8, (-90, 90, 90, -90), strict=True))
            ],
            "8 thrusters, 3D-vectored (horizontals +/-20 deg, verticals tilted 30 deg outward)",
            "D",
        ),
    }
    for alpha in (30, 35, 40, 50, 55, 60):
        result[f"L8-HV-a{alpha}"] = (
            horizontals(alpha)
            + [ActuatorGeometry(f"V{i + 1}", p, (0, 0, 1)) for i, p in enumerate(VERT8)],
            f"Heavy with horizontal thrusters at {alpha} deg (45 deg = BlueROV2)",
            "D",
        )
    return result


def directional_study(out, voltage=15.5):
    """E1b: steady-state wrench cases from HoloOcean's isotropic SI drag equation.

    Station keeping in a horizontal current from heading angle beta needs the body force
    opposing F = 1/2 rho Cd A U^2 along the current; a vertical transit at speed w needs
    the same law along z (neutral buoyancy, Perfect=true).  Moments are zero because the
    drag acts at the centre of mass in the backend.  Steady state only, no dynamics.
    """
    k = 0.5 * HOLOOCEAN_DRAG["rho"] * HOLOOCEAN_DRAG["cd"] * HOLOOCEAN_DRAG["area"]
    cases = []
    for u in (0.2, 0.4):
        for beta in (0, 45, 90):
            f = k * u * u
            b = math.radians(beta)
            cases.append(
                (f"current {u} m/s from {beta} deg", [f * math.cos(b), f * math.sin(b), 0, 0, 0, 0])
            )
    for w in (0.1, 0.2):
        cases.append((f"vertical transit {w} m/s", [0, 0, k * w * w, 0, 0, 0]))
    cases.append(
        (
            "current 0.3 m/s from 45 deg + vertical 0.1 m/s",
            [k * 0.09 * S, k * 0.09 * S, k * 0.01, 0, 0, 0],
        )
    )
    rows = []
    for layout, (acts, _desc, grade) in layouts().items():
        alloc = ThrustAllocator(acts)
        lo, hi = t200_bounds(len(acts), voltage)
        for label, tau in cases:
            res = alloc.allocate(tau, lower=lo, upper=hi)
            rows.append(
                {
                    "layout": layout,
                    "case": label,
                    "geometry_grade": grade,
                    "required_force_N": float(np.linalg.norm(tau[:3])),
                    "propulsion_power_W": t200_power(res.forces_N, voltage),
                    "peak_thruster_force_N": max(abs(f) for f in res.forces_N),
                    "residual_N": res.residual_norm,
                    "feasible": res.residual_norm < 1e-6,
                    "saturated": ";".join(res.saturated),
                }
            )
        for axis, vec in (
            ("surge", [1, 0, 0, 0, 0, 0]),
            ("sway", [0, 1, 0, 0, 0, 0]),
            ("heave", [0, 0, 1, 0, 0, 0]),
        ):
            fmax = alloc.max_wrench_along(vec, lo, hi)
            rows.append(
                {
                    "layout": layout,
                    "case": f"max steady {axis} force",
                    "geometry_grade": grade,
                    "required_force_N": fmax,
                    "max_holdable_current_m_s": math.sqrt(fmax / k)
                    if axis != "heave" and math.isfinite(fmax)
                    else None,
                    "max_vertical_speed_m_s": math.sqrt(fmax / k)
                    if axis == "heave" and math.isfinite(fmax)
                    else None,
                }
            )
    write_csv(out / "E1b_directional.csv", rows)
    return rows


def t200_bounds(n, voltage):
    return (
        np.full(n, -T200.max_force(voltage, "reverse")),
        np.full(n, T200.max_force(voltage, "forward")),
    )


def t200_power(forces, voltage):
    total = 0.0
    for f in forces:
        cap = T200.max_force(voltage, "forward" if f > 0 else "reverse")
        total += T200.power(max(-cap, min(cap, f)), voltage) if f else 0.0
    return total


def layout_study(out):
    rows = []
    defs = layouts()
    for name in SCENARIOS:
        records, dts, _ = load_trace(name)
        taus = [NATIVE_B @ np.array(r["applied_N"]) for r in records]
        for layout, (acts, desc, grade) in defs.items():
            for method in ("redistributed", "pseudoinverse", "power_irls"):
                if method != "redistributed" and layout not in ("L8-HV", "L6-STD"):
                    continue
                alloc = ThrustAllocator(acts, method=method)
                energy = peak_power = peak_force = 0.0
                infeasible_time = residual_int = 0.0
                for r, dt, tau in zip(records, dts, taus, strict=True):
                    v = r["voltage_V"]
                    lo, hi = t200_bounds(len(acts), v)
                    pf = None
                    if method == "power_irls":
                        pf = [
                            (lambda f, v=v: T200.power(min(f, T200.max_force(v, "forward")), v))
                        ] * len(acts)
                    res = alloc.allocate(tau, lower=lo, upper=hi, power_functions=pf)
                    p = t200_power(res.forces_N, v)
                    energy += p * dt
                    peak_power = max(peak_power, p)
                    peak_force = max(peak_force, max(abs(f) for f in res.forces_N))
                    tol = max(0.5, 0.01 * float(np.linalg.norm(tau)))
                    if res.residual_norm > tol:
                        infeasible_time += dt
                    residual_int += res.residual_norm * dt
                duration = sum(dts)
                rows.append(
                    {
                        "scenario": name,
                        "layout": layout,
                        "allocation": method,
                        "geometry_grade": grade,
                        "description": desc,
                        "actuators": len(acts),
                        "rank": alloc.rank,
                        "duration_s": duration,
                        "propulsion_energy_Wh": energy / 3600,
                        "peak_propulsion_power_W": peak_power,
                        "peak_thruster_force_N": peak_force,
                        "infeasible_time_fraction": infeasible_time / duration,
                        "mean_wrench_residual_N": residual_int / duration,
                    }
                )
    write_csv(out / "E1_layouts.csv", rows)
    return rows


def replay_fidelity(out):
    """E0: archived 100 Hz propulsion energy vs native-layout replay of the 10 Hz archive."""
    rows = []
    for name in SCENARIOS:
        records, dts, summary = load_trace(name)
        energy = (
            sum(sum(r["thruster_power_W"]) * dt for r, dt in zip(records, dts, strict=True)) / 3600
        )
        replay = (
            sum(
                t200_power(r["applied_N"], r["voltage_V"]) * dt
                for r, dt in zip(records, dts, strict=True)
            )
            / 3600
        )
        ref = summary["category_energy_Wh"]["propulsion"]
        rows.append(
            {
                "scenario": name,
                "archived_100Hz_propulsion_Wh": ref,
                "decimated_trace_power_integral_Wh": energy,
                "native_replay_Wh": replay,
                "decimation_relative_error": (energy - ref) / ref if ref else None,
                "model_replay_vs_trace_relative": (replay - energy) / energy if energy else None,
            }
        )
    write_csv(out / "E0_replay_fidelity.csv", rows)
    return rows


# ------------------------------------------------------------------ payload (E2/E3)
SUITES = {
    "S0-propulsion-only": {"keep": [], "add": []},
    "S1-avionics": {"keep": ["navigator", "companion_computer"], "add": [], "rpi": "IDLE"},
    "S2-camera": {"keep": ["navigator", "companion_computer", "camera"], "add": [], "rpi": "VIDEO"},
    "S3-camera-sonar": {
        "keep": ["navigator", "companion_computer", "camera"],
        "add": ["bluerobotics-ping360"],
        "rpi": "VIDEO",
    },
    "S4-dvl-sonar": {
        "keep": ["navigator", "companion_computer"],
        "add": ["waterlinked-dvl-a50", "bluerobotics-ping360"],
        "rpi": "IDLE",
    },
    "S5-inspection": {
        "keep": ["navigator", "companion_computer"],
        "add": [
            "bluerobotics-4k-camera",
            "tritech-gemini-720is",
            "waterlinked-dvl-a50",
            "bluerobotics-lumen",
            "bluerobotics-lumen#2",
        ],
        "rpi": "VIDEO",
        "lights_on": True,
    },
    "S6-ai-vision": {
        "keep": ["navigator", "companion_computer", "camera"],
        "add": ["jetson-orin-nx-16gb"],
        "rpi": "VIDEO",
    },
}


class ReplayBackend:
    def __init__(self):
        self.energy_action_contract = None

    def step(self, action):
        return {}

    def close(self):
        pass


def suite_components(suite):
    """Component entries (pre-load configuration data) of a named sensor/compute suite."""
    base = load_config(data=vehicle_config("bluerov2-heavy"))
    spec = SUITES[suite]
    comps = [c for c in base["components"] if c["name"] in spec["keep"]]
    for c in comps:
        if c["name"] == "companion_computer":
            c["initial_state"] = spec.get("rpi", "IDLE")
    from holoenergy.catalog import profile_reference

    for item in spec["add"]:
        key, _, idx = item.partition("#")
        entry = {"profile": profile_reference(key, "component")}
        if idx:
            entry["name"] = f"{key}_{idx}"
        if key == "bluerobotics-lumen":
            entry["initial_state"] = "ACTIVE" if spec.get("lights_on") else "OFF"
            entry.setdefault("name", "light_1")
        comps.append(entry)
        if key == "tritech-gemini-720is":
            # Review A-04: 19-74 V supply vs the 12-16.8 V bus. The step-up converter is a
            # declared gap (unconfigured, excluded from the bus), not an assumed efficiency.
            comps.append(
                {
                    "name": "imaging_sonar_step_up_converter",
                    "category": "auxiliaries",
                    "status": "unconfigured",
                    "states": {"ACTIVE": None},
                    "notes": "Gemini 720is needs 19-74 Vdc; converter efficiency unpublished",
                }
            )
    return comps


def suite_config(suite, *, fidelity="L1", battery_r=None):
    data = {
        "profile": "package:vehicles/bluerov2_heavy_holoocean.yaml",
        "components": suite_components(suite),
        "simulation": {"dt_s": 0.1, "expected_agent_type": "BlueROV2", "control_scheme": 0},
        "power_manager": {"apply_derating_to_actions": False},
        "logging": {"enabled": False},
    }
    config = load_config(data=data)
    if battery_r is not None:
        config["battery"]["internal_resistance_ohm"] = battery_r
    if fidelity == "L0":
        from holoenergy.config import with_fidelity

        config = with_fidelity(config, "L0")
    return config


def replay(config, name):
    records, dts, _ = load_trace(name)
    env = EnergyAwareEnv(ReplayBackend(), config=config)
    limited = 0
    for r, dt in zip(records, dts, strict=True):
        if abs(dt - 0.1) > 1e-6:  # the first archived record covers 0.01 s only
            continue
        env.energy.mark_phase(r["phase"])
        row = env.step(r["applied_N"])["Energy"]
        limited += row["derating_factor"] < 1 - 1e-9
    report = env.energy.report()
    env.close()
    return report, limited


def payload_study(out):
    rows = []
    for name in ("station_0", "station_0.5", "mission_0.4"):
        for suite in SUITES:
            report, limited = replay(suite_config(suite), name)
            d = report.to_dict()
            ev = d["evidence"]
            rows.append(
                {
                    "scenario": name,
                    "suite": suite,
                    "duration_s": d["duration_s"],
                    "terminal_energy_Wh": d["terminal_energy_Wh"],
                    "total_ocv_work_Wh": d["total_ocv_work_Wh"],
                    **{f"E_{k}_Wh": v for k, v in d["category_energy_Wh"].items()},
                    "soc_loss_percent": 100 * d["soc_loss"],
                    "peak_current_A": d["peak_current_A"],
                    "grade_A_percent": ev["share_percent"]["A"],
                    "grade_B_percent": ev["share_percent"]["B"],
                    "grade_C_percent": ev["share_percent"]["C"],
                    "grade_D_percent": ev["share_percent"]["D"],
                    "upper_bound_percent": ev["upper_bound_share_percent"],
                    "interval_low_Wh": None
                    if d["intervals"]["terminal_energy_Wh"]["open_low"]
                    else d["intervals"]["terminal_energy_Wh"]["low"],
                    "interval_high_Wh": None
                    if d["intervals"]["terminal_energy_Wh"]["open_high"]
                    else d["intervals"]["terminal_energy_Wh"]["high"],
                    "power_limited_ticks": limited,
                    "mean_power_W": 3600 * d["terminal_energy_Wh"] / d["duration_s"],
                }
            )
    write_csv(out / "E2_payload_suites.csv", rows)
    env_rows = []
    for name in SCENARIOS:
        report, limited = replay(suite_config("S2-camera"), name)
        d = report.to_dict()
        env_rows.append(
            {
                "scenario": name,
                "current_m_s": float(name.split("_")[1]),
                "kind": name.split("_")[0],
                "duration_s": d["duration_s"],
                "propulsion_Wh": d["category_energy_Wh"]["propulsion"],
                "terminal_energy_Wh": d["terminal_energy_Wh"],
                "battery_losses_Wh": d["category_energy_Wh"]["battery_losses"],
                "mean_power_W": 3600 * d["terminal_energy_Wh"] / d["duration_s"],
                "soc_loss_percent": 100 * d["soc_loss"],
                "power_limited_ticks": limited,
            }
        )
    write_csv(out / "E3_environment.csv", env_rows)
    return rows, env_rows


# ------------------------------------------------------------------ external (E4)
def external_drag(out):
    rows = []
    std = ThrustAllocator(layouts()["L6-STD"][0])
    heavy = ThrustAllocator(layouts()["L8-HV"][0])
    voltage = 15.5
    for u, measured in GABL_2021 + [(0.5, None)]:
        ho = 0.5 * HOLOOCEAN_DRAG["rho"] * HOLOOCEAN_DRAG["cd"] * HOLOOCEAN_DRAG["area"] * u * u
        identified = VON_BENZON["X_u_N_s_per_m"] * u + VON_BENZON["X_uu_N_s2_per_m2"] * u * u
        row = {
            "current_m_s": u,
            "measured_surge_load_N": measured,
            "holoocean_drag_N": ho,
            "ratio_holoocean_to_measured": ho / measured if measured else None,
            # A load of the order of the still-water zero residual cannot support a ratio.
            "measured_above_zero_residual": None
            if measured is None
            else measured > 2 * GABL_ZERO_RESIDUAL_N,
            "von_benzon_identified_surge_N": identified,
            "ratio_holoocean_to_identified": ho / identified,
            "ratio_identified_to_measured": identified / measured if measured else None,
            # Like-for-like with a free-running, still-water identification: HoloOcean's
            # quadratic drag plus Unreal linear damping m c u acting on the body velocity.
            "holoocean_still_water_resistance_N": ho + HOLOOCEAN_MASS * HOLOOCEAN_DAMPING * u,
            "ratio_holoocean_still_water_to_identified": (
                ho + HOLOOCEAN_MASS * HOLOOCEAN_DAMPING * u
            )
            / identified,
            "within_identified_range": u <= VON_BENZON_MAX_SPEED,
        }
        for label, alloc in (("std", std), ("heavy", heavy)):
            n = alloc.n
            lo, hi = t200_bounds(n, voltage)
            for src, force in (("measured", measured), ("holoocean", ho)):
                if force is None:
                    row[f"P_{label}_{src}_W"] = None
                    continue
                res = alloc.allocate([force, 0, 0, 0, 0, 0], lower=lo, upper=hi)
                row[f"P_{label}_{src}_W"] = t200_power(res.forces_N, voltage)
                row[f"residual_{label}_{src}_N"] = res.residual_norm
        rows.append(row)
    # Backend consistency: archived patched station keeping surge wrench vs HoloOcean equation.
    checks = []
    for name in ("station_0.2", "station_0.5", "station_0.8"):
        records, dts, _ = load_trace(name)
        u = float(name.split("_")[1])
        steady = [NATIVE_B @ np.array(r["applied_N"]) for r in records if r["t_s"] > 10]
        fx = float(np.mean([abs(t[0]) for t in steady]))
        checks.append(
            {
                "scenario": name,
                "current_m_s": u,
                "mean_surge_wrench_N": fx,
                "holoocean_equation_N": 0.5
                * HOLOOCEAN_DRAG["rho"]
                * HOLOOCEAN_DRAG["cd"]
                * HOLOOCEAN_DRAG["area"]
                * u
                * u,
            }
        )
    write_csv(out / "E4_external_drag.csv", rows)
    write_csv(out / "E4_backend_consistency.csv", checks)
    return rows, checks


# ------------------------------------------------------------------ baselines/ablations (E5)
def baselines(out):
    rows = []
    # Speed-cubic baseline fitted on the calm-water mission (P_prop = k |v|^3).
    calm, dts, _ = load_trace("mission_0")
    num = sum(sum(r["thruster_power_W"]) * (r["speed_m_s"] ** 3) for r in calm)
    den = sum(r["speed_m_s"] ** 6 for r in calm)
    k = num / den if den else 0.0
    mean_calm = sum(sum(r["thruster_power_W"]) * dt for r, dt in zip(calm, dts, strict=True)) / sum(
        dts
    )
    for name in SCENARIOS:
        records, dts, _ = load_trace(name)
        ref = (
            sum(sum(r["thruster_power_W"]) * dt for r, dt in zip(records, dts, strict=True)) / 3600
        )
        cubic = sum(k * r["speed_m_s"] ** 3 * dt for r, dt in zip(records, dts, strict=True)) / 3600
        const = mean_calm * sum(dts) / 3600
        rows.append(
            {
                "scenario": name,
                "holoenergy_actuator_effort_Wh": ref,
                "speed_cubic_baseline_Wh": cubic,
                "constant_power_baseline_Wh": const,
                "speed_cubic_relative_error": (cubic - ref) / ref if ref else None,
                "constant_relative_error": (const - ref) / ref if ref else None,
                "fitted_k_W_s3_m3": k,
                "fit_scenario": "mission_0 (calm water)",
            }
        )
    write_csv(out / "E5_baselines.csv", rows)
    abl = []
    for name in ("station_0.5", "mission_0.4"):
        variants = {
            "L1 full (S2-camera)": suite_config("S2-camera"),
            "L1 no payload": suite_config("S0-propulsion-only"),
            "L1 R=0 (no voltage sag)": suite_config("S2-camera", battery_r=0.0),
            "L1 R=cell max (14.63 mOhm)": suite_config("S2-camera", battery_r=0.01463),
            "L0 ideal bucket": suite_config("S2-camera", fidelity="L0"),
        }
        for label, cfg in variants.items():
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                report, _ = replay(cfg, name)
            d = report.to_dict()
            abl.append(
                {
                    "scenario": name,
                    "variant": label,
                    "terminal_energy_Wh": d["terminal_energy_Wh"],
                    "total_ocv_work_Wh": d["total_ocv_work_Wh"],
                    "battery_losses_Wh": d["category_energy_Wh"]["battery_losses"],
                    "soc_loss_percent": 100 * d["soc_loss"],
                    "peak_current_A": d["peak_current_A"],
                    "minimum_voltage_V": d["minimum_voltage_V"],
                }
            )
    write_csv(out / "E5_ablations.csv", abl)
    return rows, abl


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", default=str(ROOT / "experiments" / "results" / "offline"))
    args = parser.parse_args(argv)
    out = Path(args.output)
    warnings.simplefilter("ignore", UserWarning)
    results = {
        "E0": replay_fidelity(out),
        "E1": layout_study(out),
        "E1b": directional_study(out),
        "E2_E3": payload_study(out),
        "E4": external_drag(out),
        "E5": baselines(out),
    }
    manifest = {
        "holoenergy_version": __version__,
        "git": git_state(),
        "evidence_registry_version": default_registry().version,
        "numpy": np.__version__,
        "inputs": {p.name: file_hash(p) for p in sorted(TRACES.glob("*.trace.jsonl.gz"))},
        "backend": "HoloOcean 2.3.0 drag-patched build, 100 Hz closed loop (archived); "
        "decimated to 0.1 s in the archive",
        "simulator_launched": False,
        "random_seed": None,
        "deterministic": True,
        "outputs": sorted(p.name for p in out.glob("*.csv")),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps(results, indent=1, default=str) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(manifest['outputs'])} CSV files to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
