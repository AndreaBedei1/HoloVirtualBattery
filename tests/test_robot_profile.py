"""Typed builder: a seven-actuator robot assembled from library and user parts.

The builder only produces the public configuration, so the same loader and models run. The
test checks that nothing BlueROV2-specific is needed: any actuator count and orientation, a user
pack, library sensors selected without a vehicle profile, a converter that closes a supply gap,
the user's own evidence, and a YAML round trip.
"""

import math
import warnings

import pytest

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
)
from holoenergy._validation import ConfigurationError
from holoenergy.config import load_config


def user_tables():
    rows = [{"command": 0.0, "force_N": 0.0, "power_W": 0.0}] + [
        {"command": c, "force_N": 40.0 * c, "power_W": 20.0 + 250.0 * c**1.5} for c in (0.5, 1.0)
    ]
    return ({"voltage_V": 15.0, "forward": rows, "reverse": rows},)


def robot():
    c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
    horizontals = [
        ThrusterProfile(f"H{i + 1}", position_m=p, direction=d, catalog="bluerobotics-t200")
        for i, (p, d) in enumerate(
            [
                ((0.2, -0.12, 0), (c, s, 0)),
                ((0.2, 0.12, 0), (c, -s, 0)),
                ((-0.2, 0.12, 0), (c, s, 0)),
                ((-0.2, -0.12, 0), (c, -s, 0)),
            ]
        )
    ]
    verticals = [
        ThrusterProfile(
            f"V{i + 1}",
            position_m=p,
            direction=(0, 0, 1),
            model="lab_thruster",
            voltage_tables=user_tables(),
            voltage_policy="table_voltage",
            evidence=Ref("lab_thruster.bench", relation="exact"),
        )
        for i, p in enumerate([(0.25, 0, 0.05), (-0.25, 0.15, 0.05), (-0.25, -0.15, 0.05)])
    ]
    return RobotEnergyProfile(
        name="seven-actuator test robot",
        dt_s=0.05,
        water_temperature_C=12.0,
        battery=BatteryProfile(
            nominal_voltage_V=14.8,
            capacity_Ah=20,
            max_current_A=50,
            internal_resistance_ohm=0.02,
            cutoff_voltage_V=12.0,
            ocv_curve=((0, 12.0), (0.5, 14.8), (1, 16.8)),
            losses=Ref("lab_pack.resistance"),
        ),
        thrusters=tuple(horizontals + verticals),
        propulsion_evidence=Ref(
            "bluerobotics_t200.static_force_power_curve", relation="representative"
        ),
        components=(
            SensorProfile(name="imaging_sonar", catalog="tritech-gemini-720is"),
            ComputeProfile(
                name="computer",
                device="lab_cpu",
                states=(State("ACTIVE", current_A=1.2, at_V=5.0),),
                initial_state="ACTIVE",
            ),
        ),
        converters=(
            ConverterProfile(
                name="sonar_boost",
                serves=("imaging_sonar",),
                input_V=(9, 36),
                quiescent=State("ACTIVE", evidence=Ref("lab_boost.quiescent")),
            ),
        ),
        sources=(EvidenceSourceSpec("LAB-NB-4", "measurement", "Bench notebook 4, 2026"),),
        records=(
            EvidenceRecordSpec(
                "lab_pack.resistance",
                "lab_pack",
                "resistance",
                "ohm",
                value=0.02,
                value_min=0.018,
                value_max=0.022,
                bound="measured_mean",
                relation="exact",
                grade="A",
                sources=("LAB-NB-4",),
            ),
            EvidenceRecordSpec(
                "lab_boost.quiescent",
                "lab_boost",
                "electrical_power",
                "W",
                value=1.5,
                bound="measured_mean",
                relation="exact",
                grade="A",
                sources=("LAB-NB-4",),
            ),
            EvidenceRecordSpec(
                "lab_thruster.bench",
                "lab_thruster",
                "force_power_table",
                None,
                bound="measured_mean",
                relation="exact",
                grade="A",
                sources=("LAB-NB-4",),
                dataset="__set_in_test__",
            ),
        ),
        allow_placeholders=True,
    )


def with_dataset(profile, tmp_path):
    import dataclasses
    import json

    path = tmp_path / "lab_thruster.json"
    path.write_text(json.dumps({"voltage_tables": list(user_tables())}), encoding="utf-8")
    records = tuple(
        dataclasses.replace(r, dataset=str(path)) if r.dataset else r for r in profile.records
    )
    return dataclasses.replace(profile, records=records)


class Backend:
    def step(self, action):
        return {}

    def close(self):
        pass


CONTRACT = {
    "agent_type": "custom",
    "control_scheme": 0,
    "action_units": "force_N",
    "thruster_count": 7,
    "dt_s": 0.05,
}


def test_builder_robot_runs_with_user_evidence_and_closes_the_supply_gap(tmp_path):
    warnings.simplefilter("ignore", UserWarning)
    profile = with_dataset(robot(), tmp_path)
    with EnergyAwareEnv(Backend(), energy_profile=profile, control_contract=CONTRACT) as env:
        assert len(env.propulsion.ids) == 7
        for _ in range(100):
            env.step([15.0, 4.0, 12.0, 0.0, 0.0, 0.5])
        report = env.energy.report()
        assert env.evidence_map.actuator_grades["V1"] == "B"  # table_voltage: representative
        assert env.evidence_map.actuator_grades["H1"] == "B"
    kinds = {(w["kind"], w["subject"]) for w in report.evidence["scientific_warnings"]}
    assert ("supply_domain_mismatch", "imaging_sonar") not in kinds  # the boost converter serves it
    assert any(k == "voltage_independent_table" for k, _ in kinds)
    assert report.device_state_energy_Wh["computer"]["ACTIVE"] > 0  # 1.2 A at 5 V
    assert "lab_pack.resistance" in report.provenance["user_evidence"]["records"]


def test_yaml_round_trip_gives_the_same_resolved_configuration(tmp_path):
    warnings.simplefilter("ignore", UserWarning)
    profile = with_dataset(robot(), tmp_path)
    path = profile.to_yaml(tmp_path / "robot.yaml")
    loaded = load_config(path)
    assert loaded == load_config(data=profile.to_config())
    # Independent expectations, not derived from to_config():
    assert loaded["simulation"]["dt_s"] == 0.05
    assert loaded["battery"]["capacity_Ah"] == 20
    assert loaded["propulsion"]["thruster_count"] == 7
    geometry = {g["id"]: g for g in loaded["actuation"]["geometry"]}
    assert geometry["V2"]["position_m"] == [-0.25, 0.15, 0.05]
    assert geometry["H1"]["direction"][0] == pytest.approx(math.cos(math.radians(30)))
    assert loaded["evidence"]["battery_losses"]["record"] == "lab_pack.resistance"
    assert loaded["hotel_load"]["constant_W"] == 0.0


def test_validate_reports_structured_warnings(tmp_path):
    warnings.simplefilter("ignore", UserWarning)
    found = with_dataset(robot(), tmp_path).validate()
    kinds = {w["kind"] for w in found}
    assert "voltage_independent_table" in kinds  # V1-V3 read their 15 V table on a 12-16.8 V bus
    assert "supply_domain_mismatch" not in kinds  # the boost converter serves the sonar


def test_builder_never_fills_missing_values():
    import dataclasses

    with pytest.raises(ConfigurationError, match="water_temperature_C"):
        dataclasses.replace(robot(), water_temperature_C=None).to_config()
    with pytest.raises(ConfigurationError, match="current_A needs at_V"):
        State("ACTIVE", current_A=1.0).to_entry()
    unknown = ComputeProfile(name="x", states=(State("ACTIVE"),)).to_entry()
    assert unknown["status"] == "unconfigured"


def test_builder_guards_against_invalid_choices():
    import dataclasses

    import numpy as np

    with pytest.raises(ConfigurationError, match="thermal"):
        dataclasses.replace(robot(), thermal="lumped").to_config()
    with pytest.raises(ConfigurationError, match="cannot serve itself"):
        ConverterProfile(name="c", serves=("c",), input_V=(9, 36)).to_entry()
    bucket = BatteryProfile(nominal_voltage_V=14.8, capacity_Ah=10, model="energy_bucket")
    assert bucket.to_section()["capacity_Wh"] == pytest.approx(148.0)
    numpy_robot = dataclasses.replace(robot(), dt_s=np.float64(0.05))
    assert "dt_s: 0.05" in numpy_robot.to_yaml(tmp_path_factory_dir()).read_text(encoding="utf-8")


def tmp_path_factory_dir():
    import tempfile
    from pathlib import Path

    return Path(tempfile.mkdtemp()) / "numpy_robot.yaml"


def test_ref_relation_caps_the_component_grade():
    entry = ComputeProfile(
        name="cpu", states=(State("ACTIVE", evidence=Ref("lab_boost.quiescent", relation="proxy")),)
    ).to_entry()
    assert entry["relation"] == "proxy"
