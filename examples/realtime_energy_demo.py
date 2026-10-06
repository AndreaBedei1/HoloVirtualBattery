"""HoloOcean + HoloEnergy + local dashboard, with a reproducible power-limit event."""

import time
from contextlib import ExitStack

from _common import ROOT, backend, parser, settings, simulator_action

from holoenergy import EnergyAwareEnv
from holoenergy.analysis.replay import ReplayBackend
from holoenergy.dashboard.server import DashboardServer
from holoenergy.provenance import write_json
from holoenergy.telemetry import TelemetryPublisher


def main():
    p = parser(__doc__)
    p.set_defaults(scenario=ROOT / "configs/bluerov2_realtime_holoocean.json")
    p.add_argument("--dashboard-port", type=int, default=8765)
    p.add_argument("--telemetry-port", type=int, default=8766)
    p.add_argument(
        "--no-dashboard", action="store_true", help="Use an independently started dashboard"
    )
    p.add_argument("--no-pacing", action="store_true", help="Run faster than real time")
    p.add_argument(
        "--hold-seconds", type=float, default=0, help="Keep dashboard available after mission"
    )
    args = p.parse_args()
    if args.hold_seconds < 0:
        p.error("--hold-seconds must be nonnegative")
    config = settings(args)
    # Source v0.1.0 pack rating is retained in provenance; this is a test intervention.
    config["provenance"]["purpose"] = "real-time software demo with a temporary 8 A power cap"
    config["logging"]["path"] = str(args.output_dir / "realtime_energy.jsonl")
    rows = []
    with ExitStack() as stack:
        if not args.no_dashboard:
            dashboard = stack.enter_context(
                DashboardServer(args.dashboard_port, args.telemetry_port)
            )
            print(f"Dashboard: {dashboard.url}", flush=True)
        telemetry = stack.enter_context(TelemetryPublisher(args.telemetry_port, 20))
        if args.backend == "synthetic":
            base = ReplayBackend(config)
            contract = base.energy_action_contract
        else:
            base, contract = backend(args, config)
        try:
            env = EnergyAwareEnv(
                base, config=config, control_contract=contract, telemetry=telemetry
            )
        except Exception:
            close = getattr(base, "close", None)
            if close:
                close()
            elif getattr(base, "__exit__", None):
                base.__exit__(None, None, None)
            raise
        try:
            nominal_limit = env.battery.max_current_A
            beginning = time.perf_counter()
            for step in range(args.steps):
                fraction = step / args.steps
                phase = (
                    "transit" if fraction < 0.3 else "power_limit" if fraction < 0.7 else "return"
                )
                env.energy.mark_phase(phase)
                env.battery.max_current_A = 8.0 if phase == "power_limit" else nominal_limit
                # Public direct thruster order belongs to this BlueROV2 demo, not the core.
                direction = 1 if (step // 80) % 2 == 0 else -1
                action = (
                    [0.0] * 4 + [direction * 20.0] * 4
                    if args.backend == "holoocean"
                    else [direction * 20.0] * env.propulsion.count
                )
                if "Camera" in env.payload.components and step == args.steps // 2:
                    env.energy.set_component_state("Camera", "OFF")
                env.energy.set_environment(water_temperature_C=8 if fraction < 0.5 else 15)
                state = env.step(simulator_action(args, action))
                rows.append(state["Energy"])
                if not args.no_pacing:
                    remaining = beginning + (step + 1) * env.dt_s - time.perf_counter()
                    if remaining > 0:
                        time.sleep(remaining)
        finally:
            env.close()
        report = {
            "backend": args.backend,
            "steps": len(rows),
            "phases": env.energy.summary()["phases"],
            "minimum_derating_factor": min(r["derating_factor"] for r in rows),
            "power_limit_intervention_A": 8,
            "telemetry_sent": telemetry.sent,
            "telemetry_dropped": telemetry.dropped,
            "energy_summary": env.energy.summary(),
            "physical_validation": False,
            "power_limit_applied_to_backend": all(r["dynamics_energy_consistent"] for r in rows),
        }
        write_json(args.output_dir / "realtime_report.json", report)
        print(
            f"Demo complete: {len(rows)} steps; minimum action factor {report['minimum_derating_factor']:.4f}",
            flush=True,
        )
        print(f"Report: {args.output_dir / 'realtime_report.json'}", flush=True)
        if args.hold_seconds:
            time.sleep(args.hold_seconds)


if __name__ == "__main__":
    main()
