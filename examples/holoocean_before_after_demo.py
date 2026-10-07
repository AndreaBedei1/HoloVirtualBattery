"""Same robot, current, controller, battery and mission on stock and patched HoloOcean 2.3.0.

The AFTER backend is an implementation-corrected simulation (drag in the units of
its own SI equation); neither run is a real-world validation of the BlueROV2.
"""

import json
import math

from _common import ROOT, parser, settings
from native_current_energy_study import metrics, mission_plan, run

from holoenergy.provenance import write_json

K_SOURCE = 0.5 * 997 * 0.8 * 0.45  # HoloOcean 2.3.0 BlueROV2 source coefficients, N/(m/s)^2
BUILD_DRAG_SCALE = {"before": 0.01, "after": 1.0}  # measured by the drag audit, not assumed


def implementation_drag_N(trace, scale):
    """Drag implied by the source equation and the audited build scale along the trace."""
    values = []
    for row in trace:
        relative = [v - c for v, c in zip(row["velocity_m_s"], row["current_m_s"], strict=True)]
        speed = math.sqrt(sum(r * r for r in relative))
        values.append(scale * K_SOURCE * speed * speed)
    return values


def main():
    p = parser(__doc__)
    p.set_defaults(scenario=ROOT / "configs/bluerov2_realtime_holoocean.json")
    p.add_argument("--before-binary", help="Stock package executable (default: installed)")
    p.add_argument("--after-binary", required=True, help="Patched package executable")
    p.add_argument("--current", type=float, default=0.4, help="World-X current, m/s")
    p.add_argument("--trace-every", type=int, default=10)
    args = p.parse_args()
    if args.backend != "holoocean":
        p.error("The demo requires the native HoloOcean backend")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = {}
    for label, binary in (("before", args.before_binary), ("after", args.after_binary)):
        args.holoocean_binary = binary
        baseline = settings(args)
        plan = mission_plan(baseline["simulation"]["dt_s"])
        trace, summary, config = run(args, baseline, f"demo_{label}", [args.current, 0, 0], plan)
        result = metrics(trace, summary, config, 3)
        drag = implementation_drag_N(trace, BUILD_DRAG_SCALE[label])
        result["mean_implementation_drag_N"] = sum(drag) / len(drag)
        result["peak_implementation_drag_N"] = max(drag)
        results[label] = result
    rows = [
        ("implementation drag, mean [N]", "mean_implementation_drag_N"),
        ("implementation drag, peak [N]", "peak_implementation_drag_N"),
        ("applied effort norm, last 3 s [N]", "mean_tail_applied_effort_norm_N"),
        ("saturated ticks [-]", "saturated_tick_fraction"),
        ("propulsion energy [Wh]", "propulsion_Wh"),
        ("terminal energy [Wh]", "terminal_Wh"),
        ("max position error [m]", "max_position_error_m"),
        ("max |roll|,|pitch| [deg]", "max_abs_roll_pitch_deg"),
        ("final SOC [-]", "final_soc"),
    ]
    print(f"Mission at {args.current:g} m/s current: stock vs patched HoloOcean 2.3.0")
    print(f"{'quantity':38s} {'stock':>12s} {'patched':>12s}")
    for name, key in rows:
        print(f"{name:38s} {results['before'][key]:12.5f} {results['after'][key]:12.5f}")
    write_json(
        args.output_dir / "before_after_demo.json",
        {
            "evidence_kind": "implementation-corrected simulation vs stock simulation; "
            "not real-world validation",
            "current_m_s": args.current,
            "drag_scale_basis": "audited runtime scale of each build (sources/verified_backend)",
            "results": results,
        },
    )
    print(json.dumps({"output": str(args.output_dir / "before_after_demo.json")}))


if __name__ == "__main__":
    main()
