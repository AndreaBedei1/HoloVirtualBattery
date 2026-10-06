import importlib.util
import subprocess
import sys
from pathlib import Path

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
