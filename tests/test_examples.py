import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(
    "script,expected",
    [
        ("bluerov2_energy_demo.py", "Mean power:"),
        ("bluerov2_sensor_payload_demo.py", "Difference:"),
    ],
)
def test_synthetic_examples(script, expected, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / script),
            "--backend",
            "synthetic",
            "--steps",
            "12",
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert expected in result.stdout and "Backend: synthetic" in result.stdout


@pytest.mark.skipif(
    importlib.util.find_spec("holoocean") is not None,
    reason="Do not launch installed simulator in unit tests",
)
def test_missing_holoocean_fails_clearly(tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples/bluerov2_energy_demo.py"),
            "--output-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode != 0
    assert "HoloOcean is not installed" in result.stderr
    assert "Backend: synthetic" not in result.stdout


def example_common():
    spec = importlib.util.spec_from_file_location(
        "energy_example_common", ROOT / "examples/_common.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_native_backend_resets_and_sets_simulated_timing(monkeypatch, tmp_path):
    common = example_common()
    scenario = {
        "package_name": "Ocean",
        "world": "SimpleUnderwater",
        "agents": [{"agent_type": "BlueROV2", "agent_name": "rov0", "control_scheme": 0}],
    }
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps(scenario))
    calls = []

    class NativeBackend:
        def reset(self):
            calls.append("reset")

    def make(**kwargs):
        calls.append(kwargs)
        return NativeBackend()

    monkeypatch.setitem(sys.modules, "holoocean", SimpleNamespace(make=make))
    args = SimpleNamespace(backend="holoocean", scenario=path, show_viewport=False)
    env, contract = common.backend(args, {"simulation": {"dt_s": 0.05}})
    assert isinstance(env, NativeBackend)
    assert calls[1] == "reset"
    assert calls[0]["ticks_per_sec"] == 20
    assert calls[0]["frames_per_sec"] is False
    assert calls[0]["show_viewport"] is False
    assert calls[0]["scenario_cfg"]["ticks_per_sec"] == 20
    assert contract["agent_name"] == "rov0"
    assert json.loads(path.read_text()) == scenario


def test_native_backend_closes_when_reset_fails(monkeypatch, tmp_path):
    common = example_common()
    path = tmp_path / "scenario.json"
    path.write_text(json.dumps({"agents": [{"agent_type": "BlueROV2", "agent_name": "rov0"}]}))

    class NativeBackend:
        exited = False

        def reset(self):
            raise RuntimeError("initialization failed")

        def __exit__(self, *args):
            self.exited = True

    env = NativeBackend()
    monkeypatch.setitem(sys.modules, "holoocean", SimpleNamespace(make=lambda **kwargs: env))
    args = SimpleNamespace(backend="holoocean", scenario=path, show_viewport=False)
    with pytest.raises(RuntimeError, match="initialization failed"):
        common.backend(args, {"simulation": {"dt_s": 0.05}})
    assert env.exited
