"""Browser tests of the web application (Playwright, headless Chromium).

They drive the real server and the real Python API. They are skipped when Playwright or its
browser is not installed (``pip install playwright && python -m playwright install chromium``).
The GUI-API consistency test checks that a run launched from the browser saves exactly the
report the Python API produces for the same robot and mission documents.
"""

import copy
import json
import urllib.request

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from holoenergy.config import load_config  # noqa: E402
from holoenergy.dashboard.api import DEFAULT_MISSION, TEMPLATES  # noqa: E402
from holoenergy.dashboard.server import DashboardServer  # noqa: E402
from holoenergy.mission import Mission, run_scenario  # noqa: E402

ROUTES = ("overview", "robot", "mission", "run", "results", "compare", "library", "evidence")
OVERFLOW_JS = "document.documentElement.scrollWidth - document.documentElement.clientWidth"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    with DashboardServer(0, 0, runs_dir=tmp_path_factory.mktemp("runs")) as srv:
        yield srv


@pytest.fixture(scope="module")
def browser():
    with playwright.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # noqa: BLE001
            pytest.skip(f"Chromium for Playwright is not installed: {exc}")
        yield b
        b.close()


def _page(browser, server, width=1280, robot=None, mission=None):
    page = browser.new_page(viewport={"width": width, "height": 900}, bypass_csp=True)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(server.url)
    page.evaluate("localStorage.clear()")
    if robot is not None:
        page.evaluate("r => localStorage.setItem('he.robot', JSON.stringify(r))", robot)
    if mission is not None:
        page.evaluate("m => localStorage.setItem('he.mission', JSON.stringify(m))", mission)
    page.goto(server.url + "#/overview")
    page.wait_for_selector("h1:has-text('Overview')")
    return page, errors


def _go(page, route):
    page.click(f"nav.tabs a[href='#/{route}']")
    page.wait_for_function(f"document.title.startsWith('{route[0].upper() + route[1:]}')")


def test_every_section_renders_without_script_errors(browser, server):
    page, errors = _page(browser, server)
    for route in ROUTES:
        _go(page, route)
        assert page.locator("h1").first.is_visible()
        assert page.locator(f"nav.tabs a[href='#/{route}'][aria-current='page']").count() == 1
    assert errors == []
    page.close()


def test_robot_builder_adds_library_and_custom_hardware_with_provenance(browser, server):
    page, errors = _page(browser, server)
    _go(page, "robot")
    before = page.locator("[data-del-comp]").count()
    page.select_option("#add-comp", "blueprint-oculus-m750d")
    page.wait_for_function(f"document.querySelectorAll('[data-del-comp]').length === {before + 1}")
    assert page.get_by_text("Blueprint Subsea Oculus M750d", exact=True).is_visible()
    page.click("#add-custom")
    page.fill("#c-name", "lab_winch")
    page.select_option("#c-cat", "auxiliaries")
    page.fill("#c-power", "12.5")
    page.select_option("#c-src", "measurement")
    page.fill("#c-cite", "Bench notebook 7, p. 3")
    page.click("#c-ok")
    page.wait_for_selector("text=Added lab_winch (grade A)")
    robot = page.evaluate("JSON.parse(localStorage.getItem('he.robot'))")
    names = [c["name"] for c in robot["components"]]
    assert "lab_winch" in names and "imaging_sonar_oculus" in names
    assert robot["evidence"]["records"][-1]["grade"] == "A"
    assert robot["evidence"]["sources"][-1]["type"] == "user"
    load_config(data=robot)  # the browser document is a valid configuration
    assert errors == []
    page.close()


def test_custom_hardware_without_citation_is_refused_in_plain_language(browser, server):
    page, _ = _page(browser, server)
    _go(page, "robot")
    page.click("#add-custom")
    page.fill("#c-name", "mystery")
    page.fill("#c-power", "3")
    page.select_option("#c-src", "datasheet")
    page.click("#c-ok")
    page.wait_for_selector("#c-err .issue.error")
    assert "needs a citation" in page.inner_text("#c-err")
    page.close()


def test_mission_builder_edits_phases(browser, server):
    page, _ = _page(browser, server)
    _go(page, "mission")
    n = page.locator("[data-del-ph]").count()
    page.click("#add-phase")
    page.wait_for_function(f"document.querySelectorAll('[data-del-ph]').length === {n + 1}")
    page.fill(f"#ph-dur-{n}", "45")
    page.press(f"#ph-dur-{n}", "Tab")
    page.wait_for_timeout(300)
    mission = page.evaluate("JSON.parse(localStorage.getItem('he.mission'))")
    assert mission["phases"][-1]["duration_s"] == 45
    Mission.from_mapping(mission)
    page.close()


def test_gui_run_matches_the_python_api_and_compare_reports_a_verdict(browser, server, tmp_path):
    robot = copy.deepcopy(TEMPLATES["four-thruster-rov"]["robot"])
    mission = copy.deepcopy(DEFAULT_MISSION)
    page, errors = _page(browser, server, robot=robot, mission=mission)
    _go(page, "run")
    page.fill("#run-label", "gui-a")
    page.click("#run-btn")
    page.wait_for_selector("h2:has-text('By category')", timeout=120_000)
    assert page.get_by_text("Terminal energy").first.is_visible()
    with urllib.request.urlopen(server.url + "api/runs", timeout=10) as r:
        runs = json.load(r)["runs"]
    saved = runs[-1]
    expected = run_scenario(load_config(data=robot), Mission.from_mapping(mission), tmp_path / "py")
    assert saved["terminal_energy_Wh"] == pytest.approx(expected.terminal_energy_Wh, rel=1e-12)
    assert saved["category_energy_Wh"] == pytest.approx(expected.category_energy_Wh, rel=1e-12)
    # A second configuration (no DVL), then the comparison view.
    without = copy.deepcopy(robot)
    without["components"] = [c for c in robot["components"] if c["name"] != "dvl"]
    page.evaluate("r => localStorage.setItem('he.robot', JSON.stringify(r))", without)
    page.goto(server.url + "#/run")
    page.reload()  # a hash change alone keeps the in-memory robot
    page.wait_for_selector("#run-btn")
    page.fill("#run-label", "gui-b")
    page.click("#run-btn")
    page.wait_for_selector("h2:has-text('By category')", timeout=120_000)
    _go(page, "compare")
    page.click("#cmp-go")
    page.wait_for_selector("#cmp-out .kpis")
    text = page.inner_text("#cmp-out")
    assert "evidence-aware" in text and "strict" in text
    with urllib.request.urlopen(server.url + "api/runs", timeout=10) as r:
        runs = json.load(r)["runs"]
    a, b = runs[-2], runs[-1]
    # The DVL is the only difference: the sensor energy difference matches the terminal one
    # within the small voltage coupling of actuator power.
    assert a["terminal_energy_Wh"] - b["terminal_energy_Wh"] == pytest.approx(
        a["category_energy_Wh"]["sensors"] - b["category_energy_Wh"]["sensors"], rel=0.05
    )
    assert "Ranking not supported" in text
    assert errors == []
    page.close()


def test_preflight_shows_evidence_warnings_before_a_run(browser, server):
    page, _ = _page(browser, server)
    _go(page, "run")
    page.click("text=Affects interpretation")
    body = page.inner_text("main")
    assert "5V rail converter efficiency is unknown" in body
    assert "proxy (grade C)" in body
    page.close()


@pytest.mark.parametrize("width", [320, 390, 768])
def test_no_horizontal_overflow_on_small_screens(browser, server, width):
    page, _ = _page(browser, server, width=width)
    for route in ROUTES:
        _go(page, route)
        page.wait_for_timeout(300)
        assert page.evaluate(OVERFLOW_JS) <= 0, route
    page.close()


def test_keyboard_reaches_skip_link_and_navigation(browser, server):
    page, _ = _page(browser, server)
    page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.className") == "skip"
    for _ in range(3):
        page.keyboard.press("Tab")
    assert page.evaluate("document.activeElement.getAttribute('href')") == "#/robot"
    page.keyboard.press("Enter")
    page.wait_for_function("document.title.startsWith('Robot')")
    page.close()


def test_large_robot_with_long_names_does_not_break_the_layout(browser, server):
    robot = copy.deepcopy(TEMPLATES["four-thruster-rov"]["robot"])
    robot["actuators"] = [
        {
            "id": f"T{i:02d}",
            "position_m": [0.3 * ((i % 4) - 1.5), 0.2 * (i // 4 - 1), 0],
            "direction": [1, 0, 0] if i % 2 else [0, 0, 1],
            "profile": "package:actuators/bluerobotics_t200.yaml",
        }
        for i in range(12)
    ]
    robot["actuation"]["backend"]["backend_index"] = list(range(12))
    robot["components"] = robot["components"] + [
        {
            "name": f"extremely_long_research_payload_device_name_number_{i:02d}_with_suffix",
            "category": "sensors",
            "states": {"ACTIVE": {"power_W": 1.0 + i}},
            "initial_state": "ACTIVE",
        }
        for i in range(20)
    ]
    mission = copy.deepcopy(DEFAULT_MISSION)
    mission["phases"] = [
        {"name": f"phase_{i:02d}_with_a_rather_long_descriptive_name", "duration_s": 10}
        for i in range(15)
    ]
    page, errors = _page(browser, server, width=320, robot=robot, mission=mission)
    for route in ("overview", "robot", "mission", "run"):
        _go(page, route)
        page.wait_for_timeout(400)
        assert page.evaluate(OVERFLOW_JS) <= 0, route
    assert page.locator("[data-del-comp]").count() == 23 or route != "robot"
    assert errors == []
    page.close()
