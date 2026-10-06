# Verification record

Date: 2026-10-06. Workspace: Windows, Python 3.13.12 and 3.10.20.
Branch: feature/holoenergy-battery-model. No remote or push was configured.
The starting directory was empty, so a new repository and external package were created.

## Automated verification

- 62 pytest tests passed in the Python 3.13 energy-only environment. In the
  installed HoloOcean Python 3.10.20 environment, 61 passed and 1 was skipped:
  the missing-HoloOcean test is intentionally inapplicable when it is installed.
  Coverage includes L0 Wh/SOC integration, Rint Coulomb
  counting, sag and terminal/ohmic energy balance, current/power/charge limits,
  temperature maps, voltage/thermal cutoff, exact cooling, entropy signs,
  startup and periodic ping accounting, unknown-state rejection, nonlinear
  derating, auxiliary shortages, multi-tick integration, reset, logging,
  control contracts, configuration/profile validation, CLI examples and failure behavior.
- Ruff lint passed; Python files passed format checks.
- Official T200 workbook import reproduced the committed profile with no diff.
  The source hash matches the bundled metadata; the conflicting source row is
  explicitly tested and preserved.
- Source distribution and universal Python wheel built successfully.
- Wheel installed into build/wheel-check with only its runtime dependency PyYAML.
  Python isolated mode (-I) verified import from site-packages and all eight
  packaged thruster power outputs; it did not import the repository source.
- Dependency graph is captured in uv.lock. Observed dev tools: pytest 9.1.1,
  Ruff 0.16.10, openpyxl 3.1.5, build 1.6.1; runtime PyYAML 6.0.3.

Checks:

    .venv\Scripts\python.exe -m pytest -q
    .venv\Scripts\ruff.exe check holoenergy tools examples tests
    .venv\Scripts\ruff.exe format --check holoenergy tools examples tests
    .venv\Scripts\python.exe tools\import_t200.py
    git diff --exit-code -- holoenergy/profiles/thrusters/bluerobotics_t200.json
    uv build --out-dir dist

## Demonstration checks

Both synthetic demos ran successfully with JSONL logging. A separate CSV demo
and CSV/JSONL parsing are checked in tests. Representative energy-only output:

| Run | Duration | Terminal Wh | Final reference SOC |
| --- | --- | --- | --- |
| Energy demo, 360 ticks | 18 s | 0.904156 | 0.996660 |
| Sonar OFF, 300 ticks | 15 s | 0.860258 | 0.996808 |
| Sonar ACTIVE, 300 ticks | 15 s | 0.879417 | 0.996743 |

These are deterministic synthetic runs using acknowledged placeholders, not
measurements or validated BlueROV2 endurance. Added sonar load can displace
propulsion during supply limiting, so total delta need not equal payload delta.
The energy-only .venv's missing-HoloOcean path failed with a clear error and no
synthetic fallback. HoloOcean is installed elsewhere on this machine, as verified below.

## Native HoloOcean integration

The user supplied C:/Users/Andrea/Desktop/Holoocean2-3. Inspection identified the
source checkout HoloOcean-2.3.0/HoloOcean-2.3.0 and the actual installed client:

- Interpreter: C:/Users/Andrea/miniconda3/envs/holoocean_joystick/python.exe,
  Python 3.10.20; HoloOcean 2.3.0.
- Installed Ocean package and Windows world binary under
  C:/Users/Andrea/AppData/Local/holoocean/2.3.0/worlds/Ocean.
- Native scenario: configs/bluerov2_holoocean.json, Ocean/SimpleUnderwater,
  one BlueROV2, scheme 0, eight forces, pose/velocity and 128x128 camera.
- HoloEnergy installed editable in this existing Conda environment with --no-deps;
  HoloOcean source, engine and existing dependencies were not modified.

Both demos completed 300 native steps (15 s simulated), producing JSONL logs:

| Native run | Terminal Wh | Final reference SOC |
| --- | --- | --- |
| Energy demo / sonar ACTIVE | 0.879417 | 0.996743 |
| Payload demo / sonar OFF | 0.860258 | 0.996808 |
| Payload demo / sonar ACTIVE | 0.879417 | 0.996743 |

The scenario renders a camera. Sonar OFF/ACTIVE changes the modeled electrical
proxy; this lightweight scenario does not render an imaging sonar. Sensor state
energy differences do not establish physical Ping360 power accuracy.

The opt-in native integration script compared actual vehicle motion over
60 ticks / 3 s using an explicitly imposed 8 A test limit:

| Mode | Surge displacement | Last angled thruster command | Maximum modeled current |
| --- | --- | --- | --- |
| Action derating enabled | 2.473942 m | 9.812758 N each | 8.0 A |
| Accounting only | 4.674221 m | 20.0 N each | 8.0 A |

This confirms the curtailed commands change physics, while accounting-only mode
retains full simulator thrust. Native timestamp increments were 0.05 s, all
applied actions stayed within public [-28.75,28.75] N limits, and each simulator
process was closed. The 8 A cap is a test intervention, not a revised battery rating.
Report/logs are in logs/holoocean/; the comparison is reproducible with:

    <HoloOcean-Python> examples/verify_holoocean_integration.py --backend holoocean --steps 60 --output-dir logs/holoocean

Read-only source inspection and hashes are saved in
sources/holoocean_local_inspection.json. The native check validates software
coupling and lifecycle, not the real battery/thermal/payload calibration.

## Created files

- Packaging: pyproject.toml, uv.lock, MANIFEST.in, .gitignore, README.md.
- Package API: holoenergy/__init__.py, config.py, env_wrapper.py, logging.py,
  _validation.py.
- Models: battery.py, thermal.py, propulsion.py, payload.py, hotel_load.py,
  converters.py, power_manager.py and models/__init__.py.
- Profiles: batteries/bluerobotics_4s18ah.yaml;
  thrusters/bluerobotics_t200.json;
  sensors/bluerobotics_usb_camera.yaml, bluerobotics_ping360.yaml, custom_payload.yaml;
  vehicles/bluerov2_heavy.yaml.
- Configuration: configs/bluerov2_energy.yaml and bluerov2_holoocean.json.
- Examples: examples/_common.py, bluerov2_energy_demo.py,
  bluerov2_sensor_payload_demo.py and verify_holoocean_integration.py.
- Tests: conftest.py, test_battery_models.py, test_thermal_model.py,
  test_payload_models.py, test_energy_accounting.py, test_config_and_profiles.py,
  test_examples.py.
- Documentation: scientific_sources.md, holoenergy_design.md,
  validation_protocol_bluerov2.md and this record.
- Research: sources/research*.json and the unchanged official T200 workbook.
  Processing: tools/import_t200.py.

Generated logs and environments are ignored by Git. Built distributions are
in dist/ and are also ignored. Source records are versioned for auditability.

## Remaining validation and next work

Native HoloOcean 2.3.0 startup, force units, tick timing, actuator bounds and
motion under curtailed commands are now verified on this machine.
No physical BlueROV2 was connected. Cross-version/world testing and scientific
calibration of real energy and temperature remain outstanding.

Before quantitative publication:

1. Extend native checks to mission scenarios, other supported versions and
   actual imaging-sonar rendering when those are needed.
2. Replace placeholder OCV/DC resistance, effective thermal parameters, hotel load
   and converter efficiencies with controlled measurements.
3. Characterize pack temperature-dependent OCV, resistance, accessible capacity
   and current limits; default temperature maps are reference identities only.
4. Measure sensor state-specific loads and identify any DVL/other sonar hardware.
5. Validate on held-out maneuver/mission data and perform timestep refinement.

L2 RC polarization, aging, burst-current budgets, hot-cell gradients, exact
brownouts, inflow/interference and PID/custom-dynamics hooks remain deferred.
