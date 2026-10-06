"""Compare identical synthetic/BlueROV2 commands with sonar OFF and ACTIVE."""

import copy

from _common import action_for_step, backend, parser, settings, simulator_action

from holoenergy import EnergyAwareEnv


def run(args, config, sonar_state):
    config = copy.deepcopy(config)
    config["sensors"]["ImagingSonar"]["initial_state"] = sonar_state
    config["logging"]["path"] = str(
        args.output_dir / f"sonar_{sonar_state.lower()}.{args.log_format}"
    )
    base, contract = backend(args, config)
    payload_Wh = 0.0
    with EnergyAwareEnv(base, config=config, control_contract=contract) as env:
        for step in range(args.steps):
            energy = env.step(simulator_action(args, action_for_step(step)))["Energy"]
            payload_Wh += energy["power_payload_W"] * energy["dt_s"] / 3600
    return energy["energy_used_Wh"], payload_Wh, energy["soc"]


def main():
    args = parser(__doc__).parse_args()
    try:
        config = settings(args)
        off = run(args, config, "OFF")
        active = run(args, config, "ACTIVE")
        print(f"Backend: {args.backend}; Ping360 ACTIVE uses its 5 W datasheet maximum.")
        print("Placeholders remain in battery/thermal/hotel/converter parameters.")
        print(f"OFF:    total {off[0]:.6f} Wh, payload {off[1]:.6f} Wh, SOC {off[2]:.6f}")
        print(f"ACTIVE: total {active[0]:.6f} Wh, payload {active[1]:.6f} Wh, SOC {active[2]:.6f}")
        print(f"Difference: total {active[0] - off[0]:.6f} Wh; payload {active[1] - off[1]:.6f} Wh")
        print(
            "Under power limiting, added sonar demand can displace propulsion instead of raising total."
        )
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(f"Payload demo failed: {exc}") from exc


if __name__ == "__main__":
    main()
