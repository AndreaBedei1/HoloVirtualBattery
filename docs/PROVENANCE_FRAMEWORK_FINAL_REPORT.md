# HoloEnergy provenance-aware framework: final report of the native phase (2026-11-12)

## Repository state

| Item | Value |
| --- | --- |
| Branch | `feature/provenance-aware-energy-framework` (pushed; normal pushes only) |
| Starting commit | `04f3325` (8 provenance-aware commits on `fix/verified-holoocean-drag-backend`) |
| Final commit and CI | see the last section |
| Tags | `v0.1.0` unchanged (`fdcd7ee`); `v0.2.0` created on the release commit after the author's approval (2026-11-12) |
| `main` | not merged |
| Author | Andrea Bedei (repository configuration); no co-author lines |

## CI

* **Fix:** `uv pip install ... --find-links dist --no-index` could not resolve NumPy.
  - The job now installs the locked runtime dependencies (NumPy, PyYAML) from `uv.lock`, then installs the exact built wheel file offline (`--no-index --reinstall-package holoenergy`).
  - Resolving by name had let uv reuse a cached wheel of the same version.
  - NumPy was kept.
* **Smoke test:** the installed-wheel test checks the registry datasets, NumPy allocation and the proxy profiles. It also runs the installed `holoenergy` CLI: `profiles`, `validate`, `evidence` and `audit-sensors`.
* **Runs:** [43272502605](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43272502605) and [43286942485](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43286942485), both 8/8 jobs green (Ubuntu and Windows × Python 3.10–3.13). The final run is listed at the end.
* **Tests:** 317 unit tests pass locally (257 at the start). `ruff check` and `ruff format --check` are clean.

## Independent reviews

| Review | Findings | Resolution |
| --- | --- | --- |
| Software | 10 confirmed defects. The most severe: a rejected attach left evidence state behind; NaN or negative cumulative load energy was accepted; constant hotel energy was outside the evidence total; YAML-dataset proxy actuators escaped the stale-link check; modem upper-bound and proxy shares were missing; `reverse: null` crashed with normalized commands | all fixed, each with a regression test (`tests/test_review_regressions.py`) |
| Scientific | The speed baseline used over-ground speed; T200 static curves graded A although applied with inflow; the von Benzon comparison was not like-for-like; communication claims ignored upper-bound pricing; several stale or unqualified numbers | Water-relative baseline added. T200 relation set to `representative` (grade B). Comparison and every claim corrected (below and in README, RESEARCH_STATUS and the outline) |
| Reproducibility | Offline campaign, DESERT matrix, native heave run and analysis reproduced to floating-point precision or exactly. Gaps: figure script not committed, scripts overwrote committed results, non-deterministic gzip hashes, unclear interpreters | Script committed; output options added; deterministic traces and figures; [native_runs.md](native_runs.md) extended |

## Evidence registry

177 records and 144 sources (grades A 113, B 3, C 40, D 21; 157 configured, 20 unconfigured). New this phase:

* **External hydrodynamic data:** Gabl et al. 2021 restrained-load curve (B), the derived equivalent drag area (C), von Benzon et al. 2022 identified damping (C), and Wu 2018 adopted coefficients (D).
* **HoloOcean literals:** the BlueROV2 drag literals (A, simulator-exact).
* **Proxy-vehicle records:** 46.
* **Loader change:** parameter files may declare their own sources.
* **Single source of truth:** offline E4 reads every constant from the registry.

Literature used: the 60-paper workbook database (hashes only; no PDFs committed). New sources:

* Gabl et al. 2021 and its dataset;
* Wu 2018;
* for related work: Sargent 2013 (doi:10.1057/jos.2012.20), Oberkampf and Roy 2010 (ISBN 9780521113601) and Masiero et al. 2012 (doi:10.1109/OCEANS-Yeosu.2012.6263524).

Two communication-energy references are marked "to verify". Remaining gaps are listed in [EVIDENCE_GAPS.md](EVIDENCE_GAPS.md).

**What the grades mean:** evidence-grade shares describe the parameters of the electrical models only, not geometry, dynamics, or the placeholder OCV that sets the bus voltage. After the review, propulsion is graded B. The committed native summaries were produced earlier and report it as A.

## Framework changes this phase

* Double-counting audit including attached sources, with an optional reject policy.
* Stale evidence links graded D.
* Proxy-energy and upper-bound shares that include modems.
* `ensure_interfaces` for all-node observers.
* Exact charging of late PHY events, with cumulative non-negativity and finiteness checks.
* Hotel energy included in the evidence total.
* `reverse: null` actuators and `max_power_W: null` batteries.
* Dashboard panels: actuation, communications, evidence, compare runs.
* `tools/build_patched_holoocean.py --engine-kind launcher`.
* Deterministic traces (content hashes) and deterministic figures.

## Backend verification (implementation, not vehicle validation)

* **Rebuild:** HoloOcean v2.3.0 (`49e70552`) was rebuilt against the installed Launcher UE 5.3.2 (CL 29314046) with MSVC 14.44.35207 and Windows SDK 10.0.19041.0.
  - `PLATFORM_HAS_ASAN_INCLUDE=0` reproduces the official machine.
  - Official cooked content is reused through hard links.
* **Artifacts:** STOCK `8c206c9c…` (not launched), CONTROL `51e0de81…`, PATCHED `9575fb02…`. The patch SHA256 is `00f1b303…`.
* **Checks at 100 Hz:**
  - The control gives 0.0099999995 / 0.0100003658, the same as the archived official values.
  - The patched build gives 1.0000000097 / 1.0000002332 and PASS.
  - The step ratio is 1.000000.
* **Instances:** isolated by random UUID, at most two of my own at once, next to four instances of another project that were never touched.

## Native HoloOcean results (closed loop, 100 Hz)

[`experiments/results/native`](../experiments/results/native), [tables](../experiments/results/native/tables), [figures](figures/paper).

* **Chain closure:** 42 runs close the chain tick by tick (force residual ≤ 5.2e-5 N, power residual ≤ 4e-12 W).
  - 38 PASS.
  - 4 wrench-equivalent runs at 0.8 m/s flag ticks where the native clamp could not reproduce the virtual wrench.

**Actuator configurations.** Virtual layouts are evaluated on the HoloOcean BlueROV2 Heavy dynamic body through wrench-equivalent actuation; only L8-HV is simulator-exact.
* Shared vectored horizontals give identical costs in surge current: 0.158 Wh per 30 s at 0.2 m/s, 3.18 Wh at 0.5 m/s.
* L4-2H2V is 13–17% cheaper but cannot sway. L8-VEC30 costs 21–30% more.
* Heave: 6T needs 42% more energy than 8T, close to √2 from the static curve. 4T-H45 cannot heave.
* At 0.8 m/s no layout holds station. HoloOcean's drag is 114.9 N against about 81 N of clamp-limited surge, whereas Gabl measured 28.8 N. This is a property of the simulated vehicle.
* Direct and wrench-equivalent mappings agree exactly at 0–0.5 m/s, and differ by 8.7% at 0.8 m/s.
* Where requests are met, tracking is identical across layouts. The energy differences come from geometry and the T200 curve.

**Orientation**, at 0.5 m/s current over 30 s (surge / sway):

| Horizontal angle | Surge current | Sway current |
|---|---|---|
| 30° | 2.32 Wh | 4.67 Wh |
| 45° | 3.18 Wh | 2.73 Wh |
| 60° | 5.47 Wh | 1.99 Wh |

The 60° surge case is power-limited on 8% of ticks, so its request is not fully met.

**Station keeping** (L8-HV): 0 / 0.158 / 3.18 / 6.28 Wh of propulsion at 0 / 0.2 / 0.5 / 0.8 m/s. The 0.8 m/s case is not met. The 30 s windows include the initial transient.

**Moving mission** (67 s):
* Total energy is 0.62 / 1.63 / 4.03 Wh at 0 / 0.2 / 0.4 m/s.
* SOC loss is 0.21–1.36%, peak current 4.0–32.6 A, and minimum voltage 16.30–16.74 V.

**Power limiting:** starting at 3% SOC in 0.5 m/s current, the pack reaches its 12.0 V cutoff, thrust is derated to zero, and the vehicle drifts 6.4 m.

**Sensors and compute** (transit in 0.2 m/s): the inspection suite adds 86% and AI vision 23%.

**Battery:** L0 is 3.8% below L1. This is the effect of the placeholder OCV.

**Baselines** (fitted only on the calm-water transit; model-vs-model comparison):
* A cubic in over-ground speed is −89% / −98.7% in station keeping at 0.2 / 0.5 m/s and −65% / −91% on transits in current.
* A cubic in speed through the water is −15% to +13% on the same cases, and +68% on heave.
* A constant-power model ranges from −93% to +255%.
* **Conclusion:** an energy-accuracy advantage of actuator effort over a water-relative speed model is shown only for heave and actuator-layout and orientation effects, not for surge-dominated cases in this simulator.

**Ablations** (native transit in 0.2 m/s):
* propulsion 1.52 Wh, sensors and compute 0.11 Wh, battery losses 0.017 Wh;
* without current: 0.62 Wh total;
* L0 instead of L1: −3.8%.

## BlueROV2 hydrodynamic comparison

[Audit](bluerov2_hydrodynamic_external_comparison.md).

* HoloOcean's drag is 3.8–4.5× the mean restrained load of a modified standard BlueROV2 (Gabl et al. 2021, Table 1) at 0.4–1.0 m/s. The match is in loading condition only. The 0.2 m/s point lies within the zero residual.
* HoloOcean's still-water resistance (quadratic drag plus linear damping) is 1.13–1.21× the damping identified on a free-running Heavy (von Benzon et al. 2022) at 0.2–0.6 m/s.
* The two references disagree by 3–4×.
* The earlier claim of "3.8–7.2×" was narrowed. The verified backend is not a validated hydrodynamic model.

## DESERT native integration

* **Setup:** own engine container (`holoenergy-desert-5571`, image `holo-desert-engine:4.0.0-v2`, fingerprint `755d96a2c67be143`) on 127.0.0.1:5571. Docker is never managed by the session.
* **Non-interference:** native PASS on e01_chat, e05_multihop and e04_congestion. The SUN convergecast scenario rejects the check's traffic even without observation.
* **Energy check:** E = ΣP·t matches the adapter's energy for all 9 configurations.

**Communication-energy results** (10 messages, 70 s):
* Direct: 33.4 mWh for 10/10 delivered. MAC ACK adds 0.3%.
* Multi-hop static: 51.2 mWh. With ACK only 3/10 are delivered.
* Flooding on the 4-node square sends 3× the frames for +7%.
* Optical: 19.5 mWh. Hybrid: 52.8 mWh.

These energies price RX and listen at the published 0.8 W maximum: 72–95% of the acoustic energy rests on upper bounds. They also use DESERT's 4.8 kbit/s airtime with S2C M datasheet power, so strategy differences inherit both choices.

**Cross-layer** (same 67 s transit in 0.2 m/s current):
* The vehicle's acoustic modem adds at most 1.37% of terminal energy (TX about 48%, listen 42–52%); optical adds 0.57%.
* It is the same for every strategy because the vehicle sends the same messages and never relays.
* Network-wide energy and delivery differ: multi-hop 27/34, flooding 33/34.
* Bus and adapter agree to 1e-15 Wh, and the trajectory is identical in every case.
* The modem would be a larger share in still-water station keeping.

Communication accounting stays observe-only.

## Proxy vehicles

* **Created (literature proxies, grade C electrical models):** `hovering-mares-like`, `torpedo-remus-like`, `torpedo-tethys-like` and `torpedo-autosub-like`. Each states its relation to the generic HoloOcean class, its validity range and its gaps.
* **Not created:** AMOUR, Silver Frog and the dual-electric USV. Their sources do not relate thrust to electrical power.
* **Native runs:** none yet. A fin/command adapter is needed.

## External validation and uncertainty

* **Validation levels:**
  - Component level: by construction from manufacturer tables.
  - Vehicle/subsystem level: the partially comparable drag data above.
  - Mission level: no dataset reproduces its initial conditions.
* **Fitting:** no HoloEnergy parameter was fitted. The baselines use an explicit calibration run.
* **Intervals:** only from published ranges, e.g. the hotel-load part of the inspection transit, 2.62–2.84 Wh, open on both sides. Propulsion and hydrodynamics are not bounded. No distributions were assumed.

## Dashboard and overhead

The new panels were checked in a browser with live telemetry. Cost is 3.3–4.3 ms per tick, and 4.9 ms with telemetry and evidence snapshots. That is 12–19% of the native step on a shared machine. Simulated results do not depend on wall time.

## Figures, tables, documentation

* Figures `docs/figures/paper/F01`–`F13` (PNG, SVG, PDF and CSV, deterministic) and tables in `experiments/results/native/tables/` and `experiments/results/offline/`.
* Documents: README; [documentation index](README.md); [provenance_framework.md](provenance_framework.md); [native_runs.md](native_runs.md); [double_counting_policy.md](double_counting_policy.md); [comparison](bluerov2_hydrodynamic_external_comparison.md); [paper outline](paper_outline_smpat.md); [RESEARCH_STATUS](RESEARCH_STATUS.md); [EVIDENCE_GAPS](EVIDENCE_GAPS.md).

## Supported and unsupported claims

* **Supported:** a provenance-aware energy layer for HoloOcean; closed-loop coupling of actuator effort, loads, battery and available thrust, verified tick by tick; arbitrary layouts with consistency flags; observe-only communication energy verified not to perturb DESERT; interval propagation from published ranges.
* **Unsupported:**
  - physical validation of any vehicle, and validated BlueROV2 hydrodynamics;
  - an advantage over water-relative speed models outside heave and layout effects;
  - inflow-aware T200 power;
  - battery temperature or pressure effects;
  - exact BlueROV2 Standard geometry;
  - typical modem energy;
  - validity of the proxies for the named vehicles;
  - statistical generalisation.

## Threats to validity

* One controller policy and one rigid body.
* Deterministic single runs.
* Static T200 tables; placeholder pack OCV and thermal parameters; upper-bound modem powers.
* Unvalidated simulator hydrodynamics.
* Transient-dominated 30 s windows.
* Native runs produced from working trees with uncommitted changes (recorded as dirty).

## Upstream HoloOcean

The draft in [holoocean_drag_issue_draft.md](holoocean_drag_issue_draft.md) was updated with the second-machine reproduction. Nothing was posted.

## Release and merge recommendation

* **Release:** a `v0.2.0` tag is justified after the final CI run is green. Native HoloOcean and DESERT matrices are complete, the documentation is updated, and the reviews are resolved. The author approved it; `v0.2.0` tags the release commit that sets the package version to 0.2.0 on top of `2d0512a`.
* **Merge:** merge into `main` only after the author reviews the corrected claims and decides the upstream contribution. No merge was performed.

## Remaining blockers

* Real BlueROV2 data (pack OCV/R, hotel load, thrust and power in flow, Heavy drag) for calibration and validation.
* A fin/command adapter for native proxy runs.
* Verification of two related-work references.
* Authorization to publish the upstream contribution.

## Final state

| Item | Value |
| --- | --- |
| Final code and results commit | `52868b714e6730d96b50ac7a99756bff3bd19633` (remote HEAD equal to local HEAD at push) |
| CI on that commit | run [43293424867](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43293424867): 8/8 jobs green (Ubuntu + Windows, Python 3.10-3.13) |
| Commits in this phase | 25 on top of `04f3325` up to the final code commit (documentation commits follow) |
| Cleanup | own DESERT container removed; no own HoloOcean process left; separate packages kept in `C:/HOB` for reproduction; Docker Desktop left running |
