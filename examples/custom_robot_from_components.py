"""A robot that is not a BlueROV2, built from library and user parts with the typed builder.

Five actuators in a non-standard layout:
- two stern T200 at a 15 deg toe-in;
- one lateral T200;
- two vertical thrusters of the user's own design with a single 16 V bench table.

The robot also has a 4S-class pack and library sensors chosen by name (no vehicle profile). A
step-up converter feeds the 19-74 V sonar, and the user supplies their own evidence (a bench
measurement and an engineering assumption).

The numbers that are not from the packaged library are ILLUSTRATIVE (graded D or user-declared).
The point is configurability, not a physical claim. The run uses an energy-only backend, so it
needs no simulator:

    uv run python examples/custom_robot_from_components.py
"""

from __future__ import annotations

import math
import warnings

from holoenergy import (
    BatteryProfile,
    ComputeProfile,
    ConverterProfile,
    EnergyAwareEnv,
    EvidenceRecordSpec,
    EvidenceSourceSpec,
    Ref,
    RobotEnergyProfile,
    SensorProfile,
    State,
    ThrusterProfile,
    assess_energy_requirement,
)


def bench_table():
    """User thruster: one bench table at 16 V (illustrative numbers)."""
    rows = [{"command": 0.0, "force_N": 0.0, "power_W": 0.0}] + [
        {"command": c, "force_N": 35.0 * c, "power_W": 15.0 + 220.0 * c**1.5} for c in (0.5, 1.0)
    ]
    return ({"voltage_V": 16.0, "forward": rows, "reverse": rows},)


def build():
    toe = math.radians(15)
    stern = [
        ThrusterProfile(
            f"S{i + 1}",
            position_m=(-0.35, y, 0.0),
            direction=(math.cos(toe), -math.copysign(math.sin(toe), y), 0.0),
            catalog="bluerobotics-t200",
        )
        for i, y in enumerate((0.15, -0.15))
    ]
    lateral = [
        ThrusterProfile(
            "L1", position_m=(0.05, 0.0, 0.0), direction=(0, 1, 0), catalog="bluerobotics-t200"
        )
    ]
    vertical = [
        ThrusterProfile(
            f"V{i + 1}",
            position_m=(x, 0.0, 0.06),
            direction=(0, 0, 1),
            model="lab_v16",
            voltage_tables=bench_table(),
            voltage_policy="table_voltage",
        )
        for i, x in enumerate((0.25, -0.25))
    ]
    return RobotEnergyProfile(
        name="five-thruster inspection ROV (illustrative)",
        dt_s=0.05,
        water_temperature_C=10.0,
        battery=BatteryProfile(
            nominal_voltage_V=14.8,
            capacity_Ah=15,
            max_current_A=45,
            internal_resistance_ohm=0.025,
            cutoff_voltage_V=12.0,
            ocv_curve=((0, 12.0), (0.5, 14.8), (1, 16.8)),
            losses=Ref("lab_pack.resistance"),
        ),
        thrusters=tuple(stern + lateral + vertical),
        propulsion_evidence=Ref(
            "bluerobotics_t200.static_force_power_curve", relation="representative"
        ),
        components=(
            SensorProfile(name="imaging_sonar", catalog="tritech-gemini-720is"),
            SensorProfile(name="dvl", catalog="waterlinked-dvl-a50"),
            ComputeProfile(
                name="computer",
                device="lab_cpu",
                states=(State("ACTIVE", evidence=Ref("lab_cpu.power")),),
                initial_state="ACTIVE",
            ),
        ),
        converters=(
            ConverterProfile(
                name="sonar_boost",
                serves=("imaging_sonar",),
                input_V=(9, 36),
                quiescent=State("ACTIVE", power_W=1.0),
            ),
        ),
        sources=(
            EvidenceSourceSpec("LAB-NB-1", "measurement", "Own bench measurements, notebook 1"),
            EvidenceSourceSpec(
                "ENG-ASSUME-1", "assumption", "Engineering assumption (team review)"
            ),
        ),
        records=(
            EvidenceRecordSpec(
                "lab_pack.resistance",
                "lab_pack",
                "resistance",
                "ohm",
                value=0.025,
                value_min=0.022,
                value_max=0.028,
                bound="measured_mean",
                relation="exact",
                grade="A",
                sources=("LAB-NB-1",),
            ),
            EvidenceRecordSpec(
                "lab_cpu.power",
                "lab_cpu",
                "electrical_power",
                "W",
                value=7.0,
                value_min=6.0,
                value_max=8.0,
                bound="range",
                relation="user",
                grade="D",
                sources=("ENG-ASSUME-1",),
            ),
        ),
        allow_placeholders=True,
    )


class EnergyOnlyBackend:
    def step(self, action):
        return {}

    def close(self):
        pass


def main():
    warnings.simplefilter("ignore", UserWarning)
    robot = build()
    contract = {
        "agent_type": "custom",
        "control_scheme": 0,
        "action_units": "force_N",
        "thruster_count": len(robot.thrusters),
        "dt_s": robot.dt_s,
    }
    with EnergyAwareEnv(
        EnergyOnlyBackend(), energy_profile=robot, control_contract=contract
    ) as env:
        for _ in range(int(60 / robot.dt_s)):  # 60 s holding a 12 N surge + 6 N heave demand
            env.step([12.0, 0.0, 6.0, 0.0, 0.0, 0.0])
        report = env.energy.report()
    print(
        f"terminal energy {report.terminal_energy_Wh:.4f} Wh, categories {report.category_energy_Wh}"
    )
    print("electrical grade shares (%):", report.evidence["share_percent"])
    dyn = report.evidence["dynamics_evidence"]
    print(
        f"dynamics: {dyn['source']} / {dyn['external_consistency']} / validation {dyn['validation']}"
        f" ({dyn['dependent_share_percent']:.0f} % of the energy follows the dynamics)"
    )
    for w in report.evidence["scientific_warnings"]:
        print(f"WARNING [{w['kind']}] {w['subject']}: {w['effect']}")
    verdict = assess_energy_requirement(report, max_energy_wh=1.0)
    print(
        f"requirement <= 1 Wh: nominal pass {verdict.nominal_pass}, verdict {verdict.verdict}, "
        f"open {list(verdict.open_high)}"
    )


if __name__ == "__main__":
    main()
