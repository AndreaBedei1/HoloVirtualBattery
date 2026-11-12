# Experimental design and statistics review (Reviewer F)

Target: HoloEnergy, branch `feature/provenance-aware-energy-framework`, tag `v0.2.0`
(`bd11c98`), as a submission to Simulation Modelling Practice and Theory.

## 1. Scope and method

Question asked: do the experiments, as designed and analysed, support the conclusions stated in
`README.md`, `docs/RESEARCH_STATUS.md`, `docs/PROVENANCE_FRAMEWORK_FINAL_REPORT.md` and the
RQ1-RQ6 table of `docs/paper_outline_smpat.md`?

Material read: `experiments/run_native_campaign.py` (`matrix()`, controller, metrics, chain
check), `experiments/analyze_native_campaign.py` (baselines, ablations, `requested_feasible`),
`experiments/run_offline_campaign.py` (E0-E5), `experiments/run_comm_matrix.py`,
`experiments/run_crosslayer.py`, `experiments/make_paper_figures.py` (F06-F08 logic), all 42
`experiments/results/native/N*/*.summary.json` and their committed 0.1 s traces, the native
tables, `desert/comm_matrix.json`, `crosslayer.json`, `benchmark_overhead.json`, the offline
CSVs, the figure CSVs in `docs/figures/paper/`, the campaign logs in `logs/`, the git history
of the campaign window, and the seed handling of `holo_desert`
(`F:\Andrea\HoloWithDesertCommunications\src`).

What was run: only Python on committed results (scripts in the session scratchpad,
`reviews/F/*.py`); every number below that is not quoted from a document was recomputed
from the summaries or the `trace10` files. HoloOcean, DESERT and Docker were not started.
Nothing in the repository other than this file was modified. Out of scope: hydrodynamic
correctness of the external comparison (RQ6 ratios were only sanity-checked against
`E4_external_drag.csv`), battery-model physics, code defects.

Severity: **critical** = a stated primary conclusion does not follow from the evidence;
**major** = a conclusion holds only conditionally, or the design cannot detect the effect it
claims, and a rerun or reanalysis is needed; **minor** = reporting, labelling or definitional
issue that does not change a conclusion once corrected.

## 2. Verdict in brief

The native campaign is a careful *implementation verification* (tick-by-tick chain closure
holds in all 42 runs, infeasible cases are kept and reported). As *experimental evidence for
RQ1-RQ4* it is weaker than the text suggests: the baseline comparison is model against
model with a strawman headline and an extrapolated fair baseline; station-keeping energies
are transient-dominated; the idealised scenario makes many cells identical by construction
(42 runs, 28 materially distinct outcomes); each condition is a single deterministic run
without designed variation; the stochastic DESERT results use one seed; and all results were
generated from dirty working trees while commits were being made. The rerun needed to fix
this is small (about 60 native runs plus seeded DESERT runs; section 6).

## 3. Findings

| ID | Severity | Location | Issue | Evidence | Fix |
| --- | --- | --- | --- | --- | --- |
| F-01 | critical | `paper_outline_smpat.md` RQ1 row; `README.md` "Why actuator effort"; final report "Baselines ... Conclusion"; `analyze_native_campaign.py` | RQ1 states that an "energy-accuracy advantage of actuator effort over a water-relative speed model is shown only for heave and actuator-layout and orientation effects", and the text speaks of baselines that "underestimate" or "err". Every comparison is model against model, with HoloEnergy's own output as the reference. No measured mission energy exists, and the reference propulsion rests on HoloOcean drag that is 3.8-4.5x a measured restrained load. The experiment can show *disagreement* and *expressiveness* (a speed model has no input for layout); it cannot show an *accuracy* advantage for any case, heave included. | `baselines.csv` column `role` = "hold-out comparison (model vs model)"; `experiments/calibration/` and `experiments/validation/` hold no data; `offline/E4_external_drag.csv` ratio 3.83-4.49 at 0.4-1.0 m/s. | Reformulate RQ1 as "how far do speed-based estimates deviate from an effort-based estimate in the same simulator, and which effects can they not represent". Replace "error", "underestimate" and "advantage" by "deviation from the effort-based estimate". State that accuracy needs the measured campaign of `docs/validation_protocol_bluerov2.md`. |
| F-02 | major | `analyze_native_campaign.py` `fit_baselines`, `CALIBRATION = "N4-L8-HV-transit-c0"`; `baselines.csv`; F08 | The baseline design is unfair in both directions. (a) The headline figures (-89 %, -98.7 %) come from an over-ground-speed cubic and from a constant-power model; no current-aware practitioner would use either for station keeping in current, yet the README motivation leads with them. (b) The water-relative cubic is fitted on a single calm-water transit whose water speed spans 0-0.293 m/s and is evaluated at median water speeds of 0.53 m/s (0.5 m/s current) and 0.68 m/s (0.8 m/s), i.e. extrapolated 1.8-2.4x in speed and 6-14x in u^3. (c) The +68 % heave figure applies a model fitted with four 45-degree horizontals to motion produced by four axial verticals. Of the +68.4 %, 24.9 percentage points come from the fitted intercept a = 1.94 W integrated over 20.1 s (+43.6 % without it). The intercept also contributes 10.3 points to the +13.0 % at 0.2 m/s. | `analysis.json`: a = 1.944 W, b = 2338 W s^3 m^-3 (water); in-sample R^2 = 0.997, RMSE 1.27 W (recomputed on `trace10`). Water-speed ranges recomputed per run. | Fit any speed model on a separate calm-water calibration sweep per axis (surge, sway, heave at 0.1-0.8 m/s, steady segments only); report the fitted range and flag extrapolation. Add a no-fit quasi-static baseline (HoloOcean drag at the water-relative velocity, the same allocator, the T200 table): it isolates what closed-loop effort adds beyond steady force balance. Demote the over-ground and constant baselines to a footnote. |
| F-03 | major | N1/N2 `station30` plan (`run_native_campaign.py`); RQ2, F06, F07, F08 | Station keeping starts from rest under a step current at t = 0. The 30 s windows are dominated by the controller's response and do not reach steady state at 0.5 m/s. L8-HV propulsion power in successive 5 s windows from 5 s onward is 330, 541, 503, 433 and 398 W, still falling at the end. Over the feasible station runs, energy per 30 s differs from 30 s x (last-10-s mean power) by -9 % to +19 %. Headline ratios depend on the window: the L8-VEC30 penalty at 0.2 m/s is +29.8 % over 30 s but +37.6 % on last-10-s power, and the L4-2H2V saving is -16.8 % vs -14.7 %. The `mean_tail_*` metrics are not steady-state either. The docs list "transient-dominated 30 s windows" as a threat, but the RQ answers still quote per-30-s energies as layout properties. | `trace10` of N1/N2 runs (scratchpad `transient.py`). | Ramp the current (or start at force equilibrium), run at least 120 s, apply an explicit settling criterion (for example error < 0.05 m and power drift < 1 % per 10 s), and report steady-state power (W) and transient energy (Wh) separately. Restate the RQ2 percentages on steady-state power. |
| F-04 | major | `matrix()`; `SCENARIO` (no sensor noise, neutral buoyancy, currents only along x or y); RQ2, RQ3, RQ4 | The scenario is idealised to the point of degeneracy. In still water, station keeping costs exactly 0 W for every layout. Vertical thrusters never work in station keeping, so L8-HV, L6-STD and L4-H45 are bit-identical at 0.2, 0.5 and 0.8 m/s. The L6-STD and L8-HV transits agree within 3e-6 Wh. Of the 42 runs, 28 have materially distinct outcomes. "Layouts sharing the four vectored horizontals cost the same" is therefore true by construction, not a finding. "In still-water station keeping hotel loads are the only consumption" (RQ3) is an artefact of a perfectly trimmed, noiseless vehicle. | Grouping of identical (plan, current, propulsion, tail error) outcomes over all summaries. | Add disturbances that load the full actuator set: oblique and vertical current components, a small buoyancy or CoG offset, seeded sensor noise. Remove duplicate cells. Qualify the still-water statements as an idealised limit. |
| F-05 | major | Whole native campaign; "Threats to validity" | Each condition is one run of a deterministic simulation with one controller (user-selected gains), one initial state and two current directions. Repeating identical inputs would add nothing, but no designed variation of nuisance factors (gains, current direction, initial offset, window length) is reported either. No native conclusion therefore carries any statement of uncertainty or robustness, and no interval is given anywhere for a native result. Determinism is demonstrated for one run (heave, according to the final report), which exercises neither saturation, power limiting nor cutoff. | `provenance.random_seed` = "none (deterministic plan and controller)"; final report, "Independent reviews" row. | Check bitwise determinism on at least three runs that exercise saturation, derating and cutoff. Replace repetitions by a small designed sensitivity (gains x0.5/x2, current direction 0/45/90 deg, start offset) and report the range of each headline ratio. If sensor noise is added (F-04), use seeded replicates with a pilot-based sample size (section 6). |
| F-06 | major | `run_comm_matrix.py`, `run_crosslayer.py`; RQ4; RESEARCH_STATUS "Communications" | DESERT and the `holo_desert` application layer are stochastic: `network.seed` (default 1) selects the DESERT RNG substream (`bridge.tcl`) and seeds the application RNG. Neither script sets it, so every communication result is a single realisation at seed 1. The delivery claims (multi-hop 27/34 vs flooding 33/34; MAC ACK 3/10 on the 500 m line) and the energy differences (flooding +7 %) are single draws. Wilson 95 % intervals are 0.63-0.90 vs 0.85-0.995 (overlapping) and 0.11-0.60, and even these understate the uncertainty, because the messages share MAC and channel state. Non-interference was checked at seed 1 only. | `comm_matrix.json` `results/*/scenario/network/seed` = 1 for all 9 configurations; `holo_desert/scenarios/network.py` (`seed: int = Field(default=1)`); `crosslayer.json` per-strategy delivery counts. | Run at least 30 seeds per configuration with common random numbers (the same seed set for every strategy). Report mean delivery ratio and network energy with t-based 95 % CIs, and give paired differences between strategies with their CIs. Run the non-interference check at 5 or more seeds. Size n from a 10-seed pilot (section 6). |
| F-07 | major | `analyze_native_campaign.py` (ablation block); `ablation_layers.csv`, `ablation_switches.csv`; outline section 7 | (1) "Ablation" is an additive category decomposition of one run, i.e. an attribution, not an ablation. Its last cumulative row adds internal losses to terminal energy (1.644 Wh is OCV work; the run's terminal energy is 1.626 Wh). (2) The "switches" mix a scenario change (current off) with model changes, and L0-vs-L1 is confounded (F-13). (3) The mechanism behind contribution 1, battery to available-thrust feedback, has no ablation: no run disables `apply_derating_to_actions` to show what closing the loop changes in energy or trajectory. | `ablation_switches.csv`; `layout_config` sets `apply_derating_to_actions: True` in every run. | Rename the decomposition "energy attribution". Ablate the feedback (derating on/off) on the low-SOC run, the 60-degree surge run and one near-boundary current, and report the change in energy, SOC and final position. |
| F-08 | major | `layout_config` (`allocation.method = "redistributed"`); RQ2 | Every layout and orientation energy uses the "redistributed" allocator, while the framework also offers pseudo-inverse and power-IRLS allocation (README). The RQ2 rankings and percentages (VEC30 +21-30 %, 2H2V -13-17 %, 30 vs 60 degrees) are conditional on this policy. Over-actuated layouts are the ones an energy-optimal allocator would change most. | `run_native_campaign.py` `layout_config`; README "Actuator layouts" row. | Run the layout and orientation cells with at least two allocators (redistributed and power-IRLS) and report whether the ranking survives. |
| F-09 | major | All native summaries; `crosslayer.json`; `comm_matrix.json`; RESEARCH_STATUS "Reproducibility notes" | All 42 summaries record commit `c697633` with a dirty tree: the campaign runner itself was untracked, and `run_offline_campaign.py`, from which the runner imports `layouts()` and `suite_components()`, was modified (`suite_components` does not exist at `c697633`). Commits were made while the campaign ran (19:09-19:52 CET). Each summary's embedded `energy_report.provenance.git` records HEAD at report time: six different commits (c697633 x20, 20a76fb x9, c2db7b8 x6, 799b5da x5, 936654a x1, e118bde x1) that do not describe the code executed. For example, N6-lowsoc embeds `e118bde` but lacks the `proxy_energy_Wh`, `proxy_share_percent` and `stale_evidence_links` fields that `e118bde` adds. `holoenergy_version` is 0.1.0. The released runner differs from the executed one (trace writer). The summaries grade propulsion A, the documents B. Only one native run was reproduced. `crosslayer.json` was produced with modified battery, propulsion and actuator modules. | Summaries `provenance.git`, `energy_report.provenance.git`; `git log` timestamps; `logs/native_campaign_{A,B}.log` (41 runs; N1-L8-HV-direct-c0 ran in a separate, earlier invocation). | Rerun the final matrix in one invocation from a clean tagged commit, with no commits during the campaign. Capture the git state once at start and refuse a dirty tree. Record the hash of every imported module. At RTF 0.34-0.38 this costs a few hours (section 6). |
| F-10 | minor | RESEARCH_STATUS and final report ("38 runs PASS"); `requested_feasible`; `make_paper_figures.py` F06/F07; RQ2 "drift" values | Validity definitions are inconsistent. "PASS" is chain closure, not experiment validity: 6 PASS runs did not meet the request (N1-L8-HV-direct-c0.8, N1-L4-2H2V-we-c0.8, N2-L4-2H2V-sway, N2-a60-surge, N3-L4-H45, N6-lowsoc), and 32/42 meet it. `request_met` ignores tracking, so transits that end 0.32-0.96 m off target count as met. F06 marks "not met" without the derating criterion that the analysis uses. F07 marks the 60-degree surge case only as "pack limit". The "drift" values quoted (8.7 m; 4.2-5.2 m; 6.4 m) are mean errors over the last 10 s; the final displacements are 10.4 m, 4.8-6.0 m and 8.2 m. | Summaries; `F06_layouts_station_keeping.csv`; `F07_orientation_tradeoff.csv`. | Use one validity predicate (feasible, settled, chain PASS) in tables, figures and text, and report final displacement as drift. |
| F-11 | minor | `F08_station_keeping_current.csv` / `make_paper_figures.fig_station_current` | F08 draws N1-L8-HV-direct-c0.8 (`request_met` = False) as an ordinary point on the station-keeping-versus-current line, and the caption's -15 to +13 % range is quoted without saying whether that point is included (its value, -13.9 %, lies inside the range). | `F08_station_keeping_current.csv` last row. | Mark the point as infeasible or drop it; state the exclusion rule in the caption. |
| F-12 | minor | `transit_plan`, `heave_plan` (3 s final holds) | Missions end unsettled and are compared over equal time, not equal completed task. Transits end 0.47, 0.96 and 0.32 m from the final reference at 0, 0.2 and 0.4 m/s. The return leg at 0.4 m/s lags up to 1.18 m. The calm-water calibration transit overshoots 0.42-0.54 m at each stop. Heave runs end 0.35 m above the target. | Per-phase errors recomputed from `trace10` (scratchpad `transit.py`). | Extend final holds until a settling criterion holds; report the energy to settle and the terminal error next to each energy. |
| F-13 | minor | N6-L8-HV-L0 vs N4-L8-HV-transit-c0.2; `ablation_switches.csv` | L0 holds the bus at 14.8 V while L1 runs at 16.5-16.8 V (placeholder OCV). Propulsion differs by -4.0 % through the voltage-dependent T200 tables, whereas L1 internal losses are 1.1 % of OCV work. The label "L0 battery (bucket) instead of L1" suggests a battery-fidelity effect; RESEARCH_STATUS correctly calls it the effect of the placeholder OCV, but the table does not. | N6/N4 summaries (`min_voltage_V`, voltage range in `trace10`). | Separate the two effects: L1 with R = 0 vs L1 isolates internal losses, and L0 vs L1 (R = 0) at the same voltage isolates the voltage assumption. Relabel the row. |
| F-14 | minor | `paper_outline_smpat.md` RQ5; final report "Intervals" | "2.62-2.84 Wh for the hotel-load part of the inspection transit" is the interval of the *whole terminal energy* (nominal 2.829 Wh, with propulsion held nominal). The hotel-load part is 1.315 Wh nominal, with interval 1.110-1.322 Wh. | N5-S5 `energy_report.intervals.terminal_energy_Wh`; propulsion 1.514 Wh. | Correct the label or quote the hotel-load interval. |
| F-15 | minor | `README.md` "Horizontal angle" bullet | "60 deg 5.47 / 1.99 Wh, the latter at the 60 A pack limit" attributes the limit to the sway case. The limit is hit in the surge case (5.47 Wh; peak 60.0 A, 7.5 % of ticks); the sway case peaks at 22.2 A. | `F07_orientation_tradeoff.csv`. | "the former". |
| F-16 | minor | RQ2 answer; final report; outline section 8 | Consistency checks are presented as findings. The agreement of direct and wrench-equivalent mapping for L8-HV is an identity by construction (same B matrix). "Tracking is identical across layouts where the request is met" is a design property of wrench-equivalent mapping. The heave ratio 1.42, close to sqrt(2), follows from the static T200 curve and could be computed offline. The T200 power residual is recomputed with the same table. Calling the virtual 6T layout "L6-STD" invites reading the heave result as Standard versus Heavy, although both run on the Heavy body. | `wrench_equivalence_identity.csv` (relative difference exactly 0.0 at 0-0.5 m/s). | Report these as verification items. Phrase layout results as "actuator subsets on the Heavy body". |
| F-17 | minor | `crosslayer.json`; `logs/crosslayer.log`, `crosslayer2.log` | The cross-layer file merges two invocations. In the first, all four acoustic strategies failed ("negative energy from load source"); "none" and "optical" were kept, and the strategies come from a second invocation after the late-event fix (`ecb2024`). The file-level `created_utc`/`git` describe only one invocation (`e118bde`, dirty); per-strategy reports embed 3 different HEADs. | Logs; `results/*/energy_report/provenance/git`. | Rerun all strategies in one invocation (F-09) or document the merge in the file. |
| F-18 | minor | RQ4 answer; RESEARCH_STATUS cross-layer bullet | "In still-water station keeping the modem would be a much larger share" is not backed by a run. In this simulator, still-water propulsion is exactly 0 W (F-04), so the share would only reflect modem against hotel power. | No still-water cross-layer run exists. | Run it with a disturbance, or drop the sentence. |
| F-19 | minor | `run_offline_campaign.py` `baselines`; `offline/E5_baselines.csv` | The committed offline baseline table evaluates its own calibration scenario (`mission_0`: constant error 0.0, cubic -3.3 %) as a row, and uses over-ground speed only. It is not cited by the current documents, but it remains a committed result that contradicts the stated calibration/validation rule. | `E5_baselines.csv` row `mission_0`. | Mark the row "in-sample" or regenerate it with the native protocol. |
| F-20 | minor | `benchmark_overhead.json`; "12-19 % of the native step" | 3 repeats on a machine shared with four foreign HoloOcean instances; the denominator is one run's native step time (RTF 0.34-0.38 across runs). | `benchmark_overhead.json` `machine_note`, `repeats` = 3. | Quote it as an order of magnitude, or repeat at least 10 times on an idle machine and report median and IQR. |
| F-21 | minor | `matrix()` currents 0/0.2/0.5/0.8 m/s | The 0.8 m/s level is infeasible for every layout by a hand calculation (drag 114.9 N > 4 x 28.75 x cos 45 deg = 81.3 N). Six runs confirm what algebra predicts, while the informative quantity, the largest current each layout can hold, is not measured. | Arithmetic verified against the summaries. | Replace 0.8 m/s by a boundary search (for example 0.60/0.65/0.70 m/s, or bisection) per layout. |

Severity counts: 1 critical, 8 major, 12 minor.

## 4. Do the RQ answers follow from their evidence?

| RQ | Verdict | Reason |
| --- | --- | --- |
| RQ1 | Does not follow as stated | Model-vs-model only (F-01). The fair baseline is extrapolated and the heave case is an axis-transfer and intercept artefact (F-02). What is supported: over-ground speed and constant power are blind to current; a water-relative cubic stays within -15 % to +13 % of the effort-based estimate in surge and sway, extrapolated; a speed model has no input for layout. |
| RQ2 | Partly | All numbers verified. They are conditional on the allocator (F-08), on a transient window (F-03) and on the Heavy body; three of five layouts are identical by construction (F-04); 5.47 Wh at 60 degrees is a lower bound (power-limited). |
| RQ3 | Partly | +86 % and +23 % verified for one 67 s transit; they are P x t of mostly upper-bound powers, so the native run adds only voltage feedback (0.4 %). The still-water "regime" is an idealisation artefact (F-04). |
| RQ4 | Partly | 1.37 % and 0.57 % verified. Network delivery and energy comparisons are single-seed draws (F-06). The still-water extrapolation is unsupported (F-18). |
| RQ5 | Follows, with a mislabel | Deterministic interval propagation needs no repetition; the quoted interval is mislabelled (F-14). |
| RQ6 | Follows (sanity check only) | Gabl ratios 3.83-4.49 at 0.4-1.0 m/s match `E4_external_drag.csv`; the von Benzon ratio was not re-derived here. |

## 5. Per-run classification (42 native runs)

Legend. *Met* = `analyze_native_campaign.requested_feasible` (allocation residual < 1e-3,
no native saturation, no derating). *Chain*: PASS-IT = `PASS_WITH_INCONSISTENT_TICKS`.
*Err* = mean error over the last 10 s / final error (m). *Sat* = allocation-saturated /
native-saturated / derated tick fractions. Classes refer to the use the documents make of
each run. **valid** = fit for that use without caveat. **valid with limitation** = usable if
the stated limitation is reported. **invalid** = the energy value must not enter a
comparison; the run may still serve as evidence of infeasibility.

| Run | Prop. Wh | Met | Chain | Err (m) | Sat | Class | Reason |
| --- | --- | --- | --- | --- | --- | --- | --- |
| N1-L8-HV-direct-c0 | 0.000 | yes | PASS | 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | degenerate: zero effort by construction (neutral buoyancy, noiseless sensors); hotel load only (F-04) |
| N1-L8-HV-we-c0 | 0.000 | yes | PASS | 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | degenerate; identity 0 = 0 is trivial (F-04, F-16) |
| N1-L6-STD-we-c0 | 0.000 | yes | PASS | 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | degenerate and duplicate of N1-L8-HV-direct-c0 (F-04) |
| N1-L4-H45-we-c0 | 0.000 | yes | PASS | 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | degenerate and duplicate (F-04) |
| N1-L4-2H2V-we-c0 | 0.000 | yes | PASS | 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | degenerate and duplicate (F-04) |
| N1-L8-VEC30-we-c0 | 0.000 | yes | PASS | 0.00 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | degenerate and duplicate (F-04) |
| N1-L8-HV-direct-c0.2 | 0.158 | yes | PASS | 0.03 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | 30 s window transient-dominated (see F-03); reference for F08 and baselines |
| N1-L8-HV-we-c0.2 | 0.158 | yes | PASS | 0.03 / 0.00 | 0.00 / 0.00 / 0.00 | **valid** | implementation check of the wrench-equivalent identity (identity by construction, F-16) |
| N1-L6-STD-we-c0.2 | 0.158 | yes | PASS | 0.03 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; bit-identical to L8-HV because verticals idle (F-04); 30 s window transient-dominated (see F-03) |
| N1-L4-H45-we-c0.2 | 0.158 | yes | PASS | 0.03 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; bit-identical to L8-HV (F-04); 30 s window transient-dominated (see F-03) |
| N1-L4-2H2V-we-c0.2 | 0.131 | yes | PASS | 0.03 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; −16.8 % over 30 s vs −14.7 % on last-10-s power (F-03) |
| N1-L8-VEC30-we-c0.2 | 0.205 | yes | PASS | 0.03 / 0.00 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; +29.8 % over 30 s vs +37.6 % on last-10-s power (F-03) |
| N1-L8-HV-direct-c0.5 | 3.181 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | not at steady state at 30 s; power still falling in last 10 s (F-03); reference for F08 and baselines |
| N1-L8-HV-we-c0.5 | 3.181 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid** | implementation check of the wrench-equivalent identity (by construction, F-16) |
| N1-L6-STD-we-c0.5 | 3.181 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; bit-identical to L8-HV (F-04); not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N1-L4-H45-we-c0.5 | 3.181 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; bit-identical to L8-HV (F-04); not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N1-L4-2H2V-we-c0.5 | 2.779 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N1-L8-VEC30-we-c0.5 | 3.863 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N1-L8-HV-direct-c0.8 | 6.281 | no | PASS | 4.22 / 4.83 | 0.78 / 0.00 / 0.00 | **invalid** | request not met (allocation saturated 78 % of ticks, 4.2 m drift); energy not comparable; keep only as infeasibility evidence; plotted unmarked in F08 (F-11) |
| N1-L8-HV-we-c0.8 | 6.828 | no | PASS-IT | 4.22 / 4.83 | 0.49 / 0.78 / 0.77 | **invalid** | request not met; native clamp cannot realise the virtual wrench on 78 % of ticks; power-limited; energy refers to forces not applied |
| N1-L6-STD-we-c0.8 | 6.828 | no | PASS-IT | 4.22 / 4.83 | 0.49 / 0.78 / 0.77 | **invalid** | as N1-L8-HV-we-c0.8 (bit-identical) |
| N1-L4-H45-we-c0.8 | 6.828 | no | PASS-IT | 4.22 / 4.83 | 0.49 / 0.78 / 0.77 | **invalid** | as N1-L8-HV-we-c0.8 (bit-identical) |
| N1-L4-2H2V-we-c0.8 | 4.336 | no | PASS | 5.17 / 6.03 | 0.79 / 0.00 / 0.82 | **invalid** | chain PASS but request not met: allocation saturated 79 %, power-limited 82 % of ticks, 6.0 m drift |
| N1-L8-VEC30-we-c0.8 | 6.962 | no | PASS-IT | 4.32 / 4.95 | 0.76 / 0.12 / 0.79 | **invalid** | request not met; 12 % inconsistent ticks; power-limited 79 %; roll/pitch up to 49.6 deg; 4.3 m drift |
| N2-L4-2H2V-sway-c0.5 | 0.000 | no | PASS | 8.70 / 10.45 | 0.00 / 0.00 / 0.00 | **invalid** | infeasible: no sway authority, 0 Wh, 10.4 m final drift; valid only as infeasibility evidence |
| N2-L8-HV-sway-c0.5 | 2.731 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N2-L8-HV-a30-surge-c0.5 | 2.318 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N2-L8-HV-a30-sway-c0.5 | 4.674 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N2-L8-HV-a60-surge-c0.5 | 5.472 | no | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.08 | **valid with limitation** | virtual layout on Heavy body; power-limited on 7.5 % of ticks (min derating 0.968): 5.47 Wh is a lower bound; request not met by the analysis definition; not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N2-L8-HV-a60-sway-c0.5 | 1.995 | yes | PASS | 0.09 / 0.06 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; not at steady state at 30 s; power still falling in last 10 s (F-03) |
| N3-L8-HV-heave | 0.044 | yes | PASS | 0.20 / 0.35 | 0.00 / 0.00 / 0.00 | **valid with limitation** | ends unsettled, 0.35 m above target after a 3 s final hold (F-12); used for the +68 % baseline claim (F-02) |
| N3-L6-STD-heave | 0.062 | yes | PASS | 0.20 / 0.35 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; ends unsettled as N3-L8-HV-heave; √2 ratio follows from the static T200 curve (F-21) |
| N3-L4-H45-heave | 0.000 | no | PASS | 1.89 / 2.20 | 0.00 / 0.00 / 0.00 | **invalid** | infeasible: no vertical authority, 0 Wh, 2.2 m error; infeasibility evidence only |
| N4-L8-HV-transit-c0 | 0.518 | yes | PASS | 0.23 / 0.47 | 0.00 / 0.00 / 0.00 | **valid with limitation** | calibration run of all baselines, so not a hold-out; 0.42-0.54 m overshoot at stops; ends 0.47 m off target (F-12) |
| N4-L8-HV-transit-c0.2 | 1.519 | yes | PASS | 0.37 / 0.96 | 0.00 / 0.00 / 0.00 | **valid with limitation** | fixed time, not fixed task: ends 0.96 m off target and unsettled (F-12) |
| N4-L8-HV-transit-c0.4 | 3.927 | yes | PASS | 0.93 / 0.32 | 0.00 / 0.00 / 0.00 | **valid with limitation** | return leg lags up to 1.18 m; ends 0.32 m off target and unsettled (F-12) |
| N4-L6-STD-transit-c0.2 | 1.519 | yes | PASS | 0.37 / 0.96 | 0.00 / 0.00 / 0.00 | **valid with limitation** | virtual layout on Heavy body; identical to N4-L8-HV-transit-c0.2 within 3e-6 Wh (no vertical demand), redundant (F-04) |
| N5-S0-propulsion-only-transit-c0.2 | 1.520 | yes | PASS | 0.37 / 0.96 | 0.00 / 0.00 / 0.00 | **valid with limitation** | dynamics identical to N4-L8-HV-transit-c0.2; same tracking limits (F-12) |
| N5-S5-inspection-transit-c0.2 | 1.514 | yes | PASS | 0.37 / 0.96 | 0.00 / 0.00 / 0.00 | **valid with limitation** | hotel energy is power × time, mostly upper-bound powers; native run adds only 0.4 % voltage feedback on propulsion |
| N5-S6-ai-vision-transit-c0.2 | 1.518 | yes | PASS | 0.37 / 0.96 | 0.00 / 0.00 / 0.00 | **valid with limitation** | as N5-S5; result is P·t arithmetic |
| N6-L8-HV-L0-transit-c0.2 | 1.458 | yes | PASS | 0.37 / 0.96 | 0.00 / 0.00 / 0.00 | **valid with limitation** | L0-L1 difference is the T200 table at 14.8 V vs 16.5-16.8 V placeholder OCV, not battery fidelity (F-13) |
| N6-L8-HV-lowsoc-c0.5 | 0.448 | no | PASS | 6.44 / 8.18 | 0.63 / 0.00 / 0.69 | **invalid** | cutoff at 9.2 s, thrust zero afterwards, 8.2 m drift; timing set by placeholder OCV (grade D) and the 3 % start; qualitative demonstration of the cutoff path only |

Counts: valid 2, valid with limitation 31, invalid 9. Ten runs fail the request predicate
(the nine invalid runs and N2-L8-HV-a60-surge-c0.5, kept as a lower bound); six of the ten
have chain status PASS (F-10).

## 6. Proposed compact final experiment matrix

Rules for every block:
* one campaign invocation from a clean tagged commit, with no commits during the run (F-09);
* one validity predicate: feasible, settled and chain PASS (F-10);
* currents ramped over 10 s, or the vehicle started at force equilibrium;
* station runs of 120 s, with steady-state power taken as the mean over the final 30 s once
  error < 0.05 m and power drift < 1 % per 10 s, and transient energy reported separately (F-03);
* final holds of at least 10 s on missions (F-12).

Deterministic HoloOcean cells are run once, after a determinism check. Stochastic cells use
seeds with common random numbers across compared conditions. Wall-time estimate: wall time is
about 2.7x simulated time plus about 18 s start-up, from the recorded RTF.

| Block | Purpose (finding) | Cells | Native runs | Repetitions | Priority |
| --- | --- | --- | --- | --- | --- |
| V1 | Wrench-equivalent identity (F-16) | L8-HV direct vs wrench-equivalent, 0.5 m/s surge | 2 | 1 | must |
| V2 | Determinism (F-05) | One duplicate each of an S2 boundary run, the A1 low-SOC run (derating on) and the T1 0.4 m/s transit | 3 | 1 duplicate each, compared bitwise; if not identical, n >= 5 and treat as stochastic | must |
| S1 | Layouts, settled (F-03, F-04) | L8-HV, L4-2H2V, L8-VEC30 x current direction 0/90 deg x 0.2/0.5 m/s | 12 | 1 | must |
| S2 | Feasibility boundary (F-21) | Same 3 layouts, surge current by bisection between 0.55 and 0.80 m/s (about 2 steps) | 6 | 1 | must |
| S3 | Exercise verticals (F-04) | L8-HV vs L6-STD with a vertical current component (or buoyancy offset) | 2 | 1 | must |
| S4 | Oblique current | S1 layouts at 45 deg, 0.5 m/s | 3 | 1 | should |
| O1 | Orientation, settled (F-03) | 30/45/60 deg x surge/sway, 0.5 m/s | 6 | 1 | must |
| H1 | Heave, settled (F-12) | L8-HV, L6-STD (L4-H45 infeasibility stated analytically) | 2 | 1 | must |
| T1 | Transit, settled (F-12) | L8-HV at 0/0.2/0.4 m/s | 3 | 1 | must |
| T2 | Controller sensitivity (F-05) | Gains x0.5 and x2, transit at 0 and 0.4 m/s | 4 | 1 | should |
| B1 | Baseline calibration, disjoint from evaluation (F-02) | Calm water, constant speed per axis: surge and heave at 0.1/0.3/0.5/0.7 m/s, sway at 0.3/0.6 m/s | 10 | 1 | must |
| A1 | Feedback ablation (F-07) | Low-SOC start in 0.5 m/s current with derating on and off; derating off for the 60-deg surge cell (on is in O1) and for one S2 boundary run | 4 | 1 | must |
| A2 | Allocator ablation (F-08) | Power-IRLS for L8-HV, L4-2H2V, L8-VEC30 at 0.5 m/s surge, and 30/60 deg at 0.5 m/s surge | 5 | 1 | must |
| A3 | Battery decomposition (F-13) | Transit 0.2 m/s: L1 with R = 0, and L0 at the L1 OCV voltage | 2 | 1 | should |
| N1 | Seeded sensor noise (only if adopted under F-04) | L8-HV station 0.5 m/s, transit 0.2 m/s | 20 (pilot) | 10-seed pilot, then n = ceil((t(0.975, n-1) s / h)^2) with h = 2 % of the mean | should |
| D1 | DESERT strategies (F-06) | 9 comm-matrix configurations and 6 cross-layer strategies | 0 native (DESERT only) | 30 seeds each with common random numbers; extend until the 95 % CI half-width of the delivery ratio is <= 0.05 | must |
| D2 | Non-interference (F-06) | 3 native scenarios | 0 | 5 seeds | must |
| D3 | Cross-layer coupling | 6 strategies on the native transit | 6 | 1 seed, provided D1 shows vehicle-side modem energy varies < 1 % across seeds (otherwise 10 seeds) | must |

Totals: 61 native runs marked must (about 5 h with one process, about 2.5 h with the two
allowed), plus 29 should; DESERT-only seed runs in addition. Analysis requirements: per-axis
speed models fitted only on B1 and evaluated only on S, O, H and T; the quasi-static drag + T200
baseline reported next to them (F-02); for D1, t-intervals over seeds and paired strategy
differences; robustness ranges for every RQ2 ratio from S4, T2 and A2.

Can be dropped or replaced without loss: the six still-water N1 cells (one hotel-only
reference suffices); the duplicates L6-STD/L4-H45 in horizontal current; the six 0.8 m/s
cells (replaced by S2); N3-L4-H45 and N2-L4-2H2V-sway (structural infeasibility, stated
analytically and kept as one demonstration each); N5 suites (P x t replay offline gives the
same numbers up to 0.4 % voltage feedback; keep one native run for the coupling claim).

## 7. Verified-correct items

* The 42 summaries match `matrix()`: 24 N1, 6 N2, 3 N3, 4 N4, 3 N5, 2 N6. Chain status:
  38 PASS and 4 PASS_WITH_INCONSISTENT_TICKS (all wrench-equivalent runs at 0.8 m/s). Max
  force residual 5.24e-5 N, max recomputed T200 power residual 4.0e-12 W, as stated.
* The calibration run is excluded from the native baseline evaluation, and baselines are never
  scored on their own fitting data in the native analysis. Integration of the 0.1 s traces
  agrees with the 100 Hz summaries within 0.21 %.
* RQ1 numbers: over-ground cubic -89.5 % / -98.7 % (station, 0.2/0.5 m/s) and -65.5 % /
  -90.6 % (transits); water-relative cubic -15.3 % to +13.0 % in surge/sway; heave +68.4 %;
  constant model -92.7 % to +255 %, the quoted range correctly excluding the unmet 0.8 m/s run
  (-96.3 %).
* RQ2 numbers: 0.158 and 3.18 Wh shared by the three vectored-horizontal layouts; L4-2H2V
  -16.8 % / -12.6 %; L8-VEC30 +29.8 % / +21.4 %; heave ratio 1.418; orientation values
  2.32/4.67, 3.18/2.73 and 5.47/1.99 Wh; 60-degree surge derated on 7.5 % of ticks at 60 A.
* Transit totals 0.62/1.63/4.03 Wh; SOC loss 0.21-1.36 %; peak current 4.0-32.6 A; minimum
  voltage 16.30-16.74 V. Suites +86 % and +23 %. Communication shares 1.37 % (acoustic) and
  0.57 % (optical). Delivery counts 27/34 and 33/34.
* Drag 114.9 N at 0.8 m/s against a clamp-limited surge force of 81.3 N; the infeasibility
  argument is arithmetically correct.
* Infeasible and negative outcomes are reported, not hidden: 0.8 m/s for all layouts, 2H2V in
  sway, H45 in heave, low-SOC cutoff. F06 hatches unmet bars. The documents list single
  deterministic runs, transient windows, dirty trees and the absence of vehicle validation as
  threats, and call the baseline comparison "model vs model".
* Offline E0: decimation error of the replay archive 0.008-0.17 %; replay vs trace agreement
  at 1e-15.
* No native run was silently dropped: the logs list 41 runs, and the 42nd
  (N1-L8-HV-direct-c0) ran in an earlier invocation; no `.error.json` files exist.
* The overhead benchmark reports median, min and max over 3 repeats and states the shared
  machine.
