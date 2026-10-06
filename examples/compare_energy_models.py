"""Repeat identical commands with L0/L1 in an explicit synthetic or native scenario."""

from _common import action_for_step, backend, parser, settings, simulator_action

from holoenergy.analysis.replay import compare_models, read_mission


def main():
    p = parser(__doc__)
    p.add_argument(
        "--mission", help="Optional one-tick-per-row mission CSV; otherwise demonstration commands"
    )
    args = p.parse_args()
    config = settings(args)
    commands = (
        read_mission(args.mission, config["simulation"]["dt_s"])
        if args.mission
        else [{"action": action_for_step(i)} for i in range(args.steps)]
    )
    results = compare_models(
        config,
        commands,
        args.output_dir,
        backend_factory=lambda c: backend(args, c),
        action_adapter=lambda a: simulator_action(args, a),
        input_path=args.mission,
    )
    for level, result in results.items():
        m = result["metrics"]
        print(
            f"{level}: {m['terminal_energy_Wh']:.6f} Wh; SOC {m['final_soc']:.6f}; "
            f"overhead {m['wrapper_overhead_s']:.6f} s; mission completion {m['mission_completed']}"
        )
    print("Placeholders remain; no vehicle goal criterion was supplied. See comparison.json/csv.")


if __name__ == "__main__":
    main()
