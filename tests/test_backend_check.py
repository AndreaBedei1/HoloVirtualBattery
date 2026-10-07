"""Backend smoke-test verdicts: verification only, never compensation."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load("backend_check", "tools/check_holoocean_backend.py")


def test_backend_check_verdicts_never_compensate():
    assert check.verdict(1.0000002)[0] == "PASS"
    status, detail = check.verdict(0.0099999997)
    assert status == "FAIL" and "unpatched HoloOcean 2.3.0" in detail
    assert check.verdict(0.5)[0] == "FAIL"
    assert check.scale([2.0, 0.0, 0.0], [1.0, 0.0, 0.0]) == 2.0


def test_backend_check_summary_line():
    assert check.summary("PASS", "PASS", (1.0, 1.0000002)) == "PASS"
    assert check.summary("FAIL", "PASS", (0.0099999995, 0.0100004)) == (
        "FAIL: detected ~0.01 drag scaling associated with unpatched HoloOcean 2.3.0"
    )
    assert check.summary("FAIL", "PASS", (0.5, 0.5)).startswith("FAIL: drag FAIL")
    assert check.summary("PASS", "FAIL", (1.0, 1.0)).startswith("FAIL: drag PASS")
    assert check.summary("INCONCLUSIVE", "FAIL", (0.0067, 0.0067)).startswith("INCONCLUSIVE")
