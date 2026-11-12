"""Literature-proxy energy profiles for the non-BlueROV2 HoloOcean 2.3.0 agent classes."""

import json
import math
import re
import warnings
from importlib.resources import files

import pytest
import yaml

from holoenergy import EnergyAwareEnv
from holoenergy._validation import ConfigurationError
from holoenergy.analysis.replay import ReplayBackend
from holoenergy.catalog import VEHICLES, vehicle_config
from holoenergy.config import load_config, model_warnings
from holoenergy.evidence import GRADES, default_registry
from holoenergy.models.actuator import make_actuator
from holoenergy.models.battery import EnergyBucketBattery

PROXIES = {
    "hovering-mares-like": "HoveringAUV",
    "torpedo-remus-like": "TorpedoAUV",
    "torpedo-tethys-like": "TorpedoAUV",
    "torpedo-autosub-like": "TorpedoAUV",
}
DROPPED = {
    "hovering-amour-like": "amour_v.thruster_force_power",
    "surface-dual-electric": "dual_electric_usv.thruster_force_power",
    "surface-silver-frog-like": "silver_frog.thruster_force_power",
}
SIMULATOR_PREFIX = "holoocean_"


def _load(name):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return load_config(data=vehicle_config(name))


def _raw_vehicle(name):
    path = files("holoenergy").joinpath("profiles", *VEHICLES[name]["file"].split("/"))
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _proxy_records():
    path = files("holoenergy").joinpath("evidence", "data", "parameters", "proxy_vehicles.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))["parameters"]


def _linked_records(config):
    """Every evidence record id an electrical quantity of the profile is linked to."""
    ids = [config["evidence"]["propulsion"]["record"]]
    ids += list(config["battery"]["metadata"]["evidence"].values())
    for component in config.get("components", []):
        ids += [s["evidence"] for s in component["states"].values() if isinstance(s, dict)]
    return ids


def _worse_or_equal(grade, limit):
    return GRADES.index(grade) >= GRADES.index(limit)


@pytest.mark.parametrize("name", sorted(PROXIES))
def test_proxy_profile_is_registered_and_loads(name):
    assert VEHICLES[name]["relation"] == "proxy"
    config = _load(name)
    agent_type = PROXIES[name]
    assert config["simulation"]["expected_agent_type"] == agent_type
    assert config["evidence"]["vehicle_relation"] == "proxy"
    assert config["evidence"]["propulsion"]["relation"] == "proxy"
    # Physical mass/drag stay simulator-owned: the profile does not redefine them.
    assert not {"mass_kg", "volume_m3"} & set(config["vehicle"])
    agents = json.loads(
        files("holoenergy").joinpath("profiles", "holoocean", "agents_2.3.0.json").read_text()
    )["agents"][agent_type]
    assert config["propulsion"]["thruster_count"] == agents["actuator_count"]
    geometry = config["actuation"]["geometry"]
    for mount, native in zip(geometry, agents["actuators"], strict=True):
        assert mount["position_m"] == pytest.approx(native["position_m"])
        assert mount["direction"] == pytest.approx(native["direction"], abs=1e-9)
    assert config["actuation"]["backend"]["backend_index"] == [
        a["backend_index"] for a in agents["actuators"]
    ]
    assert config["actuation"]["backend"]["native_clamp_N"] == agents["per_thruster_clamp_N"]


@pytest.mark.parametrize("name", sorted(PROXIES))
def test_proxy_linked_evidence_is_at_most_grade_c(name):
    config = _load(name)
    registry = default_registry()
    for record_id in _linked_records(config):
        record = registry.get(record_id)
        assert _worse_or_equal(record.grade, "C"), record_id
        assert record.relation in ("proxy", "unsupported"), record_id
    for component in config["components"]:
        assert component["relation"] == "proxy"


def test_proxy_records_never_exceed_c_and_gaps_stay_null():
    records = _proxy_records()
    registry = default_registry()
    assert len({r["id"] for r in records}) == len(records)
    for raw in records:
        record = registry.get(raw["id"])
        if record.id.startswith(SIMULATOR_PREFIX):
            continue  # simulator-exact HoloOcean constants, not literature proxies
        assert record.relation in ("proxy", "unsupported"), record.id
        assert _worse_or_equal(record.grade, "C"), record.id
        if not record.configured:
            assert record.value is None and record.grade == "D", record.id
            assert raw.get("value") is None, record.id
        else:
            assert record.sources, record.id
            assert record.location, record.id


@pytest.mark.parametrize("name", sorted(PROXIES))
def test_unconfigured_battery_limit_stays_null(name):
    config = _load(name)
    battery = config["battery"]
    assert battery["model"] == "energy_bucket"
    assert battery["max_power_W"] is None and "max_current_A" not in battery
    record = default_registry().get(battery["metadata"]["evidence"]["max_power_W"])
    assert not record.configured and record.value is None and record.grade == "D"
    assert any("battery power/current limit is unpublished" in w for w in model_warnings(config))


@pytest.mark.parametrize("name", sorted(PROXIES))
def test_metadata_never_claims_validation(name):
    raw = _raw_vehicle(name)
    text = json.dumps(raw["metadata"]).lower()
    for match in re.finditer(r"validated", text):
        assert re.search(
            r"\b(not|never)\b[\w\s]{0,4}$", text[max(0, match.start() - 8) : match.start()]
        ), (
            name,
            text[max(0, match.start() - 40) : match.end()],
        )
    statement = raw["metadata"]["proxy_statement"]
    assert "literature proxy" in statement and f"generic HoloOcean {PROXIES[name]}" in statement
    for field in (
        "relation_to_holoocean_agent",
        "exact_or_proxy",
        "propulsion_electrical_model",
        "battery",
        "hotel_load",
        "evidence_sources",
        "known_gaps",
        "validity_range",
    ):
        assert raw["metadata"].get(field), (name, field)


@pytest.mark.parametrize("name", sorted(PROXIES))
def test_replay_smoke_step_is_graded_c(name):
    config = _load(name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        env = EnergyAwareEnv(ReplayBackend(config), config=config)
    with env:
        count = env.propulsion.count
        row = env.step([2.0] * count)["Energy"]
        assert row["power_total_W"] > 0
        summary = env.energy.summary()
        assert summary["duration_s"] > 0
        shares = summary["evidence"]["share_percent"]
        assert shares["A"] == 0 and shares["B"] == 0
        assert shares["C"] == pytest.approx(100, abs=1e-6)


@pytest.mark.parametrize("name", [n for n, t in PROXIES.items() if t == "TorpedoAUV"])
def test_torpedo_proxies_have_no_reverse_domain(name):
    config = _load(name)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        env = EnergyAwareEnv(ReplayBackend(config), config=config)
    with env:
        hotel = env.step([0.0])["Energy"]["power_total_W"]
        reverse = env.step([-5.0])["Energy"]["power_total_W"]
        assert reverse == pytest.approx(hotel)


def test_forward_only_force_power_table():
    model = make_actuator(
        {
            "model": "fwd",
            "force_power_tables": [
                {"voltage_V": 24, "forward": [[0, 0], [10, 20]], "reverse": None}
            ],
        }
    )
    assert model.max_force(24, "reverse") == 0 and model.max_force(24, "forward") == 10
    assert model.power(5, 24) == pytest.approx(10)
    with pytest.raises(ValueError, match="domain"):
        model.power(-1, 24)
    with pytest.raises(ConfigurationError, match="reverse"):
        make_actuator(
            {"model": "x", "force_power_tables": [{"voltage_V": 24, "forward": [[0, 0], [1, 1]]}]}
        )


def test_null_battery_limit_is_explicit_only():
    base = {"model": "energy_bucket", "capacity_Wh": 10, "nominal_voltage_V": 24, "initial_soc": 1}
    with pytest.raises(ConfigurationError, match="max_current_A"):
        EnergyBucketBattery(base)
    battery = EnergyBucketBattery({**base, "max_power_W": None})
    assert battery.limit_unconfigured and math.isinf(battery.max_current_A)
    assert battery.available_power(25, 3600) == pytest.approx(10)


def test_tables_reproduce_recorded_derivations():
    registry = default_registry()

    def table(name):
        return _load(name)["propulsion"]["thruster"]["force_power_tables"][0]["forward"]

    mares = table("hovering-mares-like")
    assert mares[-1][0] == registry.get("mares.thruster_force_domain").value
    assert mares[-1][1] == pytest.approx(5 * mares[-1][0])
    thrust = registry.get("remus.propeller_design_thrust_4p5kn").si()
    remus = table("torpedo-remus-like")
    for (force, power), speed_kn, record in ((remus[1], 3.0, "3kn"), (remus[2], 5.6, "5p6kn")):
        assert force == pytest.approx(thrust * (speed_kn / 4.5) ** 2, rel=1e-3)
        assert power == registry.get(f"remus.propulsion_power_{record}").value
    assert table("torpedo-tethys-like")[-1] == [
        7.0,
        registry.get("tethys.propulsion_power_level_flight").value,
    ]
    drag = (
        0.5
        * 1025
        * registry.get("alr6000.volumetric_drag_coefficient").value
        * registry.get("alr6000.hydrodynamic_displacement").value ** (2 / 3)
    )
    coefficient = registry.get("alr6000.propulsion_power_fit").value
    rows = table("torpedo-autosub-like")[1:]
    for (force, power), speed in zip(rows, (0.4, 0.5, 0.6, 0.7, 0.8), strict=True):
        assert force == pytest.approx(drag * speed**2, rel=1e-3)
        assert power == pytest.approx(coefficient * speed**2.4333, rel=1e-3)


def test_dropped_profiles_are_documented_gaps():
    registry = default_registry()
    for name, record_id in DROPPED.items():
        assert name not in VEHICLES
        record = registry.get(record_id)
        assert not record.configured and record.value is None and record.grade == "D"
        assert record.notes and "not built" in record.notes
