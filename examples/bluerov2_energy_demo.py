"""Run an explicit HoloOcean scenario or opt-in energy-only synthetic backend."""

from _common import action_for_step, backend, parser, settings, simulator_action

from holoenergy import EnergyAwareEnv


def main():
    args = parser(__doc__).parse_args()
    try:
        config = settings(args)
        base, contract = backend(args, config)
        powers = []
        with EnergyAwareEnv(base, config=config, control_contract=contract) as env:
            for step in range(args.steps):
                energy = env.step(simulator_action(args, action_for_step(step)))["Energy"]
                powers.append(energy["power_total_W"])
            print(f"Backend: {args.backend}")
            print(
                "Demo inputs include uncalibrated parameters; results are not real ROV endurance."
            )
            print(f"Energy: {energy['energy_used_Wh']:.6f} Wh")
            print(f"Final SOC: {energy['soc']:.6f}")
            print(f"Mean power: {sum(powers) / len(powers):.3f} W; max: {max(powers):.3f} W")
            print(f"Final temperature: {energy['temperature_C']:.3f} C")
            print(f"Log: {config['logging']['path']}")
    except (RuntimeError, ValueError, OSError) as exc:
        raise SystemExit(f"Energy demo failed: {exc}") from exc


if __name__ == "__main__":
    main()
