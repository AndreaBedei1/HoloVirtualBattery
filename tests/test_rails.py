"""Named supply rails (review R3-02): per-rail conversion, evidence and supply domains.

Each test removes a feature and would fail: the per-rail loss must equal sum P (1/eta - 1) on
the rails that carry the loads, an unknown efficiency must leave the rail unverified, and a
device is checked against the voltage of its own rail rather than the pack bus.
"""

import math

import pytest

from holoenergy import (
    BatteryProfile,
    ComputeProfile,
    EnergyAwareEnv,
    EvidenceRecordSpec,
    EvidenceSourceSpec,
    RailProfile,
    RobotEnergyProfile,
    SensorProfile,
    State,
    ThrusterProfile,
    compare_energy,
)
from holoenergy._validation import ConfigurationError
from holoenergy.report import EnergyReport

DT = 0.1
STEPS = 360  # 36 s


class _Null:
    def step(self, action):
        return {}

    def close(self):
        pass


def _robot(components, rails, records=()):
    thrusters = tuple(
        ThrusterProfile(f"T{i}", position_m=p, direction=d, catalog="bluerobotics-t200")
        for i, (p, d) in enumerate(
            [
                ((0.2, 0, 0), (1, 0, 0)),
                ((-0.2, 0, 0), (1, 0, 0)),
                ((0, 0.2, 0), (0, 1, 0)),
                ((0, 0, 0.1), (0, 0, 1)),
            ]
        )
    )
    return RobotEnergyProfile(
        name="rail test robot",
        dt_s=DT,
        water_temperature_C=15.0,
        battery=BatteryProfile(
            nominal_voltage_V=14.8,
            capacity_Ah=18,
            max_current_A=60,
            internal_resistance_ohm=0.02,
            cutoff_voltage_V=12.0,
            ocv_curve=((0, 12.0), (0.5, 14.8), (1, 16.8)),
        ),
        thrusters=thrusters,
        components=tuple(components),
        rails=tuple(rails),
        sources=(EvidenceSourceSpec("LAB-CONV", "measurement", "Converter bench test"),),
        records=tuple(records),
        action_mode="thrusters",
        allow_placeholders=True,
    )


def _run(profile):
    contract = {
        "agent_type": "rail_test",
        "control_scheme": 0,
        "action_units": "force_N",
        "thruster_count": len(profile.thrusters),
        "dt_s": DT,
    }
    with EnergyAwareEnv(_Null(), energy_profile=profile, control_contract=contract) as env:
        for _ in range(STEPS):
            env.step([0.0] * len(profile.thrusters))
        return env.energy.summary(), EnergyReport.from_runtime(env.energy)


EFF_RECORD = EvidenceRecordSpec(
    "lab_5v.efficiency",
    "lab_5v_regulator",
    "conversion_efficiency",
    "1",
    value=0.9,
    bound="measured_mean",
    relation="exact",
    grade="A",
    sources=("LAB-CONV",),
)


def _loads(camera_rail="5V", cpu_rail="5V"):
    return [
        SensorProfile(
            name="camera",
            states=(State("ACTIVE", power_W=3.0),),
            initial_state="ACTIVE",
            rail=camera_rail,
        ),
        ComputeProfile(
            name="computer",
            states=(State("ACTIVE", power_W=6.0),),
            initial_state="ACTIVE",
            rail=cpu_rail,
        ),
    ]


def test_conversion_loss_is_the_sum_over_rails_of_load_times_inverse_efficiency_minus_one():
    rails = [
        RailProfile("5V", output_V=5.0, efficiency=0.9, efficiency_evidence="lab_5v.efficiency"),
        RailProfile("12V", output_V=12.0, efficiency=0.8),
    ]
    summary, _ = _run(_robot(_loads("5V", "12V"), rails, [EFF_RECORD]))
    hours = STEPS * DT / 3600
    expected_loss = (3.0 * (1 / 0.9 - 1) + 6.0 * (1 / 0.8 - 1)) * hours
    assert math.isclose(summary["category_energy_Wh"]["converters"], expected_loss, rel_tol=1e-9)
    # A single legacy payload efficiency could not produce this split.
    assert not math.isclose(expected_loss, 9.0 * (1 / 0.9 - 1) * hours, rel_tol=1e-3)


def test_rail_with_matching_evidence_is_verified_and_one_without_is_not():
    rails = [
        RailProfile("5V", output_V=5.0, efficiency=0.9, efficiency_evidence="lab_5v.efficiency"),
        RailProfile("12V", output_V=12.0, efficiency=0.8),
    ]
    _, report = _run(_robot(_loads("5V", "12V"), rails, [EFF_RECORD]))
    verified = report.intervals["rail_verified"]
    assert verified["5V"] is True
    assert verified["12V"] is False
    kinds = {(w["kind"], w["subject"]) for w in report.evidence["scientific_warnings"]}
    assert ("conversion_unverified", "12V rail") in kinds
    assert ("conversion_unverified", "5V rail") not in kinds


def test_unknown_efficiency_is_charged_at_one_and_reported_as_a_lower_bound():
    rails = [RailProfile("24V", output_V=24.0)]
    sonar = SensorProfile(name="imaging_sonar", catalog="tritech-gemini-720is", rail="24V")
    summary, report = _run(_robot([sonar], rails))
    assert summary["category_energy_Wh"]["converters"] == pytest.approx(0.0, abs=1e-15)
    text = " ".join(w["effect"] for w in report.evidence["scientific_warnings"])
    assert "24V rail converter efficiency is unknown" in text
    assert report.intervals["rail_verified"]["24V"] is False


def test_device_is_checked_against_its_rail_voltage_not_the_pack():
    on_pack = _robot(
        [SensorProfile(name="imaging_sonar", catalog="tritech-gemini-720is", rail="pack")],
        [RailProfile("pack", kind="direct")],
    )
    _, report = _run(on_pack)
    mismatch = [
        w for w in report.evidence["scientific_warnings"] if w["kind"] == "supply_domain_mismatch"
    ]
    assert mismatch and "requires 19-74 V" in mismatch[0]["effect"]
    assert "Add a converter rail" in mismatch[0]["effect"]

    boosted = _robot(
        [SensorProfile(name="imaging_sonar", catalog="tritech-gemini-720is", rail="24V")],
        [RailProfile("24V", output_V=24.0)],
    )
    _, report = _run(boosted)
    assert not [
        w for w in report.evidence["scientific_warnings"] if w["kind"] == "supply_domain_mismatch"
    ]

    wrong = _robot(
        [SensorProfile(name="imaging_sonar", catalog="tritech-gemini-720is", rail="5V")],
        [RailProfile("5V", output_V=5.0)],
    )
    _, report = _run(wrong)
    effects = [w["effect"] for w in report.evidence["scientific_warnings"]]
    assert any("rail 5V supplies 5 V" in e for e in effects)


def test_direct_rail_has_no_conversion_loss_and_needs_no_converter_evidence():
    _, report = _run(_robot(_loads("pack", "pack"), [RailProfile("pack", kind="direct")]))
    assert report.intervals["rail_verified"]["pack"] is True
    assert report.category_energy_Wh["converters"] == pytest.approx(0.0, abs=1e-15)


def test_unconfigured_rail_name_and_reserved_names_are_rejected():
    with pytest.raises(ConfigurationError, match="not configured"):
        _run(_robot(_loads("5V", "5V"), []))
    with pytest.raises(ConfigurationError, match="reserved"):
        _run(_robot(_loads(), [RailProfile("payload", output_V=5.0)]))
    with pytest.raises(ConfigurationError, match="direct rail"):
        _run(_robot(_loads(), [RailProfile("5V", kind="direct", output_V=5.0)]))


def test_comparison_is_not_supported_when_the_differing_rail_has_no_converter_evidence():
    rails_a = [RailProfile("5V", output_V=5.0, efficiency=0.9)]
    rails_b = [RailProfile("5V", output_V=5.0, efficiency=0.95)]
    _, a = _run(_robot(_loads(), rails_a))
    _, b = _run(_robot(_loads(), rails_b))
    # Nominally B draws less from the bus, but neither efficiency has evidence.
    assert b.terminal_energy_Wh < a.terminal_energy_Wh
    result = compare_energy(b.to_dict(), a.to_dict())
    assert result.verdict == "RANKING_NOT_SUPPORTED"
