# Verification record

Date: 2026-10-06. Workspace: Windows, Python 3.13.12 and 3.10.20.
Historical first implementation: feature/holoenergy-battery-model, initially
without a remote. The latest consolidation started from a clean d179584 checkout
with origin configured; see the consolidated record at the end of this document.

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

## Consolidation verification — 2026-10-06

- Python 3.13.12: **106 tests passed**. Python 3.10.20 in the existing HoloOcean
  environment: **105 passed, 1 skipped** (the intentional missing-HoloOcean check).
- Source archive extracted under build/sdist-check: **106 passed**, importing
  the extracted source, with complete conftest fixtures and explicit absent-Git
  provenance. This identified a Git-dependent test assumption and verified its
  portable contract. Wheel imports from isolated site-packages with PyYAML only;
  installed-wheel Git provenance is explicitly absent even inside this workspace.
- Ruff check/format pass; official T200 importer reproduces the committed profile.
  Manufacturer workbook and all force/power values are unchanged. New metadata
  states static/bollard limitations. Wheel/sdist build successfully with MIT SPDX
  metadata, licenses, citation, tools, sources and full source tests.
- New coverage includes L0 constant reporting T, R(SOC,T), complete map imports,
  calibrated-domain flags, conservative force lookup, extrema, user brownout,
  failed-run/in-memory provenance, seeded studies, role/group/hash separation,
  synchronized residuals, sampling and unavailable-metric semantics.

Final native motion check ran from clean commit db660a7, package source SHA256
248a1d8e4d89aa5f6ec31ee6cdc6bb531d85898a7369671cf6a1f6fc0fae15b2.
It includes initialization/reset, four zero-action ticks, 60 direct surge ticks,
8 A imposed test limit, accounting-only/derated comparison, numerical arguments
passed to native step, dt checks and process shutdown. No hardware was connected;
HoloOcean was not reinstalled or modified.

| Native mode | Surge displacement | Last angled force | Maximum modeled I |
| --- | --- | --- | --- |
| Derating enabled | 2.473942 m | 9.812758 N each | 8.0 A |
| Accounting only | 4.674221 m | 20.0 N each | 8.0 A |

Both processes closed; a separate process inventory found no Holodeck process.
Accounting-only dynamics are explicitly inconsistent with curtailed energy.

| Native 300-command run | Terminal Wh | Final SOC |
| --- | --- | --- |
| L0 baseline | 0.895634 | 0.996638 |
| L1 | 0.879417 | 0.996743 |
| L1 sonar OFF | 0.860258 | 0.996808 |
| L1 sonar ACTIVE | 0.879417 | 0.996743 |

These are simulator outputs using documented placeholders and sensor maxima;
they are not accuracy or endurance measurements. No goal observer was supplied,
so mission completion/time are null. L1's 15 s comparison reports min voltage
14.381059 V, peak current 60 A, peak average-pack T 20.210963 C, terminal propulsion
0.781732 Wh, payload 0.025417 Wh, hotel 0.062500 Wh, conversion loss 0.009769 Wh
and separate internal loss 0.104989 Wh. The out-of-profile high-force demand is
flagged capped: its unmet-power estimate is not extrapolated physical demand.

Detailed logs/sidecars remain in logs/consolidation/. A compact versioned archive
with numerical results, run/source/config/profile IDs and file hashes is
sources/native_verification_consolidation.json. Rebuild it with
tools/archive_verification.py. It preserves each run's actual source commit,
including earlier clean commits used for payload/comparison checks; it does not
rewrite their provenance to the release commit. Versioned code can reproduce
the commands; raw generated logs are local ignored artifacts.

CI is defined for Python 3.10–3.13 on Linux/Windows using uv.lock, pytest, Ruff,
reproducible T200 import and package build. Native Unreal/GPU checks remain opt-in.
Remote CI outcomes and release refs are reported separately in the consolidation
report and final delivery; a workflow definition is not evidence of a completed run.

Remote verification completed successfully: all eight matrix jobs passed for
70f584f in [GitHub Actions run 37451876879](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/37451876879).
This adds actual Linux/Python 3.11/3.12 verification to the local Windows checks.
