# HoloEnergy provenance-aware framework: final report of the native phase (2026-11-12)

## Repository state

| Item | Value |
| --- | --- |
| Branch | `feature/provenance-aware-energy-framework` (pushed; normal pushes only) |
| Starting commit | `04f3325` (8 provenance-aware commits on `fix/verified-holoocean-drag-backend`) |
| Final commit | see the last section (written at the final push) |
| Tags | `v0.1.0` unchanged (`fdcd7ee`); no `v0.2.0` created |
| `main` | not merged |
| Author | Andrea Bedei (repository configuration); no co-author lines |

## CI

* **Fix:** `uv pip install ... --find-links dist --no-index` could not resolve NumPy.
  - The job now installs the locked runtime dependencies (NumPy, PyYAML) from `uv.lock` into the clean environment, then installs HoloEnergy offline.
  - It later moved to installing the exact built wheel file (`--no-index --reinstall-package`), because uv had reused a cached wheel of the same version.
  - NumPy was kept.
* **Smoke test:** the installed-wheel test checks the registry, the packaged datasets, NumPy allocation and the proxy profiles. It also runs the installed `holoenergy` CLI: `profiles`, `validate`, `evidence` and `audit-sensors`.
* **Runs:**
  - [43272502605](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43272502605): first green run after the fix, 8/8 jobs (Ubuntu and Windows × Python 3.10–3.13).
  - [43286942485](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43286942485): 8/8 green.
  - The final run is listed at the end.
* **Tests:** 308 unit tests pass locally (257 at the start). `ruff check` and `ruff format --check` are clean.

## Evidence registry

177 records and 144 sources (grades A 113, B 3, C 40, D 21; 157 configured, 20 unconfigured). New this phase:

* **External hydrodynamic data:** Gabl et al. 2021 restrained-load curve (B), the equivalent drag area derived from it (C), von Benzon et al. 2022 identified damping (C), and Wu 2018 adopted coefficients (D).
* **HoloOcean literals:** the BlueROV2 drag literals (A, simulator-exact).
* **Proxy-vehicle records:** 46, including unconfigured records for vehicles that could not be profiled.
* **Loader change:** parameter files may declare their own sources.
* **Single source of truth:** offline E4 now reads every constant from the registry.

Literature used: the 60-paper workbook database (local PDFs matched by DOI, title or arXiv; hashes only, no PDFs committed). New sources:

* Gabl et al. 2021 (Ocean Eng. 234:109279) and its 2020 dataset;
* Wu 2018 (thesis);
* for related work: Sargent 2013 (doi:10.1057/jos.2012.20), Oberkampf and Roy 2010 (ISBN 9780521113601) and Masiero et al. 2012 (DESERT, doi:10.1109/OCEANS-Yeosu.2012.6263524).

Two communication-energy references are marked "to verify" in the outline.

Remaining gaps are listed in [EVIDENCE_GAPS.md](EVIDENCE_GAPS.md): T200 at advance speed, BlueROV2 pack OCV–SOC/R/thermal parameters, hotel loads, source level → modem electrical power, Heavy-specific drag measurements, the LUMA bitrate, and the proxy adapters.

## Framework changes this phase

| Change | Why |
| --- | --- |
| Double-counting audit including attached load sources (`modem_signal_processing`), standalone DVL `includes: [dvl]`, `evidence.double_counting: error` | four audit cases of the brief; three were not detected before |
| Stale evidence links graded D | a user override of a linked value (e.g. pack resistance) still credited the record's grade C |
| Proxy-energy share and stale links in every evidence summary | per-run audit requirement |
| `DesertEnergyAdapter.ensure_interfaces` for all-node observers | silent interfaces (unused optical modem) accrued no listen energy; found by the independent E = ΣP·t recomputation |
| Load sources may report per-state corrections (device total ≥ 0) | late PHY events moving time LISTEN → TX were rejected by the bus; native HoloOcean+DESERT runs failed |
| `reverse: null` actuator tables, `max_power_W: null` batteries | forward-only and unpublished-limit evidence of proxy vehicles |
| Dashboard: actuation, communications, evidence, compare-runs panels; evidence computed only when a sample is sent | brief §45–47 |
| `tools/build_patched_holoocean.py --engine-kind launcher` | rebuild of the patched backend on this machine |

## Backend verification (implementation, not vehicle validation)

* **Rebuild:** HoloOcean v2.3.0 (`49e70552`) was rebuilt against the installed Epic Launcher UE 5.3.2 (CL 29314046) with MSVC 14.44.35207 and Windows SDK 10.0.19041.0.
  - `PLATFORM_HAS_ASAN_INCLUDE=0` reproduces the official machine, which had no ASAN headers.
  - The official cooked content is reused through hard links, and the sonar octree cache is not copied.
* **Artifacts:** STOCK `8c206c9c…` (archived check only; the installed package is never launched), CONTROL `51e0de81…` and PATCHED `9575fb02…`. The patch SHA256 is `00f1b303…`.
* **Checks at 100 Hz** with `tools/check_holoocean_backend.py`:
  - The control rebuild gives 0.0099999995 / 0.0100003658, the same as the archived official values.
  - The patched build gives 1.0000000097 / 1.0000002332 and PASS.
  - The physics/client step ratio is 1.000000.
* **Instances:** isolated by random UUID (no TCP port), each from its own package directory. At most two of my instances ran at once, next to four instances of another project, which were never touched.

## Native HoloOcean results (closed loop, 100 Hz)

[`experiments/results/native`](../experiments/results/native), [tables](../experiments/results/native/tables), [figures](figures/paper).

* **Chain closure:** all 42 runs close the chain tick by tick (max force residual 5.2e-5 N; recomputed T200 power residual 4e-12 W).
  - 38 PASS.
  - 4 wrench-equivalent runs at 0.8 m/s flag ticks where the native clamp could not reproduce the virtual wrench.

**Actuator configurations** (virtual layouts are evaluated on the HoloOcean BlueROV2 Heavy dynamic body through wrench-equivalent actuation; only L8-HV is simulator-exact):
* L8-HV, L6-STD and L4-H45 cost the same in surge current. Example: 0.158 Wh per 30 s at 0.2 m/s, 3.18 Wh at 0.5 m/s.
* L4-2H2V is 13–17% cheaper, but it cannot sway (8.7 m drift).
* L8-VEC30 costs 21–30% more.
* Heave: 6T needs 42% more energy than 8T, and 4T-H45 cannot heave.
* At 0.8 m/s no layout holds station: the 28.75 N clamp saturates and the vehicle drifts 4.2–5.2 m. Those energies are reported but not ranked.
* The direct and wrench-equivalent mappings of L8-HV give identical energy, which checks the mapping.

**Orientation**, at 0.5 m/s current over 30 s (surge / sway):

| Horizontal angle | Surge current | Sway current |
|---|---|---|
| 30° | 2.32 Wh | 4.67 Wh |
| 45° (BlueROV2) | 3.18 Wh | 2.73 Wh |
| 60° | 5.47 Wh | 1.99 Wh |

The 60° surge case reaches the 60 A pack limit.

**Station keeping** (L8-HV, 30 s at 0 / 0.2 / 0.5 / 0.8 m/s):
* Propulsion energy is 0 / 0.158 / 3.18 / 6.28 Wh (the 0.8 m/s case does not meet the request).
* Peak current grows with current speed. Power limiting is reached only in the 60° and low-SOC cases.

**Moving mission** (accelerate, transit, stop, yaw 180°, return; 67 s):
* Total energy is 0.62 / 1.63 / 4.03 Wh at 0 / 0.2 / 0.4 m/s current.
* SOC loss is 0.21–1.36%, peak current 4.0–32.6 A, and minimum voltage 16.30–16.74 V.

**Power limiting:** starting at 3% SOC in 0.5 m/s current, the pack reaches its 12.0 V cutoff, thrust is derated to zero, and the vehicle drifts 6.4 m.

**Sensors and compute** (transit in 0.2 m/s):
* The inspection suite adds 86% over propulsion only (2.83 vs 1.52 Wh).
* AI vision (Jetson Orin NX at its measured YOLOv8s workload) adds 23%.

**Battery:** L0 is 3.8% below L1. Pack OCV–SOC and thermal parameters remain placeholders (D), and the resistance is a proxy (C).

**Baselines** (fitted only on the calm-water transit, evaluated on every other L8-HV run):
* The speed-cubic model is −89% / −98.7% in station keeping at 0.2 / 0.5 m/s, −65% / −91% on transits in current, and +68% on heave.
* The constant-power model ranges from −93% to +255%.

**Ablations** (decomposition of the native transit in 0.2 m/s):
* propulsion 1.52 Wh, sensors and compute 0.11 Wh, battery losses 0.017 Wh;
* without current: 0.62 Wh total;
* L0 instead of L1: −3.8%.

## BlueROV2 hydrodynamic comparison

[Audit](bluerov2_hydrodynamic_external_comparison.md).

* The Gabl et al. 2021 values come from Table 1: a modified standard BlueROV2, head-on, nominal tank speed, tethered restraint, mean ΣFx.
* HoloOcean's quadratic drag (Cd·A = 0.36 m²) is 3.8–4.5× that load at 0.4–1.0 m/s. The 0.2 m/s point lies within the zero residual.
* The same drag is 0.86–1.16× the surge damping identified for a BlueROV2 Heavy by von Benzon et al. 2022. The two external references therefore disagree by 3–4×.
* UE linear damping acts on absolute velocity, so it is correctly excluded for a vehicle held in a current.
* The previous claim of "3.8–7.2×" was narrowed. The verified backend is not a validated hydrodynamic model.

## DESERT native integration

* **Setup:** own engine container `holoenergy-desert-5571` (image `holo-desert-engine:4.0.0-v2`, fingerprint `755d96a2c67be143`) on 127.0.0.1:5571. The session never manages Docker; holo_desert's Compose service would otherwise recreate another user's container.
* **Non-interference:** native PASS. Events, deliveries and summaries are identical with and without the observer. Only wall-clock metadata differs, and it also differs between two plain runs; the check now drops it at every depth.
* **Energy check:** E = ΣP·t recomputed from raw PHY durations equals the adapter's energy for all 9 configurations.

**Communication-energy results** (10 messages, 70 s):
* Direct: 33.4 mWh for 10/10 delivered.
* MAC ACK adds 10 control frames for +0.3%.
* Multi-hop static: 51.2 mWh, 10 relay forwards. With MAC ACK only 3/10 are delivered (51 data and 36 control frames).
* Flooding on the 3-node line equals static. On the 4-node square it sends 3× the frames for +7% energy.
* Optical: 19.5 mWh. Hybrid: 52.8 mWh, because both modems listen.

72–95% of the acoustic energy rests on published upper bounds (RX/listen ≤ 0.8 W). Energy per message or byte is reported only together with that share.

**Cross-layer** (same native transit in 0.2 m/s, six strategies):
* The vehicle's acoustic modem adds 0.0226 Wh (1.37% of mission energy) for all acoustic strategies; optical adds 0.57%.
* Network-wide modem energy (0.038–0.060 Wh) and delivery differ: multi-hop 27/34, flooding 33/34.
* Bus and adapter agree to 1e-15 Wh, and the trajectory is identical in every case.
* The only coupling is the pack voltage: propulsion energy changes by −0.006%.

Communication accounting stays observe-only; battery-aware network scheduling is future work.

## Proxy vehicles

* **Created (literature proxies, grade C electrical models):** `hovering-mares-like`, `torpedo-remus-like`, `torpedo-tethys-like` and `torpedo-autosub-like`.
  - Each states its relation to the generic HoloOcean class, its validity range and its gaps.
  - HoloOcean geometry, mass and drag are unchanged.
* **Not created:** AMOUR, Silver Frog and the dual-electric USV. Their sources do not relate thrust to electrical power; the extracted values stay as unconfigured records.
* **Native runs:** the proxies have not been run natively. The torpedo and hovering agents need a command adapter (fins).

## External validation

* **Component level:** reproduced by construction from manufacturer tables (T200, sensors, modems).
* **Vehicle/subsystem level:** only the drag comparison above is like-for-like.
* **Mission level:** no dataset reproduces its initial conditions, so none was attempted.

The calibration/validation split applies to the baselines. No HoloEnergy parameter was fitted.

## Uncertainty

Intervals come only from published ranges (e.g. 2.62–2.83 Wh for the inspection transit). Most sides stay open because only maxima are published. Upper-bound-derived energy is reported separately. No distributions were assumed.

## Dashboard and overhead

The new panels were checked in a browser with live telemetry. Energy-layer cost is 3.3–4.3 ms per tick, and 4.9 ms with telemetry, evidence snapshots and a polled dashboard. That is 12–19% of the native step on a shared machine. Simulated results do not depend on wall time.

## Figures and tables

* Figures `docs/figures/paper/F01`–`F13` (PNG, SVG, PDF and CSV): architecture, evidence flow, T200 model, backend verification, layouts, orientation, station keeping vs current with baselines, payload breakdown, communication policies, mission with and without communications, uncertainty.
* Tables: `experiments/results/native/tables/*.csv` and `experiments/results/offline/*.csv`.

## README and documentation

* README introduction, v0.2 summary, native results, validation status and limitations.
* New documents: [provenance_framework.md](provenance_framework.md), [native_runs.md](native_runs.md), [double_counting_policy.md](double_counting_policy.md), [bluerov2_hydrodynamic_external_comparison.md](bluerov2_hydrodynamic_external_comparison.md), [paper_outline_smpat.md](paper_outline_smpat.md) and a [documentation index](README.md).

## Supported and unsupported claims

* **Supported:** a configurable, provenance-aware energy layer for HoloOcean; closed-loop coupling of actuator effort, loads, battery and available thrust, verified tick by tick; arbitrary layouts with consistency flags; observe-only communication energy verified not to perturb DESERT; interval propagation from published ranges.
* **Unsupported:**
  - physical validation of any vehicle, and validated BlueROV2 hydrodynamics;
  - inflow-aware T200 power;
  - battery temperature or pressure effects;
  - exact BlueROV2 Standard geometry;
  - typical (not maximum) modem energy at DESERT source levels;
  - validity of the proxies for the named vehicles.

## Threats to validity

* One controller policy (user-selected gains) and one rigid body (HoloOcean BlueROV2).
* Deterministic single runs, so no run-to-run statistics.
* Static T200 tables; placeholder pack OCV and thermal parameters; upper-bound modem powers.
* Unvalidated simulator hydrodynamics (the external references disagree).
* Results were measured on a machine shared with other simulations. This affects wall time only.

## Upstream HoloOcean

The issue comment and PR text in [holoocean_drag_issue_draft.md](holoocean_drag_issue_draft.md) were updated with the second-machine reproduction. Nothing was posted. The `develop` diff remains not built.

## Release and merge recommendation

* **Release:** a `v0.2.0` tag is technically justified once the final CI run is green and the review findings below are resolved. The native HoloOcean and DESERT matrices are complete and the documentation is updated. It is not created here, because it needs the author's decision.
* **Merge:** merge `feature/provenance-aware-energy-framework` into `main` only after the author reviews the claims and the upstream status. No merge was performed.

## Remaining blockers

* Real BlueROV2 data (pack OCV/R, hotel load, thrust and power in flow, Heavy drag) for calibration and validation.
* A fin/command adapter for native proxy runs.
* Verification of two related-work references.
* Authorization to publish the upstream contribution.
