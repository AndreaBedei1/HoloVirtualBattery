# Paper outline (Simulation Modelling Practice and Theory)

Working title: **HoloEnergy: A Provenance-Aware Energy Simulation and Validation Framework for
Marine Robots in HoloOcean**

Framing: a simulation methodology (how energy predictions are built from graded evidence, coupled
to vehicle dynamics in closed loop, and verified tick by tick), with the Python framework as its
implementation. BlueROV2 is the reference case; the method does not depend on it.

Every number below is produced by scripts in `experiments/` and stored in
`experiments/results/`; figures are `docs/figures/paper/F*.{png,svg,pdf}` with their data in CSV.

## Research questions (as answered by the current results)

| RQ | Question | Answer from the results | Evidence |
| --- | --- | --- | --- |
| RQ1 | Does actuator-effort propulsion differ from speed-only estimates under current and disturbance? | Yes. A speed-cubic model fitted on the calm-water transit underestimates propulsion energy by 89 % (0.2 m/s) and 98.7 % (0.5 m/s) in station keeping and by 65-91 % on transits in current, and overestimates the heave mission by 68 %; a constant-power model errs by -93 % to +47 % on station keeping and transits and by +255 % on heave (0.8 m/s station keeping is excluded: no layout meets the request) | `tables/baselines.csv`, F08 |
| RQ2 | How do actuator count and orientation trade controllability against energy? | Layouts that share the four vectored horizontals cost the same in surge current (0.158 Wh / 30 s at 0.2 m/s); 2 stern thrusters are 13-17 % cheaper but cannot sway (8.7 m drift); 2 verticals need 42 % more heave energy than 4; 4 horizontals cannot heave; 3D vectoring costs 21-30 % more. A 30 deg horizontal angle halves surge cost relative to 60 deg (2.32 vs 5.47 Wh) and doubles sway cost (4.67 vs 1.99 Wh); 60 deg in surge reaches the 60 A pack limit | `tables/N1_layouts.csv`, `N2_orientation.csv`, `N3_heave.csv`, F06, F07 |
| RQ3 | How large are sensor and compute loads relative to propulsion, by regime? | In a 67 s transit in 0.2 m/s current the inspection suite adds 86 % to propulsion-only energy (2.83 vs 1.52 Wh) and AI vision 23 %; in still water hotel loads dominate station keeping (0.048 Wh / 30 s with zero thrust) | `N5_suites.csv`, F09 |
| RQ4 | Does communication activity change mission energy or battery state? | Network energy depends on strategy (flooding sends 3x the frames for +7 % energy; MAC ACK on a multi-hop line delivers 3/10); for the vehicle, modem energy is small next to propulsion (see cross-layer results) | `desert/comm_matrix.json`, `crosslayer.json`, F10, F11 |
| RQ5 | What uncertainty follows from literature-derived component models? | Intervals exist only where a range is published (e.g. 2.62-2.83 Wh for the inspection transit); most sides stay open because only maxima are published; upper-bound-derived energy is reported separately | F13, `EnergyReport.intervals` |
| RQ6 | How close are predictions to independent measurements where data are comparable? | Only one hydrodynamic comparison is like-for-like; HoloOcean drag is 3.8-4.5x the restrained load of a standard BlueROV2 and 0.86-1.16x the damping identified on a Heavy, so the two references disagree by 3-4x. Component data are reproduced by construction (T200 tables); no mission-level dataset reproduces the initial conditions | `bluerov2_hydrodynamic_external_comparison.md`, `offline/E4_external_drag.csv` |

## 1. Introduction

Energy limits the endurance of marine robots, yet simulators either omit electrical energy or
estimate it from speed. The gap is a model that (i) derives propulsion power from the actuator
effort the controller actually commands in the simulated environment, (ii) composes it with
sensors, computing, communications and battery losses, and (iii) states, for each predicted watt,
where its parameters come from and how good that evidence is. Contributions, each with its result:

1. An energy layer for HoloOcean that allocates the controller's body wrench over arbitrary
   actuator layouts and closes the chain dynamics -> effort -> electrical power -> battery ->
   available thrust in closed loop; the chain closes tick by tick in 42 native runs (force
   residual below 1e-4 N, recomputed power residual below 1e-6 W).
2. An evidence registry (131 records, 144 sources) whose grades are capped by the relation of a
   value to the simulated hardware, with unknown values kept unconfigured and reported.
3. Wrench-equivalent actuation, which evaluates virtual layouts (here 4-8 thrusters) on one
   native rigid body and flags every tick where the native clamp cannot reproduce the virtual
   wrench.
4. An observe-only communication-energy adapter for DESERT, verified not to change network
   behaviour (identical events, deliveries and statistics with and without observation).
5. A verification and validation protocol that separates implementation verification (drag
   units, timestep, energy chain) from vehicle validation, applied to a drag defect in
   HoloOcean 2.3.0 (0.01x of the SI drag) and its one-line fix.

## 2. Related work

Organised by the gap each line of work leaves (papers indexed in
`holoenergy/evidence/data/literature.yaml`):

* **Marine robot energy models and hotel loads.** Power budgets of hovering AUVs (Cruz 2019,
  Carneiro 2021, Vasilescu 2010) and torpedo AUVs (Allen 1997, Bellingham 2010, Hobson 2012,
  Furlong 2012, Roper 2021) give measured or budgeted figures for specific vehicles; they are
  not coupled to a simulator's dynamics.
* **Thruster models and allocation.** T200 characterisation (Lam 2023) and allocation for
  over-actuated vehicles (Garus 2009/2011/2018, Johansen and Fossen 2013, Prasad 2013) supply the
  effort-to-force and force-to-power steps; energy-optimal allocation is usually evaluated
  without battery feedback.
* **Mission-energy estimation and energy-aware planning.** Path planning in currents
  (Koay 2013, Wang 2022, Valachovic 2022, Alam 2021) and runtime estimation (De Carolis 2018,
  Edwards 2017) use speed-based or learned consumption models; RQ1 quantifies what a speed-only
  model misses in station keeping.
* **Batteries.** ECM identification (Chen 2022) and SOC estimation for underwater vehicles
  (Li 2023, Yang 2024, Kim 2025); pressure effects differ in sign between chemistries
  (Li 2022, Zheng 2018), which is why no universal pressure correction is applied.
* **Simulators.** HoloOcean (Potokar 2022, 2024; Romrell 2025) and the sim-to-real analysis of
  Gomes 2025 motivate explicit verification; benchmark simulators with identified BlueROV2
  dynamics (von Benzon 2022) are the comparison point for hydrodynamics.
* **Communication energy.** DESERT Underwater (Masiero et al. 2012,
  doi:10.1109/OCEANS-Yeosu.2012.6263524) simulates protocols, not electrical energy; modem
  transmit/receive/idle energy models (to be verified before citing: Zorzi et al. 2008, IEEE JSAC;
  the shallow-water network energy model of IEEE JOE 33, doi:10.1109/JOE.2008.925892) motivate
  charging each PHY state with datasheet power.
* **Simulation V&V.** Sargent (2013, doi:10.1057/jos.2012.20) and Oberkampf and Roy (2010,
  ISBN 9780521113601) define verification versus validation and the evidence each requires;
  HoloEnergy applies that split to every claim.

## 3. System and energy modelling methodology

Per-tick power from actuator effort (T200 force/power tables at the bus voltage), component
states, converters and battery losses; L0 (bucket) and L1 (Rint, one thermal node) batteries;
6xn configuration matrix and redistributed allocation within voltage-dependent bounds; power
manager with current, voltage and temperature limits feeding back to applied thrust. Figure F01.

## 4. Evidence and provenance framework

Records, sources, relation-capped grades, `use: value|value_max`, unconfigured status, bound
types, dataset records; energy-weighted grade coverage (provenance, not confidence),
upper-bound share, proxy-derived share, stale links, double-counting policy
(`docs/double_counting_policy.md`). Figure F02.

## 5. HoloOcean and communication integration

Native control scheme, 100 Hz fixed step, wrench-equivalent mapping, instance isolation; DESERT
through `holo_desert`, own engine on a non-default port, half-duplex state accounting with late
events charged exactly.

## 6. Verification and validation methodology

* Implementation verification: drag-unit check (official and control rebuild 0.0100x, patched
  1.0000000x; F04), physics step ratio 1.000000 at 100 Hz, tick-by-tick chain closure, wrench
  equivalence, DESERT non-interference, E = sum P t recomputed from raw PHY events (exact for
  9 network configurations).
* Validation hierarchy: component (manufacturer tables), vehicle/subsystem (restrained loads,
  identified damping), mission (only where conditions are reproducible: none so far).
* Calibration/validation split for baselines.

## 7. Experimental evaluation

Native matrix (`experiments/run_native_campaign.py`, 42 runs): layouts x currents, orientation,
heave, transit missions, suites, L0/L1, low-SOC power limit; DESERT matrix (9 configurations);
cross-layer runs (same mission, six network strategies); offline replay campaign for
sensitivity studies.

## 8. Results

RQ1-RQ6 as in the table above, with F06-F13 and the generated tables. Report the 0.8 m/s case
as infeasible for every layout (native clamp, 4.2-5.2 m drift) rather than ranking energies.

## 9. Discussion

What actuator-effort modelling changes for planning; why virtual layouts need consistency
flags; why most energy is graded A while vehicle hydrodynamics remain unvalidated; the cost of
the energy layer (3.4-4.2 ms per tick in Python, 13-16 % of the native step on a shared machine).

## 10. Limitations and threats to validity

HoloOcean BlueROV2 hydrodynamics not validated (external references disagree by 3-4x); T200
static tables only (no inflow model); BlueROV2 pack OCV-SOC and resistance are placeholder/proxy;
no thermal parameters for the enclosure; DESERT source level not mapped to modem electrical
power; proxy vehicle profiles are literature proxies on generic HoloOcean bodies; a single
controller policy (user-selected gains).

## 11. Conclusion

Short summary of RQ answers and of what an independent researcher can reproduce from the
repository.

## Figures and tables

F01 architecture, F02 evidence flow, F03 T200 model, F04 backend verification, F06 layouts,
F07 orientation, F08 station keeping vs current with baselines, F09 payload breakdown,
F10 communication policies, F11 mission energy with/without communications, F13 uncertainty.
Tables from `experiments/results/native/tables/` and `experiments/results/offline/`.
