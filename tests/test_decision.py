"""Evidence-aware requirement assessment and the open sides it depends on (review I-02, D-09)."""

import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy.catalog import profile_reference, vehicle_config
from holoenergy.config import load_config
from holoenergy.decision import assess_energy_requirement, compare_energy

CONTRACT = {
    "agent_type": "BlueROV2",
    "control_scheme": 0,
    "action_units": "force_N",
    "thruster_count": 8,
    "dt_s": 0.01,
}


class Backend:
    def step(self, action):
        return {}

    def reset(self):
        return {}

    def close(self):
        pass


def run(components=None, converters=None, steps=300):
    warnings.simplefilter("ignore", UserWarning)
    data = load_config(data=vehicle_config("bluerov2-heavy"))
    if components is not None:
        data["components"] = components
    if converters is not None:
        data["converters"] = converters
    env = EnergyAwareEnv(Backend(), config=data, control_contract=CONTRACT)
    for _ in range(steps):
        env.step([0, 0, 0, 0, 5.0, 5.0, 5.0, 5.0])
    report = env.energy.report()
    env.close()
    return report


def sonar():
    return {"profile": profile_reference("tritech-gemini-720is", "component")}


def test_supply_domain_mismatch_is_a_structured_warning_and_opens_the_upper_side():
    report = run(components=[sonar()])
    kinds = {(w["kind"], w["subject"]) for w in report.evidence["scientific_warnings"]}
    assert ("supply_domain_mismatch", "imaging_sonar") in kinds
    assert "imaging_sonar.supply_conversion" in report.intervals["terminal_energy_Wh"]["open_high"]


def test_declared_converter_component_closes_the_supply_gap():
    converter = {
        "name": "sonar_boost",
        "category": "auxiliaries",
        "states": {"ACTIVE": {"power_W": 2.0}},
        "serves": ["imaging_sonar"],
    }
    report = run(components=[sonar(), converter])
    kinds = {w["kind"] for w in report.evidence["scientific_warnings"]}
    assert "supply_domain_mismatch" not in kinds
    assert (
        "imaging_sonar.supply_conversion" not in report.intervals["terminal_energy_Wh"]["open_high"]
    )


def test_unverified_payload_conversion_opens_the_upper_side():
    report = run()
    open_high = report.intervals["terminal_energy_Wh"]["open_high"]
    assert "conversion:payload" in open_high
    assert any(w["kind"] == "conversion_unverified" for w in report.evidence["scientific_warnings"])


def test_assessment_distinguishes_nominal_supported_and_indeterminate():
    report = run()
    nominal = report.intervals["terminal_energy_Wh"]["nominal"]
    generous = assess_energy_requirement(report, max_energy_wh=10 * nominal)
    # The payload rail has no converter evidence, so a pass cannot be certified.
    assert generous.nominal_pass and generous.verdict == "INDETERMINATE"
    assert "conversion:payload" in generous.open_high
    tight = assess_energy_requirement(report, max_energy_wh=0.1 * nominal)
    # The supported lower bound already exceeds the limit: a certified failure.
    assert not tight.nominal_pass and tight.verdict == "SUPPORTED_FAIL"


def test_assessment_passes_when_every_contribution_is_bounded():
    report = run(components=[], converters={"payload_efficiency": 1.0})
    assessment = assess_energy_requirement(
        report, max_energy_wh=10 * report.terminal_energy_Wh, assume_verified=("payload", "hotel")
    )
    assert assessment.verdict == "SUPPORTED_PASS"
    assert assessment.supported_high_Wh is not None
    assert assessment.dynamics == "excluded: propulsion follows the simulator's dynamics"


def test_assessment_propagates_a_dynamics_factor_range():
    report = run(components=[], converters={"payload_efficiency": 1.0})
    base = assess_energy_requirement(
        report, max_energy_wh=1.0, assume_verified=("payload", "hotel")
    )
    wide = assess_energy_requirement(
        report,
        max_energy_wh=1.0,
        assume_verified=("payload", "hotel"),
        propulsion_factor_range=(0.5, 2.0),
    )
    propulsion = report.category_energy_Wh["propulsion"]
    assert wide.supported_high_Wh == pytest.approx(base.supported_high_Wh + propulsion)
    assert wide.supported_low_Wh == pytest.approx(base.supported_low_Wh - 0.5 * propulsion)
    assert "propulsion factor" in wide.dynamics


def oculus():
    return {
        "name": "imaging_sonar",
        "device": "blueprint_oculus_m750d",
        "category": "sensors",
        "relation": "representative",
        "states": {
            "ACTIVE": {"evidence": "blueprint_oculus_m750d.power_range", "use": "value_max"}
        },
        "initial_state": "ACTIVE",
    }


def ping360():
    return {"profile": profile_reference("bluerobotics-ping360", "component")}


def test_paired_comparison_cancels_identical_contributions():
    a, b = run(components=[sonar()]), run(components=[sonar()])
    result = compare_energy(a, b)
    assert result.verdict == "RANKING_NOT_SUPPORTED"
    assert result.differing == ()


def test_published_ranges_decide_or_withhold_a_ranking():
    gemini, oc, scan = (
        run(components=[sonar()]),
        run(components=[oculus()]),
        run(components=[ping360()]),
    )
    # Ping360 (<= 5 W) is below the Gemini's published minimum (16 W): supported.
    assert compare_energy(scan, gemini).verdict == "A_LOWER_SUPPORTED"
    # Gemini [16, 27] W (+ unmodelled step-up loss) vs Oculus family [10, 35] W: the nominal
    # values (27 vs 35 W) favour the Gemini, the evidence does not.
    nominal_favours_gemini = gemini.terminal_energy_Wh < oc.terminal_energy_Wh
    assert nominal_favours_gemini
    assert compare_energy(gemini, oc).verdict == "RANKING_NOT_SUPPORTED"


def test_attached_modem_states_are_bounded_by_their_records():
    """Integration review: an attached modem's record ids must reach the intervals, otherwise any
    requirement with a modem is forced INDETERMINATE."""
    from holoenergy.catalog import modem_profile
    from holoenergy.integrations import ModemPowerProfile
    from holoenergy.integrations.communications import CommunicationEnergyAdapter

    warnings.simplefilter("ignore", UserWarning)
    data = load_config(data=vehicle_config("bluerov2-heavy"))
    data["components"] = []
    env = EnergyAwareEnv(Backend(), config=data, control_contract=CONTRACT)
    profile = ModemPowerProfile.from_mapping(
        modem_profile("evologics-s2cm-18-34-1000m"), registry=env.evidence_registry
    )
    adapter = CommunicationEnergyAdapter({"acoustic": profile}, name="comms")
    env.attach(adapter)
    adapter.ledger("acoustic").add_tx(0.5, 0.4, bits=1920)
    for _ in range(300):
        env.step([0, 0, 0, 0, 5.0, 5.0, 5.0, 5.0])
    report = env.energy.report()
    env.close()
    rows = {(r["device"], r["state"]) for r in report.intervals["contributions"]}
    assert ("comms.acoustic", "TX") in rows and ("comms.acoustic", "LISTEN") in rows
    open_high = report.intervals["terminal_energy_Wh"]["open_high"]
    assert not any(x.startswith("comms.acoustic") for x in open_high)
    # TX at 2.8 W is exact; LISTEN at the 0.8 W upper bound opens only the lower side.
    assert "comms.acoustic.LISTEN" in report.intervals["terminal_energy_Wh"]["open_low"]
