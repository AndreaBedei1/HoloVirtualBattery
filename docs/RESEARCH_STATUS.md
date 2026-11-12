# HoloEnergy research status (v0.2 development, updated 2026-11-12)

Branch `feature/provenance-aware-energy-framework` (pushed to `origin`), created from
`fix/verified-holoocean-drag-backend` (6965411). Tag `v0.1.0` (fdcd7ee) unchanged;
`v0.2.0` tagged on the release commit (version 0.2.0) with the author's approval on
2026-11-12; nothing merged to `main`. Phase start: 04f3325. Final commit and CI run of
this phase: [final report](PROVENANCE_FRAMEWORK_FINAL_REPORT.md).

## Software verification

| Check | Result |
| --- | --- |
| CI wheel-verification fix (runtime deps from `uv.lock`, package only from the built wheel file; NumPy kept) | run [43272502605](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43272502605): 8/8 jobs green (Ubuntu + Windows, Python 3.10-3.13) |
| Later push (3f6e57e) | run [43286942485](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43286942485): 8/8 green |
| Final code commit (52868b7) | run [43293424867](https://github.com/AndreaBedei1/HoloVirtualBattery/actions/runs/43293424867): 8/8 green |
| Local unit tests | 317 passed (257 at the start of the phase) |
| Lint / format | `ruff check` and `ruff format --check` clean on holoenergy, examples, tools, tests, experiments |
| Installed wheel | resources, registry datasets, allocation, proxy profiles and the `holoenergy` CLI run from an isolated environment |
| Independent reviews | software (10 confirmed defects, all fixed with regression tests), scientific (claims corrected below), reproducibility (offline, DESERT matrix and a native run reproduced exactly) |

## Backend verification (not vehicle validation)

Patched HoloOcean 2.3.0 rebuilt here against the installed Launcher UE 5.3.2
(`--engine-kind launcher`), with an unpatched control build. At 100 Hz the control
reproduces the official 0.0100x drag signature and the patched package applies
1.0000000x of its SI drag equation (current and still water); the physics/client step
ratio is 1.000000 ([build](holoocean_patched_build.md),
[`experiments/results/native/backend`](../experiments/results/native/backend)).

## Native experiments (closed loop, 100 Hz, verified package)

`experiments/run_native_campaign.py`, 42 runs on the BlueROV2 body; every run closes the
chain tick by tick (max force residual 5.2e-5 N, max recomputed T200 power residual
4e-12 W). 38 runs PASS; 4 wrench-equivalent runs at 0.8 m/s flag ticks where the native
28.75 N clamp cannot reproduce the virtual wrench (energy not comparable). Layouts other
than L8-HV are virtual layouts evaluated on the HoloOcean BlueROV2 Heavy dynamic body
through wrench-equivalent actuation.

* Layouts (station keeping, surge current): L8-HV, L6-STD and L4-H45 cost the same
  (0.158 Wh / 30 s at 0.2 m/s; 3.18 Wh at 0.5 m/s) because only the shared vectored
  horizontals work; L4-2H2V is 13-17 % cheaper but cannot sway (8.7 m drift); 3D vectoring
  costs 21-30 % more. At 0.8 m/s no layout holds station (4.2-5.2 m drift): HoloOcean's
  drag (114.9 N) exceeds the clamp-limited surge force (about 81 N), a property of the
  simulated vehicle (the restrained load measured on a real standard BlueROV2 is 28.8 N).
  Direct and wrench-equivalent mapping of L8-HV agree exactly where the request is met
  (0-0.5 m/s) and differ by 8.7 % at 0.8 m/s.
* Orientation (0.5 m/s, 30 s): 30 deg 2.32 / 4.67 Wh (surge / sway current); 45 deg
  3.18 / 2.73 Wh; 60 deg 5.47 / 1.99 Wh; the 60 deg surge case is power-limited (60 A) on
  8 % of ticks, so its request is not fully met.
* Heave: 2 verticals need 42 % more propulsion energy than 4 (close to sqrt(2), as the
  static T200 curve implies); 4T-H45 cannot heave (1.9 m error). Where requests are met,
  tracking is identical across layouts: the differences come from geometry and the T200
  curve, not from vehicle behaviour.
* Transit (accelerate, transit, stop, yaw 180 deg, return): 0.62 / 1.63 / 4.03 Wh at
  0 / 0.2 / 0.4 m/s current.
* Suites (transit, 0.2 m/s): inspection suite +86 % over propulsion-only, AI vision +23 %.
* Battery: L0 is 3.8 % below L1, i.e. the effect of the placeholder OCV curve on the bus
  voltage that feeds the T200 tables; starting at 3 % SOC in 0.5 m/s current the pack
  reaches its 12.0 V cutoff, thrust is derated to zero and the vehicle drifts 6.4 m.
* Baselines (fitted on the calm-water transit only, compared model vs model): a cubic in
  over-ground speed underestimates station keeping by 89 % (0.2 m/s) and 98.7 % (0.5 m/s)
  and transits in current by 65-91 %; a cubic in speed through the water errs by -15 % to
  +13 % on the same cases and overestimates heave by 68 %; a constant-power model errs by
  -93 % to +255 %.
* Overhead: the energy layer costs 3.3-4.3 ms per tick (4.9 ms with dashboard telemetry
  and evidence snapshots), 12-19 % of the native step on a machine shared with other
  instances.

## Communications (native DESERT, observe-only)

* Non-interference: identical events, deliveries and session summaries with and without
  the observer in three native scenarios (e01_chat, e05_multihop, e04_congestion); only
  wall-clock metadata differs, also between two plain runs. The SUN convergecast scenario
  does not accept the check's round-robin traffic (fails without observation too).
* E = sum P t recomputed from raw PHY events equals the adapter's energy for all 9
  configurations (direct, MAC ACK, multi-hop static/ACK/flooding, 4-node static vs
  flooding, optical, hybrid). MAC ACK on the 500 m multi-hop line delivers 3/10 messages.
* 72-95 % of the acoustic communication energy rests on published upper bounds (RX/listen
  at most 0.8 W, priced equally), and TX airtime comes from DESERT's 4.8 kbit/s PHY with
  the S2C M datasheet power (rated up to 13.9 kbit/s). Strategy comparisons in energy (e.g.
  flooding: 3x frames, +7 %) inherit both choices.
* Cross-layer (same native 67 s transit in 0.2 m/s): the vehicle's acoustic modem adds at
  most 1.37 % of terminal energy (optical 0.57 %; TX about 48 %, listen 42-52 % of the
  acoustic modem energy). Vehicle modem energy is the same for all strategies because the
  vehicle sends the same messages and never relays; network-wide energy and delivery
  differ (multi-hop 27/34, flooding 33/34); the trajectory is identical in every case. In a
  still-water station-keeping mission the modem would be a much larger share.
* Defects found and fixed: silent interfaces of all-node observers accrued no listen energy;
  late PHY events were rejected by the bus; modem upper-bound and proxy shares were missing
  from the evidence summary (committed cross-layer summaries predate this fix).

## Evidence

Registry: 177 records, 144 sources (grades A 113, B 3, C 40, D 21; 20 unconfigured).
New this phase: hydrodynamic comparison records, proxy-vehicle records, stale-link
detection, proxy-energy share, double-counting audit including attached modems. After the
scientific review, the BlueROV2 profiles link the static T200 curves with relation
`representative` (applied with inflow), so propulsion energy is graded B; the committed
native summaries were produced before this change and report it as A. Grade shares cover
the electrical-model parameters only: not geometry, dynamics, or the placeholder OCV.

## Negative results kept visible

Over-ground speed models fail in station keeping, and water-relative speed models cannot
represent heave or actuator layout; HoloOcean BlueROV2 drag disagrees with external data
(3.8-4.5x Gabl; 1.13-1.21x von Benzon in still water) and the references disagree with
each other; T200 inflow effects unsupported; BlueROV2 pack OCV-SOC and thermal parameters
unknown; DESERT source levels not mapped to modem watts; three proxy vehicles (AMOUR,
Silver Frog, dual-electric USV) could not be profiled; no mission-level dataset reproduces
its initial conditions.

## Supported claims

Configurable, provenance-aware energy layer for HoloOcean; closed-loop coupling of
actuator effort, electrical loads, battery state and available thrust, verified tick by
tick on the patched backend; arbitrary actuator layouts with explicit consistency flags;
observe-only communication energy verified not to perturb DESERT; interval propagation
from published ranges.

## Unsupported claims

Physical validation of any vehicle; validated BlueROV2 hydrodynamics; an energy-accuracy
advantage of actuator effort over a water-relative speed model outside heave/layout
effects; inflow-aware T200 prediction; temperature/pressure battery effects; exact
BlueROV2 Standard geometry; typical (not maximum) modem energy at DESERT source levels;
validity of the proxy profiles for the named vehicles; statistical generalisation (one
controller, one body, deterministic single runs).

## Reproducibility notes

The offline campaign, the DESERT matrix and a native run were reproduced by an
independent reviewer to floating-point precision or exactly. Native runs were produced
from working trees with uncommitted changes (recorded as dirty in each summary); traces are
now written as deterministic gzip with content hashes, and figures without embedded dates.

## Remaining blockers

Real BlueROV2 measurements (pack OCV/R, hotel load, thrust/power in flow, Heavy drag) for
calibration and validation; an adapter for native closed-loop runs of the torpedo and
hovering proxies; HoloOcean upstream contribution prepared but not published (needs the
author's authorization).
