# HoloEnergy research status (v0.2 development, 2026-11-06)

Branch `feature/provenance-aware-energy-framework`, created from
`fix/verified-holoocean-drag-backend` (6965411). Tag `v0.1.0` untouched. No HoloOcean or
DESERT process was launched in this phase (user instruction: native runs only after explicit
approval, as the last step).

## Implemented (unit-tested, 257 tests passing locally)

| Area | Module | Status |
| --- | --- | --- |
| Evidence registry (A–D grades bounded by relation, null = unconfigured) | `holoenergy/evidence` | done |
| Literature index: 60 workbook papers, 27 manufacturer sources, 43 local PDFs matched (DOI/title/arXiv), hashes only | `tools/build_literature_registry.py`, `evidence/data/literature.yaml` | done |
| Verified parameters: 121 records / 141 sources (sensors, modems, compute, batteries, T200, HoloOcean agents) | `evidence/data/parameters/*.yaml` | done |
| Explicit SI units; dB re 1 µPa and dBm refused as electrical power | `holoenergy/units.py` | done |
| Arbitrary actuator count/orientation, 6×n configuration matrix, redistributed / pseudo-inverse / power-IRLS allocation | `holoenergy/allocation.py` | done |
| Wrench action mode; direct or wrench-equivalent backend mapping (virtual layouts on the native body) | `holoenergy/actuation.py` | done |
| HoloOcean 2.3.0 agent geometry/clamps extracted from pristine sources with file hashes | `tools/extract_holoocean_geometry.py` | done |
| Profiles: `bluerov2-heavy` (simulator-exact geometry), `bluerov2-standard` (6T, role-exact, proxy verticals), 19 components, 13 modem profiles | `holoenergy/profiles`, `holoenergy/catalog.py` | done |
| Observe-only communication energy (TX/RX/listen intervals from holo_desert events) | `holoenergy/integrations/desert.py` | done (synthetic + scripted tests) |
| Evidence coverage, upper-bound share, incomplete loads, double-counting warnings | `evidence/runtime.py` | done |
| EnergyReport, interval propagation (open sides kept open), compare_runs, CLI | `report.py`, `uncertainty.py`, `cli.py` | done |
| HoloOcean sensor policy (state sensors 0 W, semantic = camera + compute) | `sensor_policy.py` | done |

## Experiments (offline replay of archived 100 Hz patched-backend traces; `experiments/run_offline_campaign.py`)

* E0 replay fidelity: archive decimation changes propulsion energy by ≤ 0.17 %.
* E1/E1b layouts: with surge-only archived missions L8/L6/L4-H45 cost the same (verticals idle).
  Steady directional cases: 2 verticals (L6) need ~1.75× the heave power of 4 (L8); L4 layouts lose
  heave or sway; horizontal angle trades surge vs sway (30°: 0.93/0.62 m/s holdable; 60°: 0.70/0.82);
  3D-vectored L8 costs 28–49 % more horizontally. Benchmark layouts other than L8-HV are designs (grade C/D).
* E2 payload suites: inspection suite adds 33 % energy over propulsion alone in the 0.4 m/s mission.
* E3 environment: station keeping 0 → 0.8 m/s: 0.048 → 6.25 Wh in 30 s.
* E4 external comparison (Gabl et al. 2021, real restrained BlueROV2, thrusters off): HoloOcean BlueROV2
  drag is 3.8–7.2× the measured surge load; implied station-keeping power 4.6–9.4× higher.
  **Negative result: the verified backend is not a validated BlueROV2 hydrodynamic model.**
* E5 baselines: speed-cubic baseline (fitted in calm water) underestimates station keeping in current
  by 97–99.7 %; L0 vs L1 changes OCV work by ~5 %; cell-tolerance resistance changes losses by ~11 %.
* Communication non-interference (scripted backend): PASS (identical command logs, events, deliveries).

## Not done / pending

* Native HoloOcean closed-loop runs (tracking, derating → drift) — require user approval and the
  drag-patched binary, which is NOT present on this machine.
* Native DESERT communication experiments and native non-interference — Docker daemon not running.
* Figures/tables generation, dashboard extension (comms + evidence panels), full documentation
  update (README, API, profiles, validation), paper outline, push to origin, CI run.
* Proxy profiles for HoveringAUV/TorpedoAUV/SurfaceVessel (evidence extracted, profiles not written).

## Supported claims (current evidence)

Generic configurable energy layer; source-traceable profiles with explicit grades; coupling of
actuator effort to battery state; observe-only communication energy from network events;
interval propagation from published ranges.

## Unsupported claims

Physical validation of any vehicle; inflow-aware T200 prediction; temperature/pressure battery
effects; BlueROV2 Standard exact geometry; communication energy of real modems at DESERT source levels.
