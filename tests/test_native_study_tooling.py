"""Native study/demo/campaign helpers that run without Unreal or numpy."""

import importlib.util
import math
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


study = load("native_study", "examples/native_current_energy_study.py")
demo = load("before_after_demo", "examples/holoocean_before_after_demo.py")
campaign = load("campaign_runner", "tools/run_verified_backend_campaign.py")


def test_mission_plan_returns_home_with_a_half_turn():
    dt = 0.01
    plan = study.mission_plan(dt)
    assert len(plan) == round(67 / dt)
    displacement = sum(item["speed"] for item in plan) * dt
    assert displacement == pytest.approx(0.0, abs=1e-9)
    outbound = sum(item["speed"] for item in plan if item["speed"] > 0) * dt
    assert outbound == pytest.approx(study.TRANSIT_SPEED_M_S * 20, rel=1e-3)
    assert plan[-1]["yaw"] == pytest.approx(math.pi)
    yaw = [item for item in plan if item["phase"] == "yaw"]
    assert sum(item["yaw_rate"] for item in yaw) * dt == pytest.approx(math.pi, rel=1e-3)
    assert max(abs(item["speed"]) for item in plan) == study.TRANSIT_SPEED_M_S
    assert [p for p in dict.fromkeys(item["phase"] for item in plan)] == [
        "hold_start",
        "accelerate",
        "transit_out",
        "stop",
        "hold_turn",
        "yaw",
        "return_accelerate",
        "return_transit",
        "return_stop",
        "hold_end",
    ]


def test_smooth_ramp_is_bounded_and_monotone():
    values = [study.smooth_ramp(i / 20) for i in range(-2, 23)]
    assert values[0] == 0 and values[-1] == 1
    assert all(b >= a for a, b in zip(values, values[1:], strict=False))


def test_demo_drag_uses_relative_velocity_and_audited_scale():
    trace = [
        {"velocity_m_s": [0.0, 0.0, 0.0], "current_m_s": [0.4, 0.0, 0.0]},
        {"velocity_m_s": [0.4, 0.0, 0.0], "current_m_s": [0.4, 0.0, 0.0]},
    ]
    after = demo.implementation_drag_N(trace, demo.BUILD_DRAG_SCALE["after"])
    before = demo.implementation_drag_N(trace, demo.BUILD_DRAG_SCALE["before"])
    assert after[0] == pytest.approx(0.5 * 997 * 0.8 * 0.45 * 0.16)
    assert after[1] == 0.0
    assert before[0] == pytest.approx(after[0] / 100)


def test_campaign_runs_every_build_through_the_same_tools(tmp_path):
    args = SimpleNamespace(
        python="py",
        original_binary=Path("orig.exe"),
        rebuilt_binary=Path("rebuilt.exe"),
        patched_binary=Path("patched.exe"),
        before_source=Path("src_before"),
        after_source=Path("src_after"),
        output_root=tmp_path,
        steps=campaign.STEPS,
    )
    plan = campaign.commands(args)
    drag = [c for s, b, c in plan if s == "drag"]
    assert len(drag) == 3
    assert all("--repeats" in c and c[c.index("--repeats") + 1] == "3" for c in drag)
    assert all(
        c[c.index("--ticks-per-sec") + 1 : c.index("--ticks-per-sec") + 4] == ["60", "100", "200"]
        for c in drag
    )
    patched = [c for s, b, c in plan if s == "drag" and b == "patched"][0]
    assert patched[patched.index("--source-dir") + 1] == "src_after"
    assert {b for s, b, c in plan if s == "timestep"} == {"original", "rebuilt", "patched"}
    args.steps = ["check"]
    assert {s for s, _, _ in campaign.commands(args)} == {"check"}


def test_study_applies_the_current_natively(tmp_path, monkeypatch):
    np = pytest.importorskip("numpy")
    calls = []

    class FakeSpace:
        shape = (8,)

        def get_low(self):
            return -28.75

        def get_high(self):
            return 28.75

    class FakeNative:
        action_space = FakeSpace()

        def reset(self):
            return self.step(np.zeros(8))

        def step(self, action, **kwargs):
            pose = np.eye(4)
            return {
                "PoseSensor": pose,
                "VelocitySensor": np.zeros(3),
                "DynamicsSensor": np.zeros(18),
            }

        def set_ocean_currents(self, name, velocity):
            calls.append((name, list(velocity)))

        def close(self):
            pass

    contract = {
        "agent_type": "BlueROV2",
        "control_scheme": 0,
        "action_units": "force_N",
        "thruster_count": 8,
        "dt_s": 0.01,
        "agent_name": "rov0",
    }
    monkeypatch.setattr(study, "backend", lambda args, config: (FakeNative(), contract))
    args = SimpleNamespace(
        backend="holoocean",
        dt=None,
        holoocean_binary=None,
        scenario=ROOT / "configs/bluerov2_realtime_holoocean.json",
        config=ROOT / "configs/bluerov2_energy.yaml",
        steps=1,
        output_dir=tmp_path,
        log_format="jsonl",
    )
    baseline = study.settings(args)
    plan = [{"phase": "station_keeping", "speed": 0.0, "yaw": 0.0, "yaw_rate": 0.0}] * 3
    trace, summary, config = study.run(args, baseline, "fake", [0.3, 0, 0], plan)
    assert calls == [("rov0", [0.3, 0.0, 0.0])]
    assert config["simulation"]["dt_s"] == 0.01
    assert len(trace) == 3 and trace[-1]["current_m_s"] == [0.3, 0, 0]
