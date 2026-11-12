# Referee report G (hostile): Simulation Modelling Practice and Theory

**Manuscript (intended):** "HoloEnergy: A Provenance-Aware Energy Simulation and Validation Framework for
Marine Robots in HoloOcean"

**Material reviewed:** repository `F:\Andrea\HoloVirtualBattery`, branch
`feature/provenance-aware-energy-framework`, tag `v0.2.0`. No manuscript exists yet, so I reviewed the
intended paper as described in `docs/paper_outline_smpat.md`, with the claims and evidence in `README.md`
(first 100 lines), `docs/RESEARCH_STATUS.md`, `docs/PROVENANCE_FRAMEWORK_FINAL_REPORT.md`,
`docs/provenance_framework.md`, `docs/bluerov2_hydrodynamic_external_comparison.md`,
`docs/EVIDENCE_GAPS.md`, `docs/figures/paper/manifest.json` and all paper figures (PNG), and
`experiments/results/native/tables/*.csv`. I also spot-checked `experiments/analyze_native_campaign.py`
(baseline fitting), `holoenergy/evidence/__init__.py` (grade semantics),
`experiments/results/native/benchmark_overhead.json`, the figure CSVs, and the head of
`docs/holoocean_timestep_report.md`. No simulator was run. Web sources are listed at the end.

Severity scale: **Fatal** (by itself justifies rejection at SIMPAT), **Major** (must be fixed before the
paper is reviewable), **Minor** (presentation or consistency).

---

## 1. Summary recommendation: REJECT

The work is careful software engineering around HoloOcean: a Python energy and battery layer, a
hand-curated parameter registry with A-D grades, a wrench-reallocation trick for virtual thruster layouts,
an observer that charges DESERT PHY events with datasheet power, and a patch for a drag-unit bug in
HoloOcean 2.3.0. The documentation is unusually honest about its limits. That honesty is also what sinks
the paper at this journal:

1. **No validation against real data at any level** (G-01). The SIMPAT aims and scope require application
   papers to make "validation/verification with real data" transparent. Component tables are reproduced
   "by construction". The one vehicle-level comparison shows that the simulated BlueROV2 drag, which
   drives 83-97 % of predicted mission energy, is 3.8-4.5x one external reference, and the two external
   references disagree with each other by 3-4x. The title still says "Validation Framework".
2. **The quantitative results are self-referential** (G-02). Every "error" reported for a baseline is
   that baseline's disagreement with HoloEnergy's own output, never with a measurement. The headline
   numbers ("underestimates ... by 89 % ... 98.7 %") describe model-model disagreement against a straw-man
   baseline.
3. **The dominant uncertainty is outside the provenance method** (G-03). Grade shares cover
   electrical-model parameters only. They exclude the hydrodynamics that set the propulsion load, and the
   registry grades the HoloOcean drag literals "A (simulator-exact)" even though external data contradict
   them. In the reference case the main methodological contribution therefore signals high evidence
   quality for numbers whose magnitude is uncertain by up to 4.5-9.3x in power.
4. **Novelty is integration-level** (G-04). Thruster-power-from-effort in simulators, battery plugins with
   thruster consumers, AUV energy plus acoustic-communication simulation, per-state modem energy in DESERT
   and ns-3, and provenance and credibility grading of simulation inputs all exist. The intended
   related-work text makes two statements that are false (Section 5).

Read as a whole, the work is a well-documented release note for a HoloOcean plugin (CI runs, test counts,
CLI commands, dashboard panels), not a simulation-methodology contribution with validated predictive
capability. Counts: **4 Fatal, 13 Major, 8 Minor** (25 issues).

---

## 2. Fatal issues

### G-01 [Fatal] No validation with real data; the title claims a "Validation Framework"
- Mission level: "no mission-level dataset reproduces its initial conditions" (`paper_outline_smpat.md`,
  RQ6; `RESEARCH_STATUS.md`).
- Vehicle level: the only comparisons are drag-force comparisons with two literature sources that
  contradict each other by 3-4x (`bluerov2_hydrodynamic_external_comparison.md` §5-6, §8). No electrical
  quantity (pack current, voltage, energy) of any real vehicle is compared with a prediction.
- Component level: T200 power is "reproduced by construction" from the manufacturer tables, which is
  table lookup and not validation. The T200 data are bollard data applied in inflow; the inflow data
  needed to test them are missing (`EVIDENCE_GAPS.md`).
- Battery: the OCV-SOC curve is a placeholder (D), thermal parameters are placeholders (D), and resistance
  is a cell-only proxy (C) (`EVIDENCE_GAPS.md`).
- The outline admits the problem (`paper_outline_smpat.md` l. 143-144: "The working title keeps
  "validation framework" for the method; no vehicle-level validation has been performed."). A "validation
  framework" that has validated nothing is a protocol proposal. It has not been demonstrated.
- For the reference vehicle this gap is not forced on the authors. A BlueROV2 logs pack voltage and
  current through its power-sense module, and ArduSub logs record thruster commands. Replaying logged
  commands through the T200 tables and comparing with the logged pack current would be a cheap first
  vehicle-level validation. Its absence is not excusable for a journal paper.

### G-02 [Fatal] The results are self-referential: baselines are scored against HoloEnergy, not against data
- `experiments/analyze_native_campaign.py` l. 113-122 fits `P = a + b|u|^3` to HoloEnergy's own
  `power_propulsion_W` on one 67 s calm-water transit. Relative errors are then
  `baseline / holoenergy - 1` (l. 209-214). `baselines.csv` labels the rows "hold-out comparison (model vs
  model)".
- The README presents these numbers as errors of the baseline against reality ("underestimates
  station-keeping propulsion energy by 89 % ... and 98.7 %"). In fact they show only that a cubic in
  over-ground speed cannot see a current, which needs no simulation.
- RQ1 ("Does actuator-effort propulsion differ from speed-only estimates?") is therefore answered
  tautologically, and nothing shows that the actuator-effort prediction is closer to any real vehicle.
- RQ6 ("How close are predictions to independent measurements?") is answered only for drag force. That is
  HoloOcean's quantity, not HoloEnergy's.

### G-03 [Fatal] The dominant energy term rests on contradicted hydrodynamics, and the provenance audit excludes it
- Propulsion is 82.9 %, 93.4 % and 97.3 % of terminal energy in the 0, 0.2 and 0.4 m/s transits
  (`N4_mission.csv`). Its magnitude is set by HoloOcean's drag literal (Cd A = 0.36 m2). That literal gives
  114.85 N at 0.8 m/s, against a measured restrained load of 28.8 N (Gabl et al.). The audit's own power
  ratio is 4.5-9.3x (`bluerov2_hydrodynamic_external_comparison.md` §7).
- Every relative result inherits this factor:
  - "inspection suite adds 86 %" (RQ3);
  - "acoustic modem adds at most 1.37 %" (RQ4);
  - the layout and orientation energy differences (RQ2);
  - the 0.8 m/s infeasibility of every layout, which the authors themselves call "a property of the
    simulated vehicle".

  With drag at the Gabl level, propulsion would fall several-fold and the payload and modem shares would
  rise accordingly. The reported shares are not robust conclusions about marine robots.
- The provenance layer is the paper's central methodological claim, yet it does not cover this. The
  grade shares "describe the electrical-model parameters only (not geometry, dynamics or the
  placeholder-OCV bus voltage)" (`README.md`). The HoloOcean drag literals are registered as "A,
  simulator-exact" (`PROVENANCE_FRAMEWORK_FINAL_REPORT.md`, Evidence registry). The committed native
  summaries even report propulsion energy as grade A (`RESEARCH_STATUS.md`, Evidence).
- An evidence audit that labels the least trustworthy part of the prediction as best-graded, or leaves it
  out, misleads the reader. It does not make the predictions more credible.

### G-04 [Fatal for SIMPAT] The novelty is integration-level and the related work misstates prior art
- Each building block has close prior art (details and URLs in Section 5):
  - thruster electrical power from T200 datasheet curves inside an underwater simulator (Boré et al.
    2025, Stonefish);
  - battery systems with thruster consumers and drain-to-shutdown (Gazebo Sim; UUV Simulator battery
    plugins);
  - a battery plugin that couples SOC to each vehicle's instantaneous propulsive effort (LOTUSim-Energy,
    2026);
  - a modular AUV energy-consumption plus acoustic-communication simulator (Danielis et al. 2022,
    OMNeT++/INET);
  - per-state modem energy in network simulators (DESERT `uwphysical` TX/RX energy counters; ns-3
    `AcousticModemEnergyModel`);
  - provenance of simulation studies (Ruscheinski and Uhrmacher 2017, SIMPROV 2025);
  - graded credibility and pedigree of model inputs (NASA-STD-7009 credibility scale, Sandia PCMM, NUSAP
    and pedigree matrices).
- What remains new is binding these ideas to HoloOcean and the specific grading-and-reporting
  conventions. That is a software contribution, suitable for a software journal or a workshop. It is not
  a methodological advance for SIMPAT.
- `paper_outline_smpat.md` l. 26 ("simulators either omit electrical energy or estimate it from speed")
  and l. 71-72 (DESERT "simulates protocols, not electrical energy") are contradicted by the sources
  above.

---

## 3. Major issues

### G-05 [Major] The provenance grading scheme is ad hoc, one-dimensional and untested
- **Grade semantics.** Grades are author-assigned. Grade A is defined as "exact vehicle/component
  experimental or primary manufacturer evidence" (`holoenergy/evidence/__init__.py` l. 34), so a
  manufacturer's marketing figure ranks with an independent measurement.
- **One axis only.** The only automatic rule is a cap by "relation" (applicability). Reliability,
  measurement conditions, sample size, age and independence are not scored. Established pedigree schemes
  score several of these separately (NUSAP pedigree; ecoinvent data-quality indicators).
- **Weighting.** Coverage is energy-weighted, not sensitivity-weighted. A low-energy parameter with high
  leverage (e.g. the OCV curve, which sets the bus voltage that feeds the T200 tables) carries no weight.
- **No test of usefulness.** Nothing shows that grades predict error, i.e. that A-graded energy is more
  accurate than C-graded energy. There is no inter-rater agreement and no comparison with NASA-STD-7009,
  PCMM or W3C PROV-based M&S provenance.
- **Internal consistency.** The `grade:` fields in `holoenergy/evidence/data/parameters/*.yaml` count
  A 115, B 3, C 40, D 21, while the documents report A 113. This may be the post-cap count, but the paper
  must say which.

### G-06 [Major] Closed-loop coupling is claimed, but the layout and orientation results are static allocation
- **Same dynamics everywhere.** With wrench-equivalent actuation every virtual layout drives the same
  HoloOcean Heavy body with the same wrench. The tables confirm identical dynamics:
  - mean tail tracking error is 0.026565 m for all five layouts at 0.2 m/s and 0.090381 m at 0.5 m/s
    (`N1_layouts.csv`);
  - it is 0.201572 m for both layouts that can heave (`N3_heave.csv`);
  - it is 0.090381 m for every met orientation case (`N2_orientation.csv`).
- **Paper arithmetic.** The energy differences are therefore the same wrench trajectory pushed through
  different static allocation matrices and the static T200 curve. The authors concede that the 42 % heave
  penalty is "close to sqrt(2), as expected from the static T200 curve". The 30/45/60 deg trade-off is
  cosine geometry. None of this needs a closed-loop simulation.
- **Where feedback acts.** Battery-to-thrust feedback is active only in the runs that are flagged
  non-comparable (0.8 m/s, a60 surge) or that depend on the placeholder OCV (low-SOC run). The claimed
  benefit of closed-loop coupling is never isolated. The obvious ablation is missing: an open-loop
  post-processing of the same trajectories, compared with closed loop.
- **Not the real vehicles.** "L6-STD" and "L4-*" run on the Heavy's mass, inertia and drag, so their
  numbers are not BlueROV2 Standard energies.

### G-07 [Major] Weak and straw-man baselines (see Section 7)
- **Straw man.** The headline baseline, a cubic in over-ground speed, is blind to the current by
  construction. No practitioner estimates station-keeping energy in a current that way.
- **Thin water-relative baseline.** The water-relative cubic is fitted on a single 67 s calm-water
  transit and still lands within -15 % to +13 % in surge and sway. Its only large miss (heave, +68 %)
  is a thruster-geometry artefact that a direction-aware quasi-steady model would remove.
- **Missing baselines.** There is no quasi-steady physics baseline, no offline post-processing baseline,
  and no comparison with an existing tool.

### G-08 [Major] The experimental design cannot support general conclusions
- **Small, deterministic sample.** There are 42 deterministic single runs with one controller (gains
  copied from an example and never varied) and one rigid body.
- **Narrow environment.** Currents are steady, uniform and axis-aligned (x or y only); there are no
  waves, turbulence or spatially varying flow.
- **Short windows.** Station-keeping windows are 30 s and include the initial transient; the only
  mission is 67 s.
- **Battery barely exercised.** SOC loss is 0.21-1.36 %, i.e. at most 4 Wh of a pack of roughly 270 Wh,
  so battery dynamics and endurance (the paper's own motivation, "Energy limits the endurance of marine
  robots") are never exercised, except in an artificial run that starts at 3 % SOC.
- **No statistical design.** There is no design of experiments, no sensitivity analysis (Morris, Sobol
  or one-at-a-time over controller gains, drag, OCV, hotel loads) and no replication over initial
  conditions. All of these are listed in the SIMPAT scope.

### G-09 [Major] The uncertainty quantification is nearly empty and mislabelled
- **Scope.** Intervals cover only component loads with published ranges. Propulsion, which is 83-97 % of
  energy, is "not bounded".
- **Widths.** In `F13_uncertainty_intervals.csv` the N4 intervals are [nominal, nominal + 0.0075 Wh], an
  upper side only and 0.2-1.2 % wide. The only two-sided interval (inspection, 2.6245-2.8367 Wh) is
  labelled open on both sides yet drawn as a finite bar.
- **Mislabel.** The outline calls it "2.62-2.84 Wh for the hotel-load part of the inspection transit".
  The CSV shows it is the total terminal energy (nominal 2.829 Wh), not the hotel part.
- **What is needed.** RQ5 needs bounds or a sensitivity analysis on the dominant terms (drag, T200 in
  inflow, OCV). Otherwise "uncertainty" should not appear among the contributions.

### G-10 [Major] The battery model is basic and unparameterised, so the battery-dependent results are artefacts
- **Model.** L1 is Rint plus one thermal node; there is no RC branch.
- **Parameters.** OCV-SOC is a placeholder, thermal parameters are placeholders, and R is a cell-only
  proxy.
- **Consequences.** "L0 is 3.8 % below L1" is, in the authors' words, "the effect of the placeholder OCV
  curve". The low-SOC demonstration (12.0 V cutoff, thrust derated to zero, 6.4 m drift) inherits the
  placeholder OCV for its timing.
- **Upshot.** The battery-to-available-thrust feedback, a selling point of contribution 1, is
  demonstrated only on invented parameters.

### G-11 [Major] Static bollard T200 curves are applied in inflow, and the grade B is not justified
- **The gap.** The static curves are applied while thrusters work against currents of 0.2-0.8 m/s. The
  inflow data are missing ("unconfigured (static mode only)", `EVIDENCE_GAPS.md`). Lam et al. 2023 was
  read "abstract only".
- **The grade.** Grading the static curve "representative (B)" when it is used outside its measured
  condition is optimistic; "proxy (C)" with an explicit extrapolation flag would be defensible.
- **What is needed.** Quantify the advance-ratio error from published open-water propeller data, or
  bound it.

### G-12 [Major] The communication-energy contribution is thin, one-way and partly duplicates DESERT
- **Duplication.** DESERT's `uwphysical` module already binds `tx_power_consumption_` and
  `rx_power_consumption_` and accumulates TX and RX energy (`getConsumedEnergyTx/Rx`). ns-3 UAN has a
  per-state modem energy model. The new parts are idle/listen accrual and attachment to the vehicle bus.
- **Missing cross-check.** The adapter's TX/RX energy is not compared with DESERT's own counters; that
  would be the natural code-to-code verification.
- **One-way coupling.** The coupling is observe-only: battery state cannot affect the modem (no shutdown,
  duty cycling or power-aware MAC). It is therefore post-hoc accounting fed into the bus, not a
  co-simulation coupling.
- **Upper-bound pricing.** 72-95 % of acoustic energy is priced at an upper bound (RX = LISTEN = 0.8 W).
  The F10 caption still states "LISTEN dominates" as if it were a finding.
- **Rate mismatch.** TX airtime comes from a 4.8 kbit/s PHY, while the datasheet power belongs to a modem
  rated up to 13.9 kbit/s.
- **Trivial checks and results.** "Non-interference" holds by construction for a passive observer and is
  not a contribution. RQ4 ("at most 1.37 %") is a single 67 s case whose denominator is inflated by G-03.

### G-13 [Major] The verification is self-consistency, not independent verification
- **Force and power residuals.** "Force residual below 1e-4 N, recomputed power residual below 1e-6 W"
  (contribution 1) compares the framework's bookkeeping with a recomputation from the same tables.
- **Communication energy.** "E = sum P t recomputed from raw PHY events equals the adapter's energy"
  applies the same formula twice.
- **What is missing.** There is no analytic benchmark (e.g. closed-form steady station keeping:
  `F = k U^2` mapped to T200 power, compared with simulated tail power), no code-to-code comparison (e.g.
  Gazebo `LinearBatteryPlugin` on a constant-load profile, DESERT's own energy counters), and no
  convergence of mission energy with respect to tick rate. The timestep report checks clock and physics
  consistency at 20-200 Hz with 12 steps per case; it does not test energy convergence.

### G-14 [Major] The HoloOcean drag-defect claim is unconfirmed upstream, version-specific, and may already be stale
- **Unconfirmed.** Contribution 5 rests on a 0.01x drag-unit defect in HoloOcean 2.3.0 that has not
  been reported to or confirmed by the maintainers (`PROVENANCE_FRAMEWORK_FINAL_REPORT.md`: "Nothing was
  posted").
- **Possibly stale.** HoloOcean 2.4.0 was released on 3 Nov 2026. Its changelog does not mention drag,
  so whether the defect persists is unknown.
- **Contribution level.** A one-line unit fix to someone else's simulator is a bug report, not a
  methodological contribution.
- **Questionable reference case.** Having found that the native BlueROV2 hydrodynamics are 4x off one
  reference, the authors keep them as the reference case. They do not use HoloOcean's custom-dynamics
  route with the experimentally identified BlueROV2 Heavy model of von Benzon et al. (2022), which they
  already cite.

### G-15 [Major] Generality claims are unsupported
- **The claim.** "BlueROV2 is the reference case, not a requirement: other vehicles, batteries and
  backends use the same API" (`README.md` l. 9-10). "The method does not depend on it"
  (`paper_outline_smpat.md` l. 8).
- **The evidence.** All native results use one HoloOcean body. The torpedo and hovering proxies were
  "exercised offline only" for lack of a fin/command adapter. Three proxies could not be built, and USV
  support "depends on the control contract".
- **Upshot.** Generality is asserted from the API design, not demonstrated.

### G-16 [Major] Journal fit: this reads as a software release note, not simulation methodology
- **Missing formal model.** Section 3 of the outline is a single paragraph. Before the paper is
  reviewable it needs:
  - equations for the power manager and derating law;
  - the allocation algorithm, with convergence and bounds handling;
  - the battery state integration scheme and its time-step error;
  - the half-duplex state machine;
  - the coupling semantics (explicit, one-tick lag?).
- **Software material dominates.** The supporting documents centre on CI runs, test counts, lint status,
  CLI verbs and dashboard panels.
- **Scalability unaddressed.** SIMPAT asks for "mathematical and scalability problems encountered". The
  coupled native runs execute at 0.27-0.46x real time (`real_time_factor` in N1-N6), so a 2 h mission
  would take 4-7 h of wall time. Scaling with vehicle count and component count is not studied.
- **Uncontrolled benchmark.** The overhead was measured "while other HoloOcean instances were running
  (shared CPU/GPU)" (`benchmark_overhead.json`).

### G-17 [Major] The committed results do not match the tagged code
- **Dirty trees.** Native runs were "produced from working trees with uncommitted changes (recorded as
  dirty)".
- **Superseded results.** The committed native summaries predate the T200 regrading and "report it as
  A". The committed cross-layer summaries "predate" the fix that adds modem upper-bound and proxy shares
  (`RESEARCH_STATUS.md`).
- **Upshot.** The paper's numbers were produced by code versions that are known to differ from `v0.2.0`.
  Every reported number must be regenerated from a clean, tagged commit. See also Section 9.

---

## 4. Minor issues

### G-18 [Minor] The documents give inconsistent numbers
- Overhead is "12-16 %" in `paper_outline_smpat.md` l. 132 but "12-19 %" in `RESEARCH_STATUS.md` and the
  final report.
- `EVIDENCE_GAPS.md` still gives "0.86-1.16x von Benzon", which the comparison audit (§8, Revision)
  replaced with 1.13-1.21x.
- The grade counts differ as noted in G-05.

### G-19 [Minor] Misleading run status labels
`chain_status = PASS` is given to runs whose request failed badly: `N2-L4-2H2V-sway-c0.5` drifts 8.7 m,
`N3-L4-H45-heave` misses by 1.9 m, and `N6-L8-HV-lowsoc-c0.5` drifts 6.4 m. "PASS" refers only to
bookkeeping closure, so rename it (e.g. `CHAIN_CLOSED`) and report `satisfies_wrench` next to it.

### G-20 [Minor] Figure problems
- **F01 and F02.** Text overflows the boxes ("DESERT via holo_desert", "value/range/bound,", "upper-bound
  share,"), and arrows overlap labels.
- **F04.** Six bars convey two numbers (0.01 and 1.0); a sentence would do.
- **F08.** Four discrete current levels are joined by lines, and the not-met 0.8 m/s point is drawn on
  the same line with no marker distinction.
- **F10.** Configuration codes (A, A2, B, B2, C, C4S, C4F, E, F) are undefined in the figure, and the
  upper-bound share is not shown although it is 72-95 % for the acoustic cases.
- **F11.** Six visually identical bars (communications are about 1.4 %); a table would do, and the x
  labels "multihop" and "flooding" collide.
- **F13.** A finite bar is labelled "open low and high".
- **F09 and F11.** Legends use snake_case ("battery_losses").

### G-21 [Minor] Unverified references
The outline cites two communication-energy references "to be verified before citing". I could not
resolve doi:10.1109/JOE.2008.925892 by web search. Any unresolved citation must be removed or corrected.

### G-22 [Minor] Uninformative cases and loose wording
- Still-water station keeping gives exactly zero propulsion: the body is neutrally buoyant and
  undisturbed. The case carries no information about propulsion modelling.
- "An inspection payload adds 86 %" (`README.md` l. 74) is measured against a configuration with no
  avionics at all. Against the standard vehicle (`N4-L8-HV-transit-c0.2`, 1.626 Wh) the increase is
  about 74 %.

### G-23 [Minor] No energy convergence study
I did not find a study of mission energy against tick rate or against the 10 Hz decimation used for
baseline evaluation (`baseline_energy(..., dt=0.1)`). `trace_vs_summary_relative` reaches about 0.2 %,
which should be reported.

### G-24 [Minor] Uncontrolled performance benchmark
The overhead benchmark ran on a shared machine with other simulator instances (3 repeats). Report a
controlled benchmark with hardware details and variance.

### G-25 [Minor] Mixed-language documentation
The README mixes English and Italian, and several reports (e.g. `holoocean_timestep_report.md`) are in
Italian. Paper-supporting artifacts should be in one language.

---

## 5. Unsupported novelty (closest prior work found)

I found no explicit "first" claim in the reviewed documents (I searched for "first", "novel", "to our
knowledge" and "unique"). The implied novelty claims and their status:

| Implied claim | Status | Closest prior work |
| --- | --- | --- |
| Simulators "omit electrical energy or estimate it from speed" (`paper_outline_smpat.md` l. 26) | **False** | Gazebo Sim battery system: the Thruster system can be a battery consumer (`power_load`, `battery_name`), and the model's joints are turned off when the battery drains; its docs list "consumption should depend on torque" as a known limitation [S1]. UUV Simulator ships `LinearBatteryROSPlugin` and `CustomBatteryConsumerROSPlugin` [S2]. LOTUSim-Energy (Grosset et al., arXiv, Sep 2026) is a maritime simulator for AUVs, ROVs, USVs and UAVs with "energy-aware battery modeling"; as indexed by search, its battery plugin couples SOC estimation to each vehicle's instantaneous propulsive effort and publishes voltage and SOC (full text not read) [S3]. Boré et al. 2025 compute thruster energy in Stonefish from the T200 datasheet (PWM to power, 4th-order polynomial), without a battery [S4]. Volans (vendor) has a power model with hotel, sensor and propulsor terms [S5]. |
| DESERT "simulates protocols, not electrical energy" (`paper_outline_smpat.md` l. 71-72) | **False** | DESERT `uwphysical.cpp` binds `tx_power_consumption_` and `rx_power_consumption_` and accumulates TX and RX energy (`getConsumedEnergyTx`/`getConsumedEnergyRx`), with no idle term [S6]. ns-3 UAN `AcousticModemEnergyModel` (WHOI Micro-Modem) has TX, RX, idle and sleep states and depletion callbacks [S7]. |
| Coupled AUV energy and acoustic-communication simulation | **Not new** | Danielis et al. 2022, WMU J. Maritime Affairs 21:89-107, doi:10.1007/s13437-021-00253-z: a modular OMNeT++/INET model of AUV energy consumption and acoustic communication [S8]. Co-simulation of vehicle dynamics and networks: Gazebo plus TrueTime for AUV docking (Erdemir, Sabancı) [S9]; MAREA, a robotic simulator plus modified ns-3 (Iezzi 2025, PhD thesis) [S10]. |
| Closed-loop battery-to-thrust feedback in underwater simulation | **Contested** | Gazebo Sim (shutdown at depletion, crude) [S1]; LOTUSim-Energy (effort-coupled SOC) [S3]. HoloEnergy's current/voltage/temperature derating is more detailed, but it runs on placeholder battery parameters (G-10). |
| Provenance-aware, evidence-graded simulation parameters | **Not new as a concept** | Provenance of M&S studies: Ruscheinski and Uhrmacher, WSC 2017 [S11]; the W3C PROV-based SIMPROV (PLoS ONE 2025) and related work [S12]. Credibility grading: the NASA-STD-7009 credibility assessment scale [S13]; Sandia's PCMM (Oberkampf, Pilch and Trucano, SAND2007-5948). Pedigree and data-quality matrices: NUSAP and the ecoinvent pedigree matrix [S14]. None is cited in the outline (it cites only Sargent 2013 and Oberkampf and Roy 2010). |
| Experimentally grounded BlueROV2 simulation | **Exists; not used as backend** | von Benzon et al. 2022: a benchmark BlueROV2 Heavy simulator with identified damping and thruster dynamics, experimentally validated [S15]. Energy-aware BlueROV2 control in currents: arXiv 2602.00823 [S16]. AUV battery model tested in simulation and the field: Edwards, Virginia Tech thesis [S17]. |
| Energy layer specifically for HoloOcean | **Plausibly new, but narrow** | I found no HoloOcean energy or battery extension. The HoloOcean changelog up to 2.4.0 (3 Nov 2026) lists none [S18]. Being first for one simulator is not a methodological contribution. |

What I consider genuinely new, and worth a software or tools paper:
- per-parameter source records with extraction locations;
- unknown values kept unconfigured instead of defaulted;
- relation-capped grades propagated into per-run energy shares, with stale-link and double-counting
  checks;
- the per-tick consistency flag for wrench-equivalent layouts.

These need a demonstration that they change a decision or detect an error that would otherwise go
unnoticed. Currently there is none.

**Journal scope.** The Elsevier aims and scope state: "Papers covering applications should be presented
in such a way that the separate steps in the process, such as model development, computer implementation
of the derived model, mathematical and scalability problems encountered and validation/verification with
real data become transparent to all readers." The theory topics include "sensitivity analysis ...
experimental design, meta-modelling" and "methods and algorithms for validation and verification" [S19].
The intended paper has implementation and self-verification, but no real-data validation, no sensitivity
analysis, no experimental design and no scalability analysis.

---

## 6. Missing validation

1. **Component level (independent of the shipped tables):**
   - T200 electrical power at non-zero advance speed (towing tank or flume), or at least a bound from
     open-water propeller theory;
   - the BlueROV2 18 Ah pack OCV-SOC and DC resistance from a relaxed-OCV and pulse test;
   - the measured hotel load of the onboard computer and sensors.
2. **Vehicle level:**
   - pack current and voltage logged on a real BlueROV2 (power-sense module or ArduSub battery log) during
     station keeping in a flume or current, compared with HoloEnergy driven by the logged thruster
     commands (open-loop replay) and by the controller (closed loop);
   - drag of the Heavy configuration, or a switch to an identified model (von Benzon 2022) as backend.
3. **Mission level:** at least one real mission of tens of minutes with a logged pack voltage and SOC
   trajectory, a predicted-vs-measured energy and SOC error, and an error budget split into drag, T200,
   battery and hotel contributions.
4. **Communication level:** modem current measured during TX, RX and listen at the configured bitrate
   and source level, replacing the 0.8 W upper bound.
5. **Validation of the provenance method itself:** evidence that energy graded A, B or C has error
   ordered as the grades imply, or that the audit flags a real mis-configuration that would otherwise
   have gone unnoticed.

---

## 7. Weak baselines

| Baseline used | Problem |
| --- | --- |
| Cubic in over-ground speed, fitted on one calm-water transit | A straw man: blind to current by construction. The 89 % and 98.7 % figures follow analytically. |
| Cubic in speed through water, fitted on the same run | Fitted on 67 s of horizontal motion with 45 deg vectored thrusters, then scored on heave (aligned vertical thrusters). The +68 % is a geometry artefact. In surge and sway it lands within -15 % to +13 % of HoloEnergy. |
| Constant power | Trivial. |

Baselines that are missing and should be added:
- **B1, quasi-steady physics:** `F = 1/2 rho Cd A |v_rel| v_rel` (HoloOcean's own law), then static
  allocation, the static T200 table and hotel loads, without simulation. I expect near-agreement with
  HoloEnergy in every met run (G-06). If so, the closed loop adds value only under saturation or
  derating, and that should be the paper's focus.
- **B2, offline post-processing:** logged HoloOcean thruster forces passed through the T200 tables, with
  no battery feedback. This isolates the effect of closed-loop derating.
- **B3, classical AUV energy model:** `P = P_hotel + F_drag v / eta` as used in endurance and
  path-planning work.
- **B4, existing tools:** a Gazebo Sim `LinearBatteryPlugin` with thruster consumers on the same profile,
  and DESERT's own `uwphysical` energy counters for the communication part.
- **B5, measurement:** any real BlueROV2 power log (Section 6).

---

## 8. Overclaiming (exact quotes)

1. `docs/paper_outline_smpat.md` l. 3: "HoloEnergy: A Provenance-Aware Energy Simulation and Validation
   Framework for Marine Robots in HoloOcean". The same file, l. 143-144: "The working title keeps
   "validation framework" for the method; no vehicle-level validation has been performed." The title
   promises what the paper concedes it does not deliver.
2. `README.md` l. 21-23: "a cubic in over-ground speed, fitted on a calm-water transit, underestimates
   station-keeping propulsion energy by 89 % at 0.2 m/s and 98.7 % at 0.5 m/s." The reference is
   HoloEnergy's own output, not a measurement (G-02).
3. `README.md` l. 23-27: "Using speed through the water removes most of that error ... but a speed model
   still cannot represent which actuators work: it overestimates a heave mission by 68 %". Again
   model-model, and the gap is geometric (G-07).
4. `README.md` l. 6-8: "estimates mission energy and the performance that remains available, stating
   for every predicted watt where its parameters come from and how good that evidence is." Grade shares
   exclude geometry, dynamics and the OCV that feeds the T200 tables, i.e. the terms behind most
   propulsion watts (G-03).
5. `docs/paper_outline_smpat.md` l. 26-27: "Energy limits the endurance of marine robots, yet simulators
   either omit electrical energy or estimate it from speed." This is false (Section 5), and no mission in
   the paper approaches endurance (G-08).
6. `docs/paper_outline_smpat.md` l. 71-72: "DESERT Underwater (Masiero et al. 2012,
   doi:10.1109/OCEANS-Yeosu.2012.6263524) simulates protocols, not electrical energy". This is false
   (`uwphysical` TX/RX energy, [S6]).
7. `docs/paper_outline_smpat.md` l. 34-35: "the chain closes tick by tick in 42 native runs (force
   residual below 1e-4 N, recomputed power residual below 1e-6 W)." This is self-consistency presented as
   verification (G-13).
8. `docs/paper_outline_smpat.md` l. 41-42: "An observe-only communication-energy adapter for DESERT,
   verified not to change network behaviour". This holds by construction for a passive observer (G-12).
9. `docs/paper_outline_smpat.md` l. 44-46: "A verification and validation protocol that separates
   implementation verification (drag units, timestep, energy chain) from vehicle validation, applied to a
   drag defect in HoloOcean 2.3.0 (0.01x of the SI drag) and its one-line fix." Only the verification half
   was applied, and the defect is unconfirmed upstream (G-14).
10. `docs/paper_outline_smpat.md` l. 21 (RQ5): "e.g. 2.62-2.84 Wh for the hotel-load part of the
    inspection transit, open on both sides". The interval is the total terminal energy
    (`F13_uncertainty_intervals.csv`), and "open on both sides" contradicts quoting finite bounds (G-09).
11. `docs/paper_outline_smpat.md` l. 19 (RQ3): "In a 67 s transit in 0.2 m/s current the inspection suite
    adds 86 % to propulsion-only energy". This depends on drag that is 3.8-4.5x the external reference
    (G-03). The README (l. 74, "An inspection payload adds 86 %") also counts base avionics as "payload"
    (G-22).
12. `README.md` l. 9-10: "BlueROV2 is the reference case, not a requirement: other vehicles, batteries
    and backends use the same API." No other vehicle was run natively (G-15).
13. `docs/RESEARCH_STATUS.md`, Supported claims: "closed-loop coupling of actuator effort, electrical
    loads, battery state and available thrust, verified tick by tick on the patched backend". The
    coupling is only active in non-comparable or placeholder-driven runs (G-06, G-10).
14. `docs/figures/paper/manifest.json` l. 36 (F10 caption): "LISTEN dominates." This is an artefact of
    pricing RX and LISTEN at the 0.8 W upper bound (G-12).

---

## 9. Reproducibility gaps

- **Patched simulator.** Native results need a HoloOcean 2.3.0 rebuilt from source against Unreal
  Engine 5.3.2 with an unpublished patch. The documented paths are machine-local (`C:/HOB/...`); no
  binary or container is distributed; a version-matched UE toolchain is needed; and upstream has since
  moved to 2.4.0.
- **DESERT engine.** The engine image `holo-desert-engine:4.0.0-v2` is built locally from `holo_desert`,
  the authors' own separate package. It needs an archival release (DOI) and a citation, and the image
  digest should be published.
- **Clean regeneration.** Native runs come from dirty trees, and committed summaries predate later fixes
  (G-17). Every number in the paper must be regenerated from a clean tagged commit, with a single script
  per table and figure.
- **Archive.** There is no Zenodo or Software Heritage archive of code, traces and figures. GitHub CI
  links are not archival.
- **Literature records.** The registry depends on 60 papers stored as hashes only. That is legitimate
  for copyright, but the extraction locations must be checkable: give page, table or figure for every
  A- and B-graded record.
- **Controller and execution.** Controller gains are inherited from an example script and should be
  documented in the paper. Determinism is claimed but unproven across machines and GPU drivers (UE
  physics); run the deterministic cases on a second machine.
- **Credit to the authors.** The independent reproductions (offline campaign, DESERT matrix, one native
  run) are a strength. They do not cover the full native matrix.

---

## 10. What would change my recommendation

To **major revision**, all of the following:
1. At least one real-data validation of electrical energy on the reference vehicle: logged BlueROV2 pack
   current and voltage against predictions, with an error budget (Section 6, items 1-3).
2. A hydrodynamic backend for the reference case that is consistent with experimental data (e.g. von
   Benzon 2022 through custom dynamics), or results reported as ranges across the two external drag
   references, with the shares in RQ2-RQ4 recomputed.
3. Strong baselines B1-B4, plus the open-loop-versus-closed-loop ablation, showing where the closed loop
   changes the answer.
4. Provenance extended to dynamics and geometry, or the energy-grade metric restricted and renamed. A
   test that the grades carry information (G-05). Positioning against NASA-STD-7009, PCMM, NUSAP and
   PROV-based M&S provenance.
5. A designed experiment with global sensitivity analysis over drag, T200 inflow correction, OCV,
   controller gains and hotel loads, and missions long enough to exercise SOC (more than 20 % depletion).
6. Corrected related work (Section 5) and removal of the false statements.
7. A formal model section, a scalability study and clean-commit reproducibility with an archive DOI.

To **minor revision**: the above, plus validation that includes communication energy at the configured
bitrate and a native run of at least one non-BlueROV2 vehicle.

Without item 1 the paper is out of scope for SIMPAT as an application paper. With items 1-3 only, it
could fit a software or tools venue (e.g. SoftwareX), not SIMPAT.

---

## Sources consulted (web, accessed 2026-11-12)

- [S1] Gazebo Sim battery system: https://gazebosim.org/api/sim/8/battery.html
- [S2] UUV Simulator battery plugins: https://docs.ros.org/en/kinetic/api/uuv_gazebo_ros_plugins/html/CustomBatteryConsumerROSPlugin_8hh_source.html ; https://uuvsimulator.github.io/packages/uuv_simulator/docs/api/gazebo::CustomBatteryConsumerROSPlugin
- [S3] Grosset et al., LOTUSim-Energy, arXiv:2609.17124: https://arxiv.org/abs/2609.17124 (PDF https://arxiv.org/pdf/2609.17124)
- [S4] Boré et al., energy-aware 6-DOF AUV position control (Stonefish, T200 PWM-power polynomial), arXiv:2502.17742: https://arxiv.org/html/2502.17742v1
- [S5] Ocean News, "The Future of UXV Modeling & Simulation" (Volans power model): https://oceannews.com/featured-stories/the-future-of-uxv-modeling-simulation/
- [S6] DESERT Underwater `uwphysical.cpp`: https://github.com/signetlabdei/DESERT_Underwater/blob/master/DESERT_Framework/DESERT/physical/uwphysical/uwphysical.cpp
- [S7] ns-3 UAN framework and `AcousticModemEnergyModel`: https://www.nsnam.org/docs/models/html/uan.html ; https://www.nsnam.org/docs/release/3.42/doxygen/db/d67/classns3_1_1_acoustic_modem_energy_model.html
- [S8] Danielis et al. 2022, doi:10.1007/s13437-021-00253-z: https://elib.dlr.de/146452/
- [S9] Erdemir, Gazebo-TrueTime co-simulation (Sabancı University): https://research.sabanciuniv.edu/36617/
- [S10] Iezzi 2025, MAREA (PhD thesis, Sapienza): https://iris.uniroma1.it/handle/11573/1748242
- [S11] Ruscheinski and Uhrmacher, WSC 2017: https://www.informs-sim.org/wsc17papers/includes/files/065.pdf
- [S12] PROV-based provenance of simulation studies (search summary incl. SIMPROV, PLoS ONE 2025): https://eprints.mosi.informatik.uni-rostock.de/480/ ; https://eprints.soton.ac.uk/470891/1/manuscript.pdf
- [S13] NASA credibility assessment scale (NASA-STD-7009): https://ntrs.nasa.gov/citations/20080015742
- [S14] NUSAP / pedigree matrix: https://leidraad.pbl.nl/tools/35 ; ecoinvent pedigree: https://pre-sustainability.com/?p=30340
- [S15] von Benzon et al. 2022, JMSE 10:1898: https://vbn.aau.dk/ws/files/505520780/jmse_10_01898.pdf
- [S16] Current-harnessing stage-gated MPC (BlueROV2, currents), arXiv:2602.00823: https://arxiv.org/html/2602.00823v1
- [S17] Edwards, "Towards an Intelligent Energy Monitoring System for AUVs", Virginia Tech: https://vtechworks.lib.vt.edu/handle/10919/110316
- [S18] HoloOcean changelog (to 2.4.0): https://byu-holoocean.github.io/holoocean-docs/develop/changelog/changelog.html ; Fossen-based dynamics (Torpedo, Otter): https://byu-holoocean.github.io/holoocean-docs/v2.0.1/agents/docs/fossen-based-dynamics.html
- [S19] SIMPAT aims and scope (Elsevier): https://shop.elsevier.com/journals/simulation-modelling-practice-and-theory/1569-190X

Limits of this review: for S3, S5, S8 and S12 I read abstracts or search-indexed excerpts, not full
texts. Statements about them are restricted to what those excerpts say. PCMM is cited from the Sandia
report identifier, without re-reading it.
