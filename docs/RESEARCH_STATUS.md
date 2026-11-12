# HoloEnergy research status (v0.2 development, updated 2026-11-12)

Branch `feature/provenance-aware-energy-framework` (pushed to `origin`), created from
`fix/verified-holoocean-drag-backend` (6965411). Tag `v0.1.0` (fdcd7ee) unchanged; no
`v0.2.0` tag; nothing merged to `main`. Phase start: 04f3325. Final commit and CI run of
this phase: [final report](PROVENANCE_FRAMEWORK_FINAL_REPORT.md).

## Software verification

| Check | Result |
| --- | --- |
| CI wheel-verification fix (runtime deps from `uv.lock`, package only from the built wheel; NumPy kept) | run [43272502605](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43272502605): 8/8 jobs green (Ubuntu + Windows, Python 3.10-3.13) |
| Later push (3f6e57e) | run [43286942485](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43286942485): 8/8 green |
| Local unit tests | 308 passed (was 257 at the start of the phase) |
| Lint / format | `ruff check` and `ruff format --check` clean on holoenergy, examples, tools, tests, experiments |
| Installed wheel | resources, registry, allocation, profiles and the `holoenergy` CLI run from an isolated environment |

## Backend verification (not vehicle validation)

Patched HoloOcean 2.3.0 rebuilt here against the installed Launcher UE 5.3.2
(`--engine-kind launcher`), with an unpatched control build. At 100 Hz the control
reproduces the official 0.0100x drag signature and the patched package applies
1.0000000x of its SI drag equation (current and still water); the physics/client step
ratio is 1.000000. Hashes, toolchain and deviations from the official build:
[holoocean_patched_build.md](holoocean_patched_build.md),
[`experiments/results/native/backend`](../experiments/results/native/backend).

## Native experiments (closed loop, 100 Hz, verified package)

`experiments/run_native_campaign.py`, 42 runs, BlueROV2 body; every run closes the chain
tick by tick (max force residual 5.2e-5 N, max recomputed T200 power residual 4e-12 W).
38 runs PASS; 4 wrench-equivalent runs at 0.8 m/s flag ticks where the native 28.75 N
clamp cannot reproduce the virtual wrench (their energy is not comparable).

* Layouts (station keeping, surge current): L8-HV, L6-STD and L4-H45 cost the same
  (0.158 Wh / 30 s at 0.2 m/s; 3.18 Wh at 0.5 m/s) because only the shared vectored
  horizontals work; L4-2H2V is 13-17 % cheaper but cannot sway (8.7 m drift); 3D
  vectoring (L8-VEC30) costs 21-30 % more; at 0.8 m/s no layout holds station
  (4.2-5.2 m drift). Direct and wrench-equivalent mapping of the same L8-HV layout give
  identical energy (identity check of the mapping).
* Orientation (0.5 m/s, 30 s): 30 deg 2.32 / 4.67 Wh (surge / sway current); 45 deg
  3.18 / 2.73 Wh; 60 deg 5.47 / 1.99 Wh, the 60 deg surge case reaching the 60 A pack
  limit (derating on 8 % of ticks).
* Heave mission: 2 verticals (6T) need 42 % more propulsion energy than 4; 4T-H45 cannot
  heave (1.9 m error).
* Transit (accelerate, transit, stop, yaw 180 deg, return): 0.62 / 1.63 / 4.03 Wh at
  0 / 0.2 / 0.4 m/s current; the 6T virtual layout equals 8T (no heave demand).
* Suites (transit, 0.2 m/s): inspection suite +86 % over propulsion-only, AI vision +23 %.
* Battery: L0 is 3.8 % below L1; starting at 3 % SOC in 0.5 m/s current the pack reaches
  its 12.0 V cutoff, thrust is derated to zero and the vehicle drifts 6.4 m.
* Baselines (fitted on the calm-water transit only): speed-cubic underestimates station
  keeping by 89 % (0.2 m/s) and 98.7 % (0.5 m/s) and transits in current by 65-91 %,
  and overestimates heave by 68 %; a constant-power model errs by -93 % to +255 %.
* Overhead: the energy layer costs 3.3-4.3 ms per tick (4.9 ms with dashboard
  telemetry), 12-19 % of the native step on a machine shared with other instances.

## Communications (native DESERT, observe-only)

* Non-interference: identical events, deliveries and session summaries with and without
  the observer (`tools/check_desert_noninterference.py --mode native --port 5571`); only
  wall-clock metadata differs, also between two plain runs.
* E = sum P t recomputed from raw PHY events equals the adapter's energy for all 9
  configurations (direct, MAC ACK, multi-hop static/ACK/flooding, 4-node static vs
  flooding, optical, hybrid). Flooding on 4 nodes sends 3x the frames for +7 % energy;
  MAC ACK on the 500 m multi-hop line delivers 3/10 messages.
* 72-95 % of the acoustic communication energy rests on published upper bounds (RX/listen
  at most 0.8 W), so these energies are upper-bound-dominated estimates.
* Cross-layer (same native transit): the vehicle's acoustic modem adds 1.37 % of mission
  energy (optical 0.57 %), nearly independent of the strategy because listening
  dominates; network-wide energy and delivery differ (multi-hop 27/34, flooding 33/34);
  the trajectory is identical in every case.
* Two accounting defects were found and fixed: silent interfaces of all-node observers
  accrued no listen energy, and late PHY events were rejected by the bus.

## Evidence

Registry: 177 records, 144 sources (grades A 113, B 3, C 40, D 21; 20 unconfigured).
New this phase: hydrodynamic comparison records (Gabl 2021, von Benzon 2022, Wu 2018,
HoloOcean literals), proxy-vehicle records, stale-link detection, proxy-energy share,
double-counting audit including attached modems. Offline E4 now reads all constants
from the registry.

## Negative results kept visible

Speed-only models fail in station keeping; HoloOcean BlueROV2 drag disagrees with
external data (3.8-4.5x Gabl, 0.86-1.16x von Benzon); T200 inflow effects unsupported;
BlueROV2 pack OCV-SOC and thermal parameters unknown; DESERT source levels not mapped to
modem watts; three proxy vehicles (AMOUR, Silver Frog, dual-electric USV) could not be
profiled; no mission-level dataset reproduces its initial conditions.

## Supported claims

Configurable, provenance-aware energy layer for HoloOcean; closed-loop coupling of
actuator effort, electrical loads, battery state and available thrust, verified tick by
tick on the patched backend; arbitrary actuator layouts with explicit consistency flags;
observe-only communication energy verified not to perturb DESERT; interval propagation
from published ranges.

## Unsupported claims

Physical validation of any vehicle; validated BlueROV2 hydrodynamics; inflow-aware T200
prediction; temperature/pressure battery effects; exact BlueROV2 Standard geometry;
real-modem energy at DESERT source levels; validity of the proxy profiles for the named
vehicles.

## Remaining blockers

Real BlueROV2 measurements (pack OCV/R, hotel load, thrust/power in flow) for
calibration and validation; an adapter for native closed-loop runs of the torpedo and
hovering proxies; HoloOcean upstream contribution prepared but not published (needs the
author's authorization).
