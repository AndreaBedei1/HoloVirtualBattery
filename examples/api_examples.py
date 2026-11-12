"""Concise HoloEnergy API examples (no simulator needed: a null backend stands in for HoloOcean).

Replace ``NullBackend()`` by your HoloOcean environment (see experiments/run_native_campaign.py
for the native closed loop). Each function returns the run's EnergyReport as a dict.

    python examples/api_examples.py
"""

from __future__ import annotations

import warnings

from holoenergy import EnergyAwareEnv
from holoenergy.catalog import modem_profile
from holoenergy.integrations import ModemPowerProfile
from holoenergy.integrations.desert import DesertEnergyAdapter

DT = 0.01
CONTRACT = {
    "agent_type": "BlueROV2",
    "control_scheme": 0,
    "action_units": "force_N",
    "thruster_count": 8,
    "dt_s": DT,
}
NATIVE_GEOMETRY = [  # HoloOcean 2.3.0 BlueROV2 (holoenergy/profiles/holoocean/agents_2.3.0.json)
    {"id": f"V{i + 1}", "position_m": p, "direction": [0, 0, 1]}
    for i, p in enumerate(
        [
            [0.12, -0.2181, 0.0809],
            [0.12, 0.2181, 0.0809],
            [-0.12, 0.2181, 0.0809],
            [-0.12, -0.2181, 0.0809],
        ]
    )
] + [
    {"id": f"H{i + 1}", "position_m": p, "direction": d}
    for i, (p, d) in enumerate(
        [
            ([0.1562, -0.0988, 0.0], [0.7071067811865476, 0.7071067811865476, 0.0]),
            ([0.1562, 0.0988, 0.0], [0.7071067811865476, -0.7071067811865476, 0.0]),
            ([-0.1562, 0.0988, 0.0], [0.7071067811865476, 0.7071067811865476, 0.0]),
            ([-0.1562, -0.0988, 0.0], [0.7071067811865476, -0.7071067811865476, 0.0]),
        ]
    )
]


class NullBackend:
    """Stands in for a dynamics backend: accepts the action, returns no observations."""

    def step(self, action):
        return {}

    def reset(self):
        return {}

    def close(self):
        pass


def run(env, action, seconds=2.0):
    with env:
        for _ in range(round(seconds / DT)):
            env.step(action)
        return env.energy.report().to_dict()


def bluerov2_heavy():
    """Simulator-exact 8-thruster BlueROV2 Heavy, per-thruster forces (N)."""
    env = EnergyAwareEnv(NullBackend(), vehicle_profile="bluerov2-heavy", control_contract=CONTRACT)
    return run(env, [0, 0, 0, 0, 10, 10, 10, 10])  # four vectored horizontals, surge


def standard_6t_virtual_layout():
    """Virtual 6-thruster layout evaluated on the Heavy body through wrench-equivalent actuation."""
    env = EnergyAwareEnv(
        NullBackend(), vehicle_profile="bluerov2-standard", control_contract=CONTRACT
    )
    return run(env, [20.0, 0, 0, 0, 0, 0])  # body wrench [Fx, Fy, Fz, Mx, My, Mz]


def custom_4t_layout():
    """Any actuator count/orientation: two stern thrusters + two centreline verticals."""
    t200 = "package:actuators/bluerobotics_t200.yaml"
    actuators = [
        {"id": "H1", "profile": t200, "position_m": [-0.16, 0.10, 0.0], "direction": [1, 0, 0]},
        {"id": "H2", "profile": t200, "position_m": [-0.16, -0.10, 0.0], "direction": [1, 0, 0]},
        {"id": "V1", "profile": t200, "position_m": [0.12, 0.0, 0.08], "direction": [0, 0, 1]},
        {"id": "V2", "profile": t200, "position_m": [-0.12, 0.0, 0.08], "direction": [0, 0, 1]},
    ]
    overrides = {
        "actuators": actuators,
        "actuation": {
            "action_mode": "wrench",
            "allocation": {"method": "redistributed"},
            "backend": {
                "mapping": "wrench_equivalent",
                "native_geometry": NATIVE_GEOMETRY,
                "native_clamp_N": 28.75,
                "agent_type": "BlueROV2",
            },
        },
        "evidence": {"vehicle_relation": "user"},  # a user design, not a real vehicle
    }
    env = EnergyAwareEnv(
        NullBackend(),
        vehicle_profile="bluerov2-heavy",
        control_contract=CONTRACT,
        overrides=overrides,
    )
    return run(env, [15.0, 0, 5.0, 0, 0, 0])


def sensor_suite():
    """Add evidence-linked payload components by catalog name (DVL + imaging sonar)."""
    env = EnergyAwareEnv(
        NullBackend(),
        vehicle_profile="bluerov2-heavy",
        control_contract=CONTRACT,
        components=["waterlinked-dvl-a50", "bluerobotics-ping360"],
    )
    return run(env, [0] * 8)


def compute_workload():
    """Onboard AI computer at its measured inference workload (Jetson Orin NX, YOLOv8s)."""
    env = EnergyAwareEnv(
        NullBackend(),
        vehicle_profile="bluerov2-heavy",
        control_contract=CONTRACT,
        components=["jetson-orin-nx-16gb"],
    )
    return run(env, [0] * 8)


def desert_integration():
    """Observe-only communication energy from holo_desert PHY events.

    With a live session: ``net = adapter.observed(session)`` and use ``net`` in place of
    ``session``; or feed ``adapter.observe(link.sync(state))`` with a HoloOceanLink.
    """
    profile = ModemPowerProfile.from_mapping(modem_profile("evologics-s2cm-18-34-1000m"))
    adapter = DesertEnergyAdapter(
        {"acoustic": profile}, node="auv_01", node_map={"auv_01": 1, "auv_02": 2}
    )
    adapter.ensure_interfaces(["acoustic"])
    env = EnergyAwareEnv(NullBackend(), vehicle_profile="bluerov2-heavy", control_contract=CONTRACT)
    env.attach(adapter)
    adapter.observe(
        [
            {
                "event": "phy_tx_start",
                "time": 0.5,
                "node": 1,
                "interface_index": 0,
                "duration_s": 0.41,
                "phy_bits": 1960,
            }
        ]
    )
    return run(env, [0] * 8)


def custom_battery():
    """User battery replacing the profile's pack: user values are graded D, never inherited.

    Changing a value the profile linked to evidence (here the resistance) drops that link:
    ``env.warnings`` names it and the battery-loss energy is graded D.
    """
    battery = {
        "capacity_Ah": 10.0,
        "initial_soc": 0.9,
        "max_current_A": 30.0,
        "internal_resistance_ohm": 0.03,
        "metadata": {"status": "USER-SUPPLIED", "placeholders": ["internal_resistance_ohm"]},
    }
    env = EnergyAwareEnv(
        NullBackend(),
        vehicle_profile="bluerov2-heavy",
        control_contract=CONTRACT,
        overrides={"battery": battery},
    )
    assert any(w.startswith("stale evidence link: battery_loss") for w in env.warnings)
    return run(env, [0, 0, 0, 0, 10, 10, 10, 10])


def proxy_auv_profile():
    """Literature proxy on a generic HoloOcean class (grade C electrical model, not validated).

    A REMUS-derived energy profile applied to the HoloOcean TorpedoAUV dynamic class; the
    propulsor table is valid for 7.1-24.8 N forward thrust only (see the profile metadata).
    """
    contract = {
        "agent_type": "TorpedoAUV",
        "control_scheme": 0,
        "action_units": "force_N",
        "thruster_count": 1,
        "dt_s": DT,
    }
    env = EnergyAwareEnv(
        NullBackend(), vehicle_profile="torpedo-remus-like", control_contract=contract
    )
    return run(env, [15.0])


EXAMPLES = [
    bluerov2_heavy,
    standard_6t_virtual_layout,
    custom_4t_layout,
    sensor_suite,
    compute_workload,
    desert_integration,
    custom_battery,
    proxy_auv_profile,
]


def main():
    warnings.simplefilter("ignore", UserWarning)  # demo profiles carry declared placeholders
    for example in EXAMPLES:
        report = example()
        energy = report["terminal_energy_Wh"]
        coverage = {g: round(v, 1) for g, v in report["evidence"]["share_percent"].items()}
        print(f"{example.__name__:28s} {energy:.5f} Wh  evidence share {coverage}")


if __name__ == "__main__":
    main()
