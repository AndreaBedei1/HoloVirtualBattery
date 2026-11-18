"""Evidence-aware requirement assessment and the open sides it depends on (review I-02, D-09)."""

import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
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
    assert "conversion treated as verified for: hotel, payload" in assessment.assumptions
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
    a, b = run(components=[oculus()]), run(components=[oculus()])
    result = compare_energy(a, b)
    assert result.verdict == "RANKING_NOT_SUPPORTED"
    assert result.differing == ()


def test_unknown_contributions_never_cancel():
    """Adversarial C3: an unknown load (here the sonar's unmodelled supply conversion) has
    unknown energy in both runs, so it cannot cancel and blocks a supported ranking."""
    a, b = run(components=[sonar()]), run(components=[sonar()])
    result = compare_energy(a, b)
    assert ("imaging_sonar.supply_conversion", "unknown") in result.differing
    assert result.verdict == "RANKING_NOT_SUPPORTED"


def test_b_lower_path_and_difference_bounds():
    scan, gemini = run(components=[ping360()]), run(components=[sonar()])
    result = compare_energy(gemini, scan)
    assert result.verdict == "B_LOWER_SUPPORTED"
    assert result.difference_low_Wh is not None and result.difference_low_Wh > 0
    assert result.difference_high_Wh is None  # the Gemini's conversion loss is unbounded


def test_open_low_items_are_removed_from_the_supported_lower_bound():
    report = run(components=[ping360()])
    a = assess_energy_requirement(report, max_energy_wh=1.0)
    ping = sum(report.device_state_energy_Wh["scanning_sonar"].values())
    assert "scanning_sonar.ACTIVE" in a.open_low
    assert a.supported_low_Wh <= report.intervals["terminal_energy_Wh"]["low"] - ping + 1e-12


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


def _rep(rows, verified, open_high=(), unknown=()):
    """Minimal report dict (review R4 probes)."""
    nominal = sum(r["energy_Wh"] * r["scale"] for r in rows)
    return {
        "intervals": {
            "terminal_energy_Wh": {
                "nominal": nominal,
                "low": nominal,
                "high": nominal,
                "open_low": [],
                "open_high": list(open_high),
                "unknown_contributions": list(unknown),
            },
            "contributions": rows,
            "point_contributions": [],
            "open_contributions": [],
            "rail_verified": verified,
        },
        "evidence": {},
    }


def _row(dev, energy, ratio=(1.0, 1.0), scale=1.0):
    return {
        "device": dev,
        "state": "ACTIVE",
        "energy_Wh": energy,
        "ratio": ratio,
        "scale": scale,
        "rail": "payload",
        "record": "r",
    }


def test_placeholder_efficiency_is_not_part_of_the_lower_bound():
    """R4-01: efficiency 0.5 configured without evidence; the true scale may be 1."""
    report = _rep(
        [_row("dvl", 1.0, scale=2.0)],
        {"payload": False},
        open_high=["conversion:payload"],
        unknown=["conversion:payload"],
    )
    assessment = assess_energy_requirement(report, 1.5)
    assert assessment.supported_low_Wh == pytest.approx(1.0)
    assert assessment.verdict == "INDETERMINATE"


def test_identical_load_does_not_cancel_when_only_one_rail_is_verified():
    """R4-02: the same DVL energy, but A's rail scale is unknown (s >= 1, unbounded)."""
    a = _rep([_row("dvl", 1.0)], {"payload": False})
    b = _rep([_row("dvl", 1.0), _row("sonar", 0.5, ratio=(0.8, 1.2))], {"payload": True})
    assert compare_energy(a, b).verdict == "RANKING_NOT_SUPPORTED"


def test_shared_unverified_rail_keeps_the_sign():
    lower = compare_energy(
        _rep([_row("x", 0.9)], {"payload": False}), _rep([_row("y", 1.0)], {"payload": False})
    )
    higher = compare_energy(
        _rep([_row("x", 1.1)], {"payload": False}), _rep([_row("y", 1.0)], {"payload": False})
    )
    assert lower.verdict == "A_LOWER_SUPPORTED" and higher.verdict == "B_LOWER_SUPPORTED"


@pytest.mark.parametrize("bad", ["payload", ("payloads",), ("Payload",)])
def test_assume_verified_is_validated(bad):
    """R4-03: a bare string or a typo must not be silently accepted."""
    report = _rep(
        [_row("dvl", 1.0)], {"payload": False}, ["conversion:payload"], ["conversion:payload"]
    )
    with pytest.raises(ConfigurationError):
        assess_energy_requirement(report, 10.0, assume_verified=bad)
