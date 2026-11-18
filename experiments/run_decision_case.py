"""EXP11: evidence-aware decision case (review I-02).

Does parameter-level evidence change an engineering decision? Three decisions are evaluated on
the final results with physical decision rules, never with scores:

A. Imaging-sonar choice for the inspection payload (the final EXP6 mission, replayed from its
   100 Hz trace: payload power does not feed back into the dynamics when there is no derating).
   Rules: (i) ranking - X uses less energy than Y is supported only if the supported upper
   bound of X is below the supported lower bound of Y; (ii) feasibility - N inspection legs per
   charge, with E_leg <= (1 - reserve) * rated pack energy / N.
B. Communication technology on the same mission (acoustic vs optical link), from the recorded
   per-state durations of the cross-layer runs and the interval of each state's power record.
C. Thruster layout (L4-2H2V vs L8-HV in head-on current): does the propulsion ranking survive
   the published alternative hydrodynamics (EXP10 part 4) and the inflow bias of the static
   T200 tables (Lam et al. 2023)?

Scenario choices (grade D, declared): reserve 30 %, leg targets 40-100 per charge, inspection
phases stop/hold/yaw. Hypothetical converter efficiencies in part A are labelled as such; they
are what a measurement would have to show, not evidence.

    uv run python experiments/run_decision_case.py
"""

from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))
sys.path.insert(0, str(ROOT))

from run_final_experiments import INSPECTION_PHASES  # noqa: E402
from run_native_campaign import layout_config  # noqa: E402

from holoenergy import EnergyAwareEnv  # noqa: E402
from holoenergy.analysis.replay import ReplayBackend  # noqa: E402
from holoenergy.catalog import profile_reference  # noqa: E402
from holoenergy.decision import assess_energy_requirement, compare_energy  # noqa: E402
from holoenergy.evidence import default_registry  # noqa: E402

FINAL = ROOT / "experiments/results/final"
MISSION = "EXP6-S5-inspection-scheduled"
RESERVE = 0.30
LEGS = (40, 60, 80, 100)
HYPOTHETICAL_ETA = (0.80, 0.85, 0.90, 0.95)
# Propulsion range from the published alternatives (EXP10): surge resistance 0.11-1.29 x the
# HoloOcean value (part 1) times the T200 inflow factor up to 1.162 (part 5).
PROPULSION_RANGE = (0.11, 1.50)
PROPULSION_RANGE_SOURCE = "EXP10 parts 1 and 5 (published resistance x T200 inflow bias)"
SHARED_SCHEDULED = ("bluerobotics_4k_camera", "bluerobotics_lumen")

OCULUS = {
    "name": "imaging_sonar",
    "device": "blueprint_oculus_m750d",
    "category": "sensors",
    "simulation_sensor": "ImagingSonar",
    "relation": "representative",
    "active_is_upper_bound": True,
    "states": {"ACTIVE": {"evidence": "blueprint_oculus_m750d.power_range", "use": "value_max"}},
    "initial_state": "ACTIVE",
    "notes": "M/MT/MD family range 10-35 W; no M750d-specific figure (record relation representative)",
}


def variants(base_components):
    """Inspection payload with each sonar; everything else as in the final S5 suite."""

    def without_gemini(items):
        out = []
        for c in items:
            if c.get("device") == "tritech_gemini_720is" or "gemini" in str(c.get("profile", "")):
                continue
            if c.get("name") == "imaging_sonar_step_up_converter":
                continue
            out.append(copy.deepcopy(c))
        return out

    rest = without_gemini(base_components)
    return {
        "Gemini 720is (multibeam)": (copy.deepcopy(base_components), "tritech_gemini_720is"),
        "Oculus M750d (multibeam)": (rest + [copy.deepcopy(OCULUS)], "blueprint_oculus_m750d"),
        "Ping360 (scanning, lower capability)": (
            rest + [{"profile": profile_reference("bluerobotics-ping360", "component")}],
            "bluerobotics_ping360",
        ),
    }


def load_trace(label):
    summary = json.loads((FINAL / f"native/EXP6/{label}.summary.json").read_text(encoding="utf-8"))
    full = ROOT / "logs/final/full" / f"{label}.trace.jsonl.gz"
    expected = summary["traces"]["full_per_tick"]["content_sha256"]
    # The recorded SHA256 is of the decompressed JSONL content.
    if full.exists():
        content = gzip.decompress(full.read_bytes())
        if hashlib.sha256(content).hexdigest() == expected:
            rows = [json.loads(line) for line in content.decode("utf-8").splitlines() if line]
            return summary, rows, "100 Hz trace (content SHA256 verified)"
    raise SystemExit(f"{full} missing or hash mismatch: rerun {label} or restore the archive")


def replay(config, rows, scheduled):
    env = EnergyAwareEnv(ReplayBackend(config), config=config)
    names = {c["name"]: c for c in env.config.get("components", []) if c.get("device") in scheduled}
    phase = None
    for r in rows:
        if r["phase"] != phase:
            phase = r["phase"]
            env.energy.mark_phase(phase)
            for name, comp in names.items():
                on = comp.get("initial_state", "ACTIVE")
                on = "ACTIVE" if on == "OFF" else on
                env.set_payload_state(name, on if phase in INSPECTION_PHASES else "OFF")
        env.step(r["requested_wrench"])
    report = env.energy.report()
    env.close()
    return report


def part_a(registry):
    summary, rows, resolution = load_trace(MISSION)
    config, _ = layout_config("L8-HV", "direct", suite="S5-inspection")
    available = (1 - RESERVE) * registry.get("bluerobotics_4s_18ah.energy_nominal").si() / 3600
    out = {"mission": MISSION, "trace": resolution, "available_Wh": available, "configs": {}}
    reports = {}
    for name, (components, sonar) in variants(config["components"]).items():
        cfg = copy.deepcopy(config)
        cfg["components"] = components
        reports[name] = replay(cfg, rows, (*SHARED_SCHEDULED, sonar))
        out["configs"][name] = summarize_config(reports[name], available)
    gemini = out["configs"]["Gemini 720is (multibeam)"]
    out["replay_check"] = {
        "native_terminal_Wh": summary["metrics"]["terminal_Wh"],
        "replay_terminal_Wh": gemini["nominal_Wh"],
        "relative_difference": gemini["nominal_Wh"] / summary["metrics"]["terminal_Wh"] - 1,
    }
    out["ranking"] = [
        {
            "a": x,
            "b": y,
            "nominal_a_lower": reports[x].terminal_energy_Wh < reports[y].terminal_energy_Wh,
            **compare_energy(reports[x], reports[y]).to_dict(),
            "verdict_min_grade_A": compare_energy(reports[x], reports[y], min_grade="A").verdict,
        }
        for x in reports
        for y in reports
        if x < y
    ]
    return out


def summarize_config(report, available):
    t = report.intervals["terminal_energy_Wh"]
    actuators = set(report.evidence.get("actuator_grades", {}))
    rail = sum(
        sum(v.values())
        for d, v in report.device_state_energy_Wh.items()
        if d not in actuators and d != "hotel_constant"
    )
    blocking = [x for x in t["unknown_contributions"] if x != "conversion:payload"]
    row = {
        "nominal_Wh": t["nominal"],
        "open_high": t["open_high"],
        "unknown_contributions": t["unknown_contributions"],
        "open_typical_values": [
            f"{r['device']}.{r['state']}" for r in report.intervals.get("open_contributions", [])
        ]
        + [
            x
            for x in t["open_high"]
            if "." in x and not x.endswith(("supply_conversion", "unconfigured"))
        ],
        "upper_bound_energy_Wh": report.evidence["upper_bound_energy_Wh"],
        "warnings": [(w["kind"], w["subject"]) for w in report.evidence["scientific_warnings"]],
        "payload_rail_Wh": rail,
        "max_legs_nominal": int(available // t["nominal"]),
        "legs": {},
        "what_if": {
            "assumption": "typical values confirmed as upper bounds; payload rail efficiency "
            "measured at eta (hypothetical outcomes, not evidence); applied to every payload load "
            "(one rail is modelled, so pack-voltage loads are also scaled); the declared-unknown "
            "ESC standby and tether interface are not in this suite and are not bounded",
            "still_blocked_by": blocking,
            "eta": {},
        },
    }
    for legs in LEGS:
        strict = assess_energy_requirement(
            report,
            available / legs,
            dynamics_policy="strict",
            propulsion_factor_range=PROPULSION_RANGE,
            dynamics_source=PROPULSION_RANGE_SOURCE,
        )
        row.setdefault("legs_strict_dynamics", {})[legs] = strict.verdict
        a = assess_energy_requirement(report, available / legs)
        row["legs"][legs] = {
            "requirement_Wh": a.requirement_Wh,
            "verdict": a.verdict,
            "nominal_pass": a.nominal_pass,
            "supported_low_Wh": a.supported_low_Wh,
        }
    for eta in HYPOTHETICAL_ETA:
        high = None if blocking else t["nominal"] + rail * (1 / eta - 1)
        row["what_if"]["eta"][eta] = {
            "upper_Wh": high,
            "max_legs_certifiable": None if high is None else int(available // high),
        }
    return row


def part_c():
    """Layout choice: is "L4-2H2V needs less propulsion than L8-HV in head-on station keeping"
    supported under every defensible dynamics alternative, and is the layout feasible?"""
    runs = {
        r["label"]: r
        for r in json.loads((FINAL / "final_runs.json").read_text(encoding="utf-8"))["runs"]
    }
    sens = json.loads((FINAL / "sensitivity.json").read_text(encoding="utf-8"))
    p4 = {
        (r["drag_law"], r["current_m_s"], r["layout"], r["case"]): r
        for r in sens["part4_drag_anisotropy"]["rows"]
        if r["feasible"]
    }
    p5 = {(r["layout"], r["current_m_s"]): r for r in sens["part5_t200_inflow_bias"]["rows"]}
    out = []
    for u in (0.2, 0.5):
        tag = f"headon{u:g}"
        cases = {
            "HoloOcean native run (propulsion Wh)": (
                runs[f"EXP3-L4-2H2V-{tag}"]["propulsion_Wh"],
                runs[f"EXP3-L8-HV-{tag}"]["propulsion_Wh"],
            ),
        }
        for law in ("HoloOcean isotropic", "von Benzon 2022 anisotropic"):
            a, b = p4.get((law, u, "L4-2H2V", "head-on")), p4.get((law, u, "L8-HV", "head-on"))
            if a and b:
                cases[f"steady allocation, {law} (W)"] = (
                    a["propulsion_power_W"],
                    b["propulsion_power_W"],
                )
        a, b = p5.get(("L4-2H2V", u)), p5.get(("L8-HV", u))
        if a and b:
            cases["steady, HoloOcean drag + T200 inflow bias (W)"] = (
                a["inflow_corrected_power_W"],
                b["inflow_corrected_power_W"],
            )
        holds = {k: v[0] < v[1] for k, v in cases.items()}
        out.append(
            {
                "current_m_s": u,
                "claim": "L4-2H2V needs less propulsion than L8-HV (head-on station keeping)",
                "cases": {
                    k: {"L4-2H2V": v[0], "L8-HV": v[1], "holds": holds[k]} for k, v in cases.items()
                },
                "supported_under_all_alternatives": all(holds.values()),
            }
        )
    feasibility = {
        "L4-2H2V sway 0.5 m/s held": runs["EXP3-L4-2H2V-sway0.5"]["steady_window_request_met"],
        "L4-2H2V oblique 0.5 m/s held": runs["EXP3-L4-2H2V-oblique0.5"][
            "steady_window_request_met"
        ],
        "L8-HV sway 0.5 m/s held": runs["EXP3-L8-HV-sway0.5"]["steady_window_request_met"],
        "L8-HV oblique 0.5 m/s held": runs["EXP3-L8-HV-oblique0.5"]["steady_window_request_met"],
    }
    return {"ranking": out, "feasibility": feasibility}


def interval_of(record):
    lo, hi = record.si("value_min"), record.si("value_max")
    v = record.si("value")
    if record.bound in ("exact", "nominal", "typical", "measured_mean"):
        lo = v if lo is None else lo
        hi = v if hi is None else hi
    if record.bound == "upper_bound":
        hi = v if hi is None else hi
        lo = 0.0 if lo is None else lo
    return (lo, hi)


def part_b(registry):
    cross = json.loads((FINAL / "crosslayer.json").read_text(encoding="utf-8"))
    out = {}
    for strategy in ("direct", "optical"):
        net = cross["results"][strategy]["network"]["vehicle_metrics"]["interfaces"]
        lo = hi = 0.0
        detail = []
        for name, iface in net.items():
            for state, seconds in iface["state_duration_s"].items():
                rid = iface["evidence"].get(state)
                if not seconds or not rid:
                    continue
                p_lo, p_hi = interval_of(registry.get(rid))
                lo += seconds * (p_lo if p_lo is not None else 0.0) / 3600
                hi = None if hi is None or p_hi is None else hi + seconds * p_hi / 3600
                detail.append(
                    {
                        "interface": name,
                        "state": state,
                        "s": seconds,
                        "record": rid,
                        "power_interval_W": [p_lo, p_hi],
                    }
                )
        out[strategy] = {
            "nominal_Wh": cross["results"][strategy]["network"]["vehicle_modem_Wh_on_bus"],
            "interval_Wh": [lo, hi],
            "states": detail,
        }
    a, o = out["direct"], out["optical"]
    out["claim"] = {
        "statement": "the optical link uses less modem energy than the acoustic link",
        "nominal": o["nominal_Wh"] < a["nominal_Wh"],
        "evidence_supported": o["interval_Wh"][1] is not None
        and o["interval_Wh"][1] < a["interval_Wh"][0],
    }
    return out


def provenance(inputs):
    """Commit, dirty flag and SHA256 of every input file of a derived result (review R6)."""
    import hashlib

    from holoenergy.provenance import git_state

    git = git_state()
    return {
        "git": {"commit": git.get("commit"), "dirty": git.get("dirty")},
        "inputs": {
            str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in inputs
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, default=FINAL / "decision_case.json")
    args = parser.parse_args(argv)
    registry = default_registry()
    out = {
        "scenario_choices": {
            "reserve": RESERVE,
            "legs_per_charge": LEGS,
            "inspection_phases": INSPECTION_PHASES,
        },
        "provenance": provenance(
            [
                FINAL / "final_runs.json",
                FINAL / "sensitivity.json",
                FINAL / "crosslayer.json",
                FINAL / f"native/EXP6/{MISSION}.summary.json",
            ]
        ),
        "part_a_payload": part_a(registry),
        "part_b_communication": part_b(registry),
        "part_c_layout": part_c(),
    }
    args.output.write_text(json.dumps(out, indent=2, default=str) + "\n", encoding="utf-8")
    a = out["part_a_payload"]
    print("replay check", a["replay_check"])
    for name, c in a["configs"].items():
        print(
            f"{name:38s} nominal {c['nominal_Wh']:.4f} Wh legs(nominal) {c['max_legs_nominal']} "
            f"verdicts {[(k, v['verdict']) for k, v in c['legs'].items()]} "
            f"blocked {c['what_if']['still_blocked_by']} what-if {[(e, v['max_legs_certifiable']) for e, v in c['what_if']['eta'].items()]}"
        )
    for r in a["ranking"]:
        print(
            r["a"][:12],
            "<",
            r["b"][:12],
            "nominal",
            r["nominal_a_lower"],
            "evidence",
            r["verdict"],
            "diff",
            r["difference_low_Wh"],
            r["difference_high_Wh"],
        )
    print(
        out["part_b_communication"]["claim"],
        {k: v["interval_Wh"] for k, v in out["part_b_communication"].items() if k != "claim"},
    )


if __name__ == "__main__":
    main()
