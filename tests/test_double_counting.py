"""Double-counting audit (docs/double_counting_policy.md): one electrical load per function."""

import warnings

import pytest

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.catalog import modem_profile
from holoenergy.integrations import ModemPowerProfile
from holoenergy.integrations.desert import DesertEnergyAdapter

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


def make(components=(), evidence=None):
    warnings.simplefilter("ignore", UserWarning)
    overrides = {"logging": {"enabled": False}}
    if evidence:
        overrides["evidence"] = evidence
    return EnergyAwareEnv(
        Backend(),
        vehicle_profile="bluerov2-heavy",
        control_contract=CONTRACT,
        components=list(components),
        overrides=overrides,
    )


def double_counts(env):
    return [w for w in env.warnings if "double counting" in w]


def test_navigator_plus_separate_imu_magnetometer_is_flagged():
    env = make(["vectornav-vn100-rugged"])
    found = double_counts(env)
    assert any("'imu'" in w for w in found) and any("'magnetometer'" in w for w in found)
    env.close()


def test_integrated_ins_dvl_plus_standalone_dvl_is_flagged():
    env = make(["sonardyne-sprint-nav-mini", "waterlinked-dvl-a50"])
    assert any("'dvl'" in w for w in double_counts(env))
    env.close()


def test_semantic_camera_is_not_an_electrical_load():
    """Semantic segmentation = physical camera + compute workload, never a third load."""
    with pytest.raises(ConfigurationError, match="derived semantic output"):
        make(
            [
                {
                    "name": "segmentation_camera",
                    "category": "sensors",
                    "simulation_sensor": "SemanticSegmentationCamera",
                    "active_W": 3.0,
                }
            ]
        )
    env = make(["jetson-orin-nx-16gb"])  # camera (profile) + AI computer: no overlap
    assert double_counts(env) == []
    env.close()


def test_modem_internal_processing_plus_separate_compute_is_flagged():
    sdr = {
        "name": "modem_dsp_on_companion",
        "category": "compute",
        "includes": ["modem_signal_processing"],
        "active_W": 2.0,
        "metadata": {"status": "USER-SUPPLIED"},
    }
    env = make([sdr])
    assert double_counts(env) == []
    profile = ModemPowerProfile.from_mapping(modem_profile("evologics-s2cm-18-34-1000m"))
    assert profile.includes == ("modem_signal_processing",)
    adapter = DesertEnergyAdapter({"acoustic": profile}, node="auv_01", node_map={"auv_01": 1})
    env.attach(adapter)
    assert any("'modem_signal_processing'" in w for w in double_counts(env))
    env.close()


def test_double_counting_can_be_rejected():
    with pytest.raises(ConfigurationError, match="double counting rejected"):
        make(["vectornav-vn100-rugged"], evidence={"double_counting": "error"})
    with pytest.raises(ConfigurationError, match="warn or error"):
        make(evidence={"double_counting": "ignore"})
    env = make(
        [
            {
                "name": "dsp",
                "category": "compute",
                "includes": ["modem_signal_processing"],
                "active_W": 1,
            }
        ],
        evidence={"double_counting": "error"},
    )
    profile = ModemPowerProfile.from_mapping(modem_profile("evologics-s2cm-18-34-1000m"))
    adapter = DesertEnergyAdapter({"acoustic": profile}, node="auv_01", node_map={"auv_01": 1})
    with pytest.raises(ConfigurationError, match="double counting rejected"):
        env.attach(adapter)
    assert adapter not in env.load_sources
    env.close()
