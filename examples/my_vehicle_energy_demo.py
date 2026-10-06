"""Custom ROV with supplied synthetic data: no hardware profile or core edit required."""

import argparse
from pathlib import Path

from holoenergy import EnergyAwareEnv
from holoenergy.analysis.replay import ReplayBackend
from holoenergy.config import load_config


def my_vehicle_config():
    # Every number below is a user-selected demonstration input, not hardware data.
    return {
        "vehicle": {"name": "MyCustomROV"},
        "simulation": {"dt_s": 0.05},
        "battery": {
            "model": "rint",
            "chemistry": "LiFePO4",
            "capacity_Ah": 30,
            "nominal_voltage_V": 24,
            "initial_soc": 1,
            "max_current_A": 30,
            "internal_resistance_ohm": 0.08,
            "cutoff_voltage_V": 20,
            "ocv_curve": [[0, 21], [1, 26]],
            "metadata": {"status": "USER-SUPPLIED", "source": "synthetic demo inputs"},
        },
        "actuators": [
            {
                "count": 6,
                "model": "custom_lookup",
                "force_power_tables": [
                    {
                        "voltage_V": v,
                        "forward": [[0, 0], [10, 30], [30, 150]],
                        "reverse": [[0, 0], [10, 35], [30, 160]],
                    }
                    for v in (20, 30)
                ],
                "metadata": {"status": "USER-SUPPLIED", "source": "synthetic demo inputs"},
            }
        ],
        "components": [
            {
                "name": "my_sonar",
                "category": "sensors",
                "states": {"OFF": 0, "IDLE": 3, "ACTIVE": 18},
            },
            {"name": "my_camera", "category": "sensors", "active_W": 4},
            {
                "name": "my_compute",
                "category": "compute",
                "power_model": {
                    "type": "lookup",
                    "input": "compute_load",
                    "initial_value": 0.2,
                    "points": [[0, 8], [0.5, 15], [1, 25]],
                },
            },
        ],
        "environment": {"water_temperature_C": 8},
        "thermal": {
            "initial_temperature_C": 20,
            "thermal_capacity_J_per_C": 2000,
            "cooling_coeff_W_per_C": 3,
            "derating_temperature_C": 45,
            "cutoff_temperature_C": 55,
            "metadata": {"status": "USER-SUPPLIED", "source": "synthetic demo inputs"},
        },
        "power_manager": {"apply_derating_to_actions": True},
        "metadata": {
            "status": "USER-SUPPLIED",
            "source": "demonstration configuration",
            "assumptions": "All values are synthetic; no real dynamics or energy validation",
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Optional completely different vehicle YAML")
    parser.add_argument("--steps", type=int, default=200)
    parser.add_argument("--output-dir", type=Path, default=Path("logs/custom_vehicle"))
    args = parser.parse_args()
    if args.steps <= 0:
        parser.error("--steps must be positive")
    config = load_config(args.config) if args.config else load_config(data=my_vehicle_config())
    config["logging"] = {
        "enabled": True,
        "format": "jsonl",
        "path": str(args.output_dir / "energy.jsonl"),
    }
    config["provenance"] = {
        "purpose": "custom user vehicle demonstration; energy only",
        "calibration_status": "synthetic supplied inputs",
    }
    with EnergyAwareEnv(ReplayBackend(config), config=config) as env:
        env.energy.mark_phase("inspection")
        for step in range(args.steps):
            if step == args.steps // 2:
                env.energy.mark_phase("return")
                if "my_compute" in env.payload.components:
                    env.energy.set_component_input("my_compute", compute_load=0.8)
            env.step([5.0] * env.propulsion.count)
        print(f"{env.vehicle.name}: {env.propulsion.count} actuators, {env.battery.nominal_V:g} V")
        print(f"Terminal energy: {env.energy.summary()['terminal_energy_Wh']:.6f} Wh")
        print("Demonstration configuration; no vehicle dynamics or physical validation")


if __name__ == "__main__":
    main()
