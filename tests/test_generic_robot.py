"""A robot unlike any packaged profile, built from scratch with the user's own evidence.

Five heterogeneous actuators (three T200, two of a user thruster with a single 16 V table), a
custom 4S-class pack, user sensors and compute, and evidence the user supplies (own measurement, datasheet,
dataset file). Nothing from the BlueROV2 profiles is inherited. Requirements of the generality
brief: user evidence must reach components, actuators, battery losses, intervals and the report.
"""

import json
import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.decision import assess_energy_requirement

T200 = "package:actuators/bluerobotics_t200.yaml"


def acme_tables():
    rows = [
        {"command": c, "force_N": 60.0 * c, "power_W": 0.0 if c == 0 else 30 + 400.0 * c**1.5}
        for c in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    rows[0]["power_W"] = 0.0
    return [{"voltage_V": 16.0, "forward": rows, "reverse": rows}]


def config(dataset_path):
    tables = acme_tables()
    acme = {"model": "acme_q16", "voltage_policy": "table_voltage", "voltage_tables": tables}
    return {
        "allow_placeholders": True,
        "vehicle": {"name": "five-thruster test ROV"},
        "simulation": {"dt_s": 0.05},
        "environment": {"water_temperature_C": 15},
        "battery": {
            "model": "rint",
            "capacity_Ah": 10,
            "nominal_voltage_V": 14.8,
            "initial_soc": 1,
            "max_current_A": 40,
            "internal_resistance_ohm": 0.03,
            "cutoff_voltage_V": 12.0,
            "ocv_curve": [[0, 12.0], [0.5, 14.8], [1, 16.8]],
        },
        "thermal": {
            "initial_temperature_C": 20,
            "thermal_capacity_J_per_C": 1500,
            "cooling_coeff_W_per_C": 2,
            "derating_temperature_C": 45,
            "cutoff_temperature_C": 60,
        },
        "actuators": [
            {"id": "S1", "profile": T200, "position_m": [-0.3, 0.12, 0], "direction": [1, 0, 0]},
            {"id": "S2", "profile": T200, "position_m": [-0.3, -0.12, 0], "direction": [1, 0, 0]},
            {"id": "L1", "profile": T200, "position_m": [0.0, 0.0, 0.0], "direction": [0, 1, 0]},
            {"id": "V1", **acme, "position_m": [0.2, 0, 0.05], "direction": [0, 0, 1]},
            {"id": "V2", **acme, "position_m": [-0.2, 0, 0.05], "direction": [0, 0, 1]},
        ],
        "actuation": {
            "action_mode": "wrench",
            "allocation": {"method": "redistributed"},
            "backend": {"mapping": "direct", "backend_index": [0, 1, 2, 3, 4]},
        },
        "components": [
            {
                "name": "forward_sonar",
                "device": "acme_fls",
                "category": "sensors",
                "supply_V": [10, 30],
                "states": {"ACTIVE": {"evidence": "acme_fls.power"}},
            },
            {
                "name": "computer",
                "device": "acme_cpu",
                "category": "compute",
                "states": {"ACTIVE": {"evidence": "acme_cpu.power_measured"}},
            },
        ],
        "hotel_load": {"constant_W": 0},
        "converters": {"payload_efficiency": 1.0},
        "evidence": {
            "propulsion": {
                "record": "bluerobotics_t200.static_force_power_curve",
                "relation": "representative",
            },
            "actuators": {
                "V1": {"record": "acme_q16.bench_table", "relation": "exact"},
                "V2": {"record": "acme_q16.bench_table", "relation": "exact"},
            },
            "battery_losses": {"record": "acme_pack.dc_resistance", "relation": "exact"},
            "sources": [
                {
                    "id": "LAB-2026-01",
                    "type": "user",
                    "title": "Own bench measurement, lab notebook 3",
                },
                {
                    "id": "ACME-DS",
                    "type": "manufacturer_datasheet",
                    "title": "ACME FLS datasheet",
                    "url": "https://example.invalid/acme-fls.pdf",
                },
            ],
            "records": [
                {
                    "id": "acme_fls.power",
                    "component": "acme_fls",
                    "quantity": "electrical_power",
                    "unit": "W",
                    "value_min": 8.0,
                    "value_max": 12.0,
                    "value": 10.0,
                    "bound": "typical",
                    "relation": "exact",
                    "grade": "A",
                    "sources": ["ACME-DS"],
                    "location": {"page": 2},
                },
                {
                    "id": "acme_cpu.power_measured",
                    "component": "acme_cpu",
                    "quantity": "electrical_power",
                    "unit": "W",
                    "value": 6.0,
                    "value_min": 5.5,
                    "value_max": 6.5,
                    "bound": "measured_mean",
                    "relation": "exact",
                    "grade": "A",
                    "sources": ["LAB-2026-01"],
                },
                {
                    "id": "acme_q16.bench_table",
                    "component": "acme_q16",
                    "quantity": "force_power_table",
                    "unit": None,
                    "dataset": {"path": str(dataset_path)},
                    "bound": "measured_mean",
                    "relation": "exact",
                    "grade": "A",
                    "sources": ["LAB-2026-01"],
                },
                {
                    "id": "acme_pack.dc_resistance",
                    "component": "acme_pack",
                    "quantity": "resistance",
                    "unit": "ohm",
                    "value": 0.03,
                    "value_min": 0.027,
                    "value_max": 0.033,
                    "bound": "measured_mean",
                    "relation": "exact",
                    "grade": "A",
                    "sources": ["LAB-2026-01"],
                },
            ],
        },
    }


class Backend:
    energy_action_contract = None

    def step(self, action):
        return {}

    def reset(self):
        return {}

    def close(self):
        pass


CONTRACT = {
    "agent_type": "custom",
    "control_scheme": 0,
    "action_units": "force_N",
    "thruster_count": 5,
    "dt_s": 0.05,
}


@pytest.fixture
def env(tmp_path):
    warnings.simplefilter("ignore", UserWarning)
    dataset = tmp_path / "acme_q16_bench.json"
    dataset.write_text(json.dumps({"voltage_tables": acme_tables()}), encoding="utf-8")
    e = EnergyAwareEnv(Backend(), config=config(dataset), control_contract=CONTRACT)
    yield e
    e.close()


def test_user_evidence_reaches_components_actuators_report_and_intervals(env):
    for _ in range(200):
        env.step([20.0, 5.0, 10.0, 0.0, 0.0, 1.0])
    report = env.energy.report()
    shares = report.evidence["share_percent"]
    assert shares["A"] > 0  # user records graded A for their own hardware
    # Per-actuator links: the user thrusters carry their own (exact, A) record, the T200s the
    # shared representative link (B).
    m = env.evidence_map
    assert m.actuator_grades["V1"] == "A" and m.actuator_grades["S1"] == "B"
    assert report.provenance["user_evidence"]["records"] == [
        "acme_fls.power",
        "acme_cpu.power_measured",
        "acme_q16.bench_table",
        "acme_pack.dc_resistance",
    ]
    rows = {(r["device"], r["state"]): r for r in report.intervals["contributions"]}
    assert rows[("computer", "ACTIVE")]["record"] == "acme_cpu.power_measured"
    assert report.intervals["battery_losses"]["record"] == "acme_pack.dc_resistance"
    kinds = {w["kind"] for w in report.evidence["scientific_warnings"]}
    assert "voltage_independent_table" in kinds  # the single 16 V table on a 12-16.8 V pack
    assert "supply_domain_mismatch" not in kinds  # the sonar's 10-30 V covers the bus
    assessment = assess_energy_requirement(
        report, max_energy_wh=100.0, assume_verified=("payload",)
    )
    assert assessment.verdict in ("SUPPORTED_PASS", "INDETERMINATE")


def test_mistyped_evidence_key_is_rejected(tmp_path):
    bad = config(tmp_path / "missing.json")
    bad["evidence"]["propulsoin"] = bad["evidence"].pop("propulsion")
    with pytest.raises(ConfigurationError, match="propulsoin"):
        EnergyAwareEnv(Backend(), config=bad, control_contract=CONTRACT)


def test_user_record_cannot_shadow_a_packaged_record(tmp_path):
    bad = config(tmp_path / "x.json")
    bad["evidence"]["records"].append(
        {
            "id": "bluerobotics_t200.static_force_power_curve",
            "component": "x",
            "quantity": "electrical_power",
            "unit": "W",
            "value": 1.0,
            "bound": "exact",
            "relation": "user",
            "grade": "D",
        }
    )
    with pytest.raises(ConfigurationError, match="Duplicate evidence id"):
        EnergyAwareEnv(Backend(), config=bad, control_contract=CONTRACT)
