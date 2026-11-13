# Review consolidation

This table covers all 167 findings of reviewers A-H (docs/reviews/). It was drafted by a subagent from the reports, commit messages and test docstrings. The rows touched by the final reruns (B-07, B-08, B-18, C-05, D-11, F-03, F-06, F-09, G-17, H-01, H-03) were then checked against the committed final results (65a06da). Counts in section 2 are the draft's and do not yet include these updates. "Confirmed?" records whether the reviewer reproduced the finding with evidence; it is not a second reproduction.

Repository: HoloVirtualBattery, branch feature/provenance-aware-energy-framework, range bd11c98..HEAD (81b91ea). Draft only; nothing in the repository was modified. 'Open' means no citing commit, test or doc line was found; where a commit appears to address a finding without citing its ID this is stated in the last column. HARDENING_STATUS.md is an outside-repo status file and is cited where it lists a fix.

## 1. Findings

| ID | Reviewer | Severity | Finding (one line) | Confirmed? | Action | Commit | Resolution | Remaining limitation |
|---|---|---|---|---|---|---|---|---|
| A-01 | Literature | major | Component 'manufacturer tables' presented as validation level | yes | code/record fix | 7c20915 | fixed (no test) | T200 profile now DATASHEET; final report l.167 and outline RQ6 still say 'by construction' |
| A-02 | Literature | major | 'No non-bollard T200 data' claim contradicts P001 (Lam 2023) | yes | none yet | — | open | P001 not accessed (access pending approval); README l.438 unchanged |
| A-03 | Literature | major | Battery-loss link printed as 'exact' though record is proxy | yes | code/record fix | 7c20915 | fixed (no test) | Profiles set proxy; audit prints stricter relation |
| A-04 | Literature | major | Gemini 720is (19-74 V) powered from 12-16.8 V bus, grade A, eff 1.0 | yes | state limitation | 7c20915 | documented limitation | Step-up converter declared unconfigured gap in S5; no supply check (see D-09) |
| A-05 | Literature | major | 'Modem adds at most 1.37 %' not an upper bound (RX 0.8 W max only) | yes | rewrite claim | 7c20915 | claim to correct in paper | README l.75, outline RQ4, final report l.150 still say 'at most 1.37 %' |
| A-06 | Literature | minor | Lumen 15 W labelled nominal; source gives peak, 10-48 V | partly | code fix + test | — | fixed + regression test (test_lumen_peak_power_is_an_upper_bound, cited as D-05) | Fix cited under D-05; reviewer used agent page fetch |
| A-07 | Literature | minor | 50 C exposure limit used as discharge cutoff temperature | partly | none yet | — | open | No change found (also C-11) |
| A-08 | Literature | minor | Pack R 13.29 mOhm lower bound; capacity fixed 18 Ah at all currents; tentative spec | yes | none yet | — | open | No change found (see C-02, C-07) |
| A-09 | Literature | minor | RPi 3.9 W H.264-playback record graded exact/A (HDMI attached) | partly | none yet | — | open | Profile caps to B; record unchanged |
| A-10 | Literature | minor | Jetson 12.815 W: nvpmodel not stated, W vs W.s header | partly | none yet | — | open | Grade moved A->B/representative (diff of 2f27fbf, see D-10); nvpmodel still 'not stated' |
| A-11 | Literature | minor | T200 table conditions (Basic ESC, static, low-thrust region) incompletely stated | yes | none yet | — | open | No change found |
| A-12 | Literature | minor | Gabl active-thrust still-water cases dismissed as 'not drag' | yes | none yet | — | open | No change found |
| A-13 | Literature | minor | DVL power-up time/35 W surge duration not published; record wording | partly | none yet | — | open | No change found |
| A-14 | Literature | minor | WHOI bridge 0.3 W idle assumes transmitter asleep (bridge idles 791 mW) | partly | none yet | — | open | No change found |
| A-15 | Literature | minor | SX1276 TX currents taken from FSK Table 6, not LoRa Table 10 | partly | none yet | — | open | No change found |
| A-16 | Literature | minor | Source conflicts (VN-100 200 vs 220 mW, WHOI hibernate) not recorded | partly | none yet | — | open | No change found (see D-15) |
| A-17 | Literature | minor | BlueROV2 runtime hours tied to 15.6 Ah pack, relation exact/A | partly | none yet | — | open | No change found |
| A-18 | Literature | minor | REMUS hotel-power example is a model assumption, not vehicle data | yes | none yet | — | open | No change found |
| A-19 | Literature | minor | P023 Table I rows misaligned in source; repo realignment consistent | yes | none yet | — | open | Advisory; no change needed found |
| A-20 | Literature | minor | L0 bucket at 38 kWh; 40 % overstatement only in a note | yes | none yet | — | open | No change found |
| A-21 | Literature | minor | Proxy force->power tables pair design predictions/drag estimates with measured power | yes | none yet | — | open | No change found |
| A-22 | Literature | minor | kT ~5 W/N from P017 has no printed unit | yes | none yet | — | open | No change found |
| A-23 | Literature | minor | RQ6 1.13-1.21 ratio range vs identified 0.72 m/s limit and 0.86-1.16 | yes | none yet | — | open | 73fe949 flags values beyond 0.72 m/s and adds results file; ID not cited |
| A-24 | Literature | minor | Bar30 60 uW at 1 sample/s, no VDD, not the operating rate | partly | none yet | — | open | No change found |
| A-25 | Literature | minor | Author name 'Benzon' should be 'von Benzon' | yes | none yet | — | open | No change found |
| B-01 | Physics | critical | Native currents hit reverse T200 branch (1.38-1.42x power); layout/orientation energies biased | yes | redesign experiment | 914ed41 | design change (FINAL_EXPERIMENTS.md) | Head-on + 45 deg currents; final matrix still running, results not committed |
| B-02 | Physics | major | Allocation bounds at OCV; spurious POWER_LIMITED derating (81.5 % ticks) | yes | code/record fix | 5d15064 | fixed (no test) | Allocation now at voltage under rated current (cited as B-02/E-07) |
| B-03 | Physics | major | Equal layout energies / zero still-water power are body properties, not findings | yes | state limitation | 7c20915 | documented limitation | FINAL_EXPERIMENTS.md l.66-67; 7c20915 cites B-03 for the damping fix (see B-18) |
| B-04 | Physics | major | Isotropic drag makes RQ2 orientation result conditional (sway 0.86x vs 1.9x) | partly | state limitation | — | documented limitation | EXP10 part 4 (run_sensitivity.py cites B-04): orientation conclusions conditional on drag law |
| B-05 | Physics | major | Speed-model 'heave overestimate 68 %' is a 2^0.75 geometry factor | yes | rewrite claim | — | claim to correct in paper | RQ1 correction listed in HARDENING_STATUS |
| B-06 | Physics | major | -15..+13 % baseline spread comes from branch/damping, not drag isotropy | yes | rewrite claim | — | claim to correct in paper | HARDENING_STATUS 'Claims to correct'; B-01 redesign pending results |
| B-07 | Physics | major | Transit energy includes Unreal ground-referenced damping (19-79 % of resistance) | yes | report damping share per run and phase | 65a06da | claim to correct in paper | Reported in final_runs.json: 21 % (calm), 12 % (0.2 m/s), 5 % (0.4 m/s) of time-mean resistance; up to 81 % in the 0.2 m/s return leg. Transit energies stay simulator-conditional |
| B-08 | Physics | major | Transits end unsettled; same mission at three currents; request_met True | yes | redesign experiment | 914ed41, 65a06da | design change (FINAL_EXPERIMENTS.md) | 10 s end hold; final tracking error 0.000/0.025/0.236 m (0.2/0/0.4 m/s); request_met now separated from tracking |
| B-09 | Physics | major | Station-keeping 30 s window includes transient; not steady state | yes | none yet | — | open | F-03 redesign (90 s, last 30 s) addresses the same issue; B-09 not cited |
| B-10 | Physics | major | Quoted layout/baseline percentages rest on reverse-branch cost asymmetry | yes | none yet | — | open | Superseded only when final matrix is committed |
| B-11 | Physics | major | Proxy profiles: 'only electrical models change' overstated (surge limit etc.) | yes | none yet | — | open | No change found |
| B-12 | Physics | minor | Redistributed allocation silently changes wrench (VEC30 roll 15->49.6 deg) | yes | none yet | — | open | No change found |
| B-13 | Physics | minor | 'Chain closes' PASS includes runs that missed the request | yes | none yet | — | open | FINAL_EXPERIMENTS.md l.37 redefines 'request met'; ID not cited |
| B-14 | Physics | minor | T200 bollard curves in inflow: bias direction unstated | partly | none yet | — | open | Order-of-magnitude estimate only; grade B kept |
| B-15 | Physics | minor | 'Max holdable current' / 'exact for simulator' ignores reverse branch and clamp | yes | none yet | — | open | No change found |
| B-16 | Physics | minor | L6-STD 'BlueROV2 Standard' proxy energy equals L8-HV in tested cases | yes | none yet | — | open | No change found |
| B-17 | Physics | minor | No added-mass term in simulator; transient claims overstated | partly | none yet | — | open | Source reading only; no registry record added |
| B-18 | Physics | minor | UE damping update v/(1+c dt) vs implemented form differs 11-51x tolerance | yes | doc/record fix | 7c20915 | fixed (no test) | MODEL_EQUATIONS.md and the record now give v(1 - c dt); the commit message of 7c20915 mislabels this fix as B-03 (history not rewritten) |
| C-01 | Battery | major | Voltage-limited operation unreachable: pack latches at first limited tick | yes | code fix + test | 69bd3d7, 5d15064 | fixed + regression test (test_voltage_limited_operation_does_not_latch_while_ocv_remains_above_limit; test_env_low_soc_operates_voltage_limited_instead_of_latching) | Latch only when OCV <= cutoff |
| C-02 | Battery | major | SOC-0 inconsistent with 2.5 V/cell capacity; L1 overstates energy above 12 V | yes | none yet | — | open | Model 242-265 Wh vs 264 Wh datasheet; no fix found |
| C-03 | Battery | major | Stale-link check misses resistance temperature curves / SOC-T maps | yes | code fix + test | 69bd3d7 | fixed + regression test (test_resistance_temperature_factors_make_the_battery_loss_link_stale) | — |
| C-04 | Battery | major | Battery-loss provenance overstated; coverage ignores D-grade parameters | yes | code fix + test | 69bd3d7 | fixed + regression test (test_placeholder_ocv_dependence_is_reported) | Link relation part fixed under A-03 |
| C-05 | Battery | major | L0-L1 '3.8 %' difference does not measure battery fidelity | yes | split the difference | 65a06da | claim to correct in paper | Final EXP5/EXP8 transit at 0.2 m/s: propulsion 1.6396 Wh (L1) vs 1.5710 Wh (L0), +4.4 %, from T200 power evaluated at the L1 bus voltage; L1 battery losses 0.0201 Wh are a separate term. Not a battery-model validation |
| C-06 | Battery | major | Thermal placeholders: model heats 19.9 K vs 37.9 K datasheet cell | yes | none yet | — | open | Thermal parameters remain placeholders (grade D) |
| C-07 | Battery | minor | Path resistance (interconnects, PSM) and propulsion eta=1 under-represented | yes | none yet | — | open | No change found |
| C-08 | Battery | minor | eta=1.0 gap triggers no runtime warning | yes | none yet | — | open | No change found |
| C-09 | Battery | minor | Proxy L0 packs with max_power null impose no limit (360 MW tick) | yes | none yet | — | open | No change found |
| C-10 | Battery | minor | REMUS 24 V label from 1997 pack not listed in placeholders | partly | none yet | — | open | No change found |
| C-11 | Battery | minor | 50 C exposure statement applied as operating cutoff on average node | partly | none yet | — | open | No change found |
| C-12 | Battery | minor | Cold-capacity convention latches abruptly; calibration flag at 20 C | partly | none yet | — | open | See E-17 |
| C-13 | Battery | minor | Endurance estimates optimistic (+7.6 % v0.2, +22 % v0.1) | yes | none yet | — | open | No change found |
| C-14 | Battery | minor | minimum_voltage_V logs start-of-tick voltage | yes | none yet | — | open | Error ~1.5e-4 V; negligible |
| C-15 | Battery | minor | OCV range not checked against thruster-table domain at config time | yes | none yet | — | open | Duplicate of E-18 |
| C-16 | Battery | minor | Legacy v0.1 pack (R 0.04 Ohm) selectable; changes conclusions (-12 %) | yes | none yet | — | open | No change found |
| D-01 | Component | major | 'At most 1.37 %' acoustic share is not an upper bound (2.6-12.1 % at 8-55 W) | yes | rewrite claim | 7c20915 | claim to correct in paper | EXP10 part 2 done; README/outline/report wording unchanged |
| D-02 | Component | major | Cross-layer cannot show strategy->vehicle battery effect (vehicle never relays; RX=LISTEN) | yes | none yet | — | open | 89b78ff adds relay strategies, ID not cited; RX=LISTEN power still equal |
| D-03 | Component | major | PHY operating point mismatches optical/acoustic device charged | yes | redesign experiment | 914ed41 | design change (FINAL_EXPERIMENTS.md) | Optical at 5 m/250 kbit/s; acoustic PHY remains DESERT 4.8 kbit/s |
| D-04 | Component | major | Payload suites assume continuous full power for whole mission | yes | none yet | — | open | 5713394 adds phase scheduling (EXP6), ID not cited; continuous case remains |
| D-05 | Component | major | Lumen 15 W is peak, not nominal; S5 upper bound understated | partly | code fix + test | — | fixed + regression test (test_lumen_peak_power_is_an_upper_bound) | Commit 2f27fbf does not cite the ID; HARDENING_STATUS lists D-05 |
| D-06 | Component | major | Double-count check flags physically distinct nav devices | yes | code/record fix | 5d15064 | fixed (no test) | docs/double_counting_policy.md:7 cites D-06; warning now states double-count condition |
| D-07 | Component | major | Legacy sensors: schema bypasses 0 W ground-truth rule | yes | code fix + test | 5d15064 | fixed + regression test (test_legacy_sensor_schema_obeys_the_sensor_policy) | — |
| D-08 | Component | major | Closed loop navigates on 0 W ground truth, no nav sensor budget | partly | state limitation | — | documented limitation | FINAL_EXPERIMENTS.md l.44 (cites D-08) |
| D-09 | Component | major | No supply-voltage domain check; converters at eta=1 | yes | none yet | — | open | A-04 only declares gap; no code reads supply_V |
| D-10 | Component | major | Jetson 12.815 W graded A/exact; units W vs W.s, conditions | partly | code/record fix | — | fixed (no test) | Record now B/representative (diff of 2f27fbf; HARDENING_STATUS lists D-10); nvpmodel not stated |
| D-11 | Component | major | Committed results from dirty trees, untracked runners, merged invocations | yes | rerun from clean commit | 5713394, 81b91ea, 65a06da | fixed (no test) | Final results regenerated from clean 81b91ea (36 native runs, comm matrix, cross-layer); runners refuse dirty trees. Old 42 runs remain only as superseded history |
| D-12 | Component | minor | RX = LISTEN power in 12 of 13 comm profiles; receive logic has no energy effect | yes | none yet | — | open | No change found |
| D-13 | Component | minor | No quantity==electrical_power check on comm records (bitrate accepted as 15 kW) | yes | none yet | — | open | No change found |
| D-14 | Component | minor | Sensor mapping inconsistencies (Ping360 as multibeam, 'exact') | partly | none yet | — | open | No change found |
| D-15 | Component | minor | Missing conditions / wording slips (VN-100 220 vs 200 mW, ZED-F9P) | partly | none yet | — | open | No change found |
| D-16 | Component | minor | Peaks and transients not modelled (A50 35 W, SBE49 750 mA, etc.) | partly | none yet | — | open | No change found |
| D-17 | Component | minor | Default includes:modem_signal_processing contradicts 'excludes MCU' | partly | none yet | — | open | No change found |
| D-18 | Component | minor | Hybrid config F never switches to optical (threshold 1e13) | yes | none yet | — | open | No change found |
| D-19 | Component | minor | 'Independent' recomputation reuses adapter assumptions | yes | none yet | — | open | 91cee7e adds an independent check; same assumptions |
| D-20 | Component | minor | Docstring says holo_desert manages Docker; code uses manage_engine=False | partly | none yet | — | open | No change found |
| D-21 | Component | minor | Jetson budgets omit MAXN/Super modes; compute README inconsistent | partly | none yet | — | open | No change found |
| D-22 | Component | minor | Energy per message dominated by LISTEN over arbitrary horizon | yes | none yet | — | open | No change found |
| E-01 | Numerical | major | Interval deltas ignore rail converter efficiency | yes | code fix + test | 5d15064 | fixed + regression test (test_intervals_lower_bound_open_and_converter_scaling) | — |
| E-02 | Numerical | major | Interval uses record.value regardless of component 'use:' | yes | code fix + test | 5d15064 | fixed + regression test (test_intervals_lower_bound_open_and_converter_scaling) | — |
| E-03 | Numerical | major | Lower-bound battery-loss record shown with finite upper plus open_upper | yes | code fix + test | 5d15064 | fixed + regression test (test_intervals_lower_bound_open_and_converter_scaling) | — |
| E-04 | Numerical | major | Stale link missed for resistance_soc_temperature_curves | yes | code fix + test | — | fixed + regression test (test_resistance_temperature_factors_make_the_battery_loss_link_stale; fixed under C-03) | 69bd3d7 cites C-03, not E-04; same defect |
| E-05 | Numerical | major | Voltage limiter and cutoff latch share threshold | yes | code fix + test | 5d15064 | fixed + regression test (test_env_low_soc_operates_voltage_limited_instead_of_latching) | Test docstring cites C-01/E-05 |
| E-06 | Numerical | major | wrench_equivalent charges energy for thrust the native clamp removes (6.8 %) | yes | code fix + test | 5d15064 | fixed + regression test (test_virtual_layout_is_charged_only_for_thrust_the_native_body_applies) | Also FINAL_EXPERIMENTS.md l.41 |
| E-07 | Numerical | major | Actuator-domain factor derates thrust that is available | yes | code/record fix | 5d15064 | fixed (no test) | Cited as B-02/E-07 |
| E-08 | Numerical | major | KeyError for device appearing mid multi-tick step | yes | code fix + test | 5d15064 | fixed + regression test (test_multi_tick_step_with_device_appearing_mid_step) | — |
| E-09 | Numerical | minor | allocation.method power_irls raises in env (no power functions) | yes | code fix + test | 7c20915 | fixed + regression test (test_power_irls_allocation_runs_in_the_env) | — |
| E-10 | Numerical | minor | IRLS weights use p(abs(x)), losing direction (reverse 39-45 % dearer) | yes | code/record fix | — | fixed (no test) | allocation.py diff in 7c20915 uses p(x); commit cites E-09 only |
| E-11 | Numerical | minor | Downsample keeps extra row; baseline energy +0.04-0.21 % | yes | none yet | — | open | No change found |
| E-12 | Numerical | minor | initial_soc taken after first tick | yes | none yet | — | open | No change found |
| E-13 | Numerical | minor | derated_tick_fraction counts CUTOFF ticks | yes | none yet | — | open | No change found |
| E-14 | Numerical | minor | Residual norm mixes N and N.m (unit-dependent thresholds) | yes | none yet | — | open | No change found |
| E-15 | Numerical | minor | Converter loss by cancellation gives negative rounding noise | yes | none yet | — | open | Magnitude ~1e-18 Wh |
| E-16 | Numerical | minor | State energy booked to state after commit_service | yes | none yet | — | open | Totals correct; per-state split off |
| E-17 | Numerical | minor | Identity curves [[25,1]] flag all native ticks outside calibration | yes | none yet | — | open | No change found |
| E-18 | Numerical | minor | Only nominal voltage checked against actuator domain | yes | none yet | — | open | Duplicate of C-15 |
| E-19 | Numerical | minor | dbm_to_watt/Quantity accept NaN/inf; degC below -273 accepted | yes | none yet | — | open | units.py diff (rate unit) unrelated |
| E-20 | Numerical | minor | interpolate(nan) raises IndexError | yes | none yet | — | open | No change found |
| E-21 | Numerical | minor | relative_difference falls back to absolute Wh when reference is 0 | yes | none yet | — | open | Currently harmless |
| E-22 | Numerical | minor | Time accumulated by repeated addition (1.9e-12 s drift) | yes | none yet | — | open | No change found |
| E-23 | Numerical | minor | terminal_energy low reported as number although open_low non-empty | yes | none yet | — | open | No change found |
| E-24 | Numerical | minor | Independent check ignores resistance temperature curves/maps | partly | none yet | — | open | Evidence column not fully read; no change found |
| E-25 | Numerical | minor | L0 voltage_dependence reports 0 Wh though propulsion uses voltage tables | yes | code/record fix | 5d15064 | fixed (no test) | — |
| F-01 | Exp. design | critical | RQ1 'advantage over water-speed model' is model vs model, no data | yes | rewrite claim | — | claim to correct in paper | HARDENING_STATUS; FINAL_EXPERIMENTS.md l.62-65 |
| F-02 | Exp. design | major | Baseline design unfair (over-ground cubic, constant power; in-sample R2 0.997) | yes | state limitation | — | documented limitation | FINAL_EXPERIMENTS.md: comparison is model vs model; baseline set unchanged |
| F-03 | Exp. design | major | Station keeping from rest under step current; window not steady | yes | redesign experiment | 914ed41, 65a06da | design change (FINAL_EXPERIMENTS.md) | 90 s runs, last 30 s steady window; steady-window feasibility reported separately (oblique runs saturate 21.6 % of the run in the transient only) |
| F-04 | Exp. design | major | Scenario degenerate: still-water station keeping 0 W for all layouts | yes | state limitation | — | documented limitation | FINAL_EXPERIMENTS.md l.66-67 (cited as B-03) |
| F-05 | Exp. design | major | One deterministic run per condition, one controller, two current directions | partly | none yet | — | open | Oblique cases added (914ed41, cites 'Review F'); no repeats |
| F-06 | Exp. design | major | Comm runs use seed 1 for all configurations; no variance | yes | redesign experiment | 914ed41, b73ae9f | design change (FINAL_EXPERIMENTS.md) | 20 seeds: 8 of 9 configurations identical across seeds (no stochastic channel or contention); B2 61/200 delivered (Wilson 95 % 0.245-0.372) |
| F-07 | Exp. design | major | 'Ablation' is attribution; derating applied in every run | partly | none yet | — | open | No change found |
| F-08 | Exp. design | major | Only redistributed allocator used for layout energies | partly | none yet | — | open | EXP10 part 3 compares allocators (<0.13 %); ID not cited |
| F-09 | Exp. design | major | All 42 summaries from dirty tree (c697633), untracked runner | yes | rerun from clean commit | 81b91ea, 65a06da | fixed (no test) | As D-11 |
| F-10 | Exp. design | minor | PASS = chain closure, not experiment validity (6 PASS missed request) | yes | none yet | — | open | See B-13 |
| F-11 | Exp. design | minor | F08 plots request_met=False point as ordinary; -15..+13 % caption | yes | none yet | — | open | No change found |
| F-12 | Exp. design | minor | Missions end unsettled; compared over equal time (0.32-0.96 m error) | yes | none yet | — | open | 10 s hold added (see B-08); ID not cited |
| F-13 | Exp. design | minor | L0 14.8 V vs L1 16.5 V changes propulsion -4.0 % | yes | none yet | — | open | No change found (OCV placeholder) |
| F-14 | Exp. design | minor | 'Hotel-load interval' 2.62-2.84 Wh is whole terminal-energy interval | yes | none yet | — | open | See H-11 |
| F-15 | Exp. design | minor | 60 A pack-limit attributed to sway case; occurs in surge case | yes | none yet | — | open | No change found |
| F-16 | Exp. design | minor | Direct vs wrench-equivalent agreement is an identity by construction | yes | none yet | — | open | No change found |
| F-17 | Exp. design | minor | Cross-layer file merges two invocations; acoustic strategies failed in first | yes | none yet | — | open | Cross-layer rerun pending |
| F-18 | Exp. design | minor | 'Still water: modem much larger share' not backed by a run | yes | none yet | — | open | No change found |
| F-19 | Exp. design | minor | Offline baseline table scores its own calibration scenario | yes | none yet | — | open | No change found |
| F-20 | Exp. design | minor | Overhead benchmark: 3 repeats on shared machine | yes | none yet | — | open | No change found |
| F-21 | Exp. design | minor | 0.8 m/s infeasible for every layout (114.9 N > 81.3 N) | yes | none yet | — | open | 0.8 m/s level absent from final matrix (0, 0.2, 0.4) |
| G-01 | Hostile SIMPAT | critical | No validation with real data; title claims 'validation framework' | yes | state limitation | — | documented limitation | FINAL_EXPERIMENTS.md l.62-64 (cites G-01); no vehicle data used |
| G-02 | Hostile SIMPAT | critical | Baselines scored against HoloEnergy, results self-referential | yes | rewrite claim | — | claim to correct in paper | Same as F-01 |
| G-03 | Hostile SIMPAT | critical | Dominant energy term rests on contradicted drag; audit excludes it | partly | rewrite claim | — | claim to correct in paper | EXP10 part 1 (Gabl 0.11-0.22x, von Benzon 0.87-1.29x); audit scope unchanged |
| G-04 | Hostile SIMPAT | critical | Novelty integration-level; related work misstates DESERT energy tracking | yes | rewrite claim | — | claim to correct in paper | Related-work correction pending (HARDENING next step 5) |
| G-05 | Hostile SIMPAT | major | Grading scheme ad hoc, one-axis, untested | partly | none yet | — | open | No change found |
| G-06 | Hostile SIMPAT | major | Closed-loop coupling claimed but layout results are static allocation | partly | none yet | — | open | No change found |
| G-07 | Hostile SIMPAT | major | Weak/straw-man baselines | partly | none yet | — | open | See F-02 |
| G-08 | Hostile SIMPAT | major | Design cannot support general conclusions | partly | none yet | — | open | See F-04, F-05 |
| G-09 | Hostile SIMPAT | major | Uncertainty quantification nearly empty and mislabelled | partly | none yet | — | open | Interval bugs fixed under E-01..E-03; UQ scope unchanged |
| G-10 | Hostile SIMPAT | major | Battery model basic and unparameterised; battery results are artefacts | partly | none yet | — | open | See C-02, C-06 |
| G-11 | Hostile SIMPAT | major | Bollard T200 curves applied in inflow; grade B unjustified | partly | none yet | — | open | Grade B kept; see B-14 |
| G-12 | Hostile SIMPAT | major | Comm-energy contribution thin, one-way, duplicates DESERT | partly | none yet | — | open | See D-02, G-04 |
| G-13 | Hostile SIMPAT | major | Verification is self-consistency, not independent | partly | none yet | — | open | See D-19, F-16 |
| G-14 | Hostile SIMPAT | major | HoloOcean drag-defect claim unconfirmed upstream, version-specific | partly | none yet | — | open | HARDENING: still present in v2.4.0; upstream issue not filed (not authorised) |
| G-15 | Hostile SIMPAT | major | Generality claims unsupported | partly | none yet | — | open | No change found |
| G-16 | Hostile SIMPAT | major | Journal fit: reads as software release note | partly | none yet | — | open | Manuscript not yet drafted |
| G-17 | Hostile SIMPAT | major | Committed results do not match tagged code | yes | rerun from clean commit | 81b91ea, 65a06da | fixed (no test) | Final results match commit 81b91ea (after v0.2.0); a release tag for this state is not yet created |
| G-18 | Hostile SIMPAT | minor | Documents give inconsistent numbers | partly | none yet | — | open | No change found |
| G-19 | Hostile SIMPAT | minor | Misleading run status labels | partly | none yet | — | open | See B-13 |
| G-20 | Hostile SIMPAT | minor | Figure problems | partly | none yet | — | open | Figures not regenerated yet |
| G-21 | Hostile SIMPAT | minor | Unverified references | partly | none yet | — | open | No change found |
| G-22 | Hostile SIMPAT | minor | Uninformative cases and loose wording | partly | none yet | — | open | No change found |
| G-23 | Hostile SIMPAT | minor | No energy convergence (dt) study | partly | none yet | — | open | No change found |
| G-24 | Hostile SIMPAT | minor | Uncontrolled performance benchmark | partly | none yet | — | open | See F-20 |
| G-25 | Hostile SIMPAT | minor | Mixed-language documentation | partly | none yet | — | open | No change found |
| H-01 | Reproducibility | major | Committed results from pre-release dirty trees, holoenergy 0.1.0, old registry | yes | rerun from clean commit | 81b91ea, 65a06da | fixed (no test) | As D-11 |
| H-02 | Reproducibility | major | No environment spec/lock for native and DESERT interpreter | yes | none yet | — | open | No change found |
| H-03 | Reproducibility | major | Docs do not require clean v0.2.0 checkout; scripts accept dirty trees silently | yes | refuse dirty trees | 5713394, 81b91ea | fixed (no test) | Final, comm and cross-layer runners refuse dirty trees (--allow-dirty is labelled not for paper-critical runs); docs/native_runs.md still to state the clean-checkout requirement |
| H-04 | Reproducibility | minor | numpy 2.4.2 vs locked 2.5.4 (<=4.5e-16 relative) | yes | none yet | — | open | No change found |
| H-05 | Reproducibility | minor | matplotlib unpinned; figure manifest lacks versions | yes | none yet | — | open | No change found |
| H-06 | Reproducibility | minor | make_paper_figures --native-dir reads tables from <native-dir>/tables; F08 silently skipped | yes | none yet | — | open | No change found |
| H-07 | Reproducibility | minor | real_time_factor in result tables prevents byte reproduction | yes | none yet | — | open | No change found |
| H-08 | Reproducibility | minor | Summaries store gzip SHA256 only; CRLF vs LF; content_sha256 missing | yes | none yet | — | open | No change found |
| H-09 | Reproducibility | minor | CSV CRLF vs LF blobs; cmp fails off Windows | yes | none yet | — | open | No change found |
| H-10 | Reproducibility | minor | RQ6 1.13-1.21x not in any results file | yes | none yet | — | open | 73fe949 writes still-water drag ratio to E4; ID not cited |
| H-11 | Reproducibility | minor | RQ5 2.62-2.84 Wh mislabelled as hotel-load interval | yes | none yet | — | open | No change found (see F-14) |
| H-12 | Reproducibility | minor | Backend-check command in native_runs.md overwrites committed result | yes | none yet | — | open | No change found |
| H-13 | Reproducibility | minor | Docs disagree on interpreter paths and dependency lists | yes | none yet | — | open | No change found |
| H-14 | Reproducibility | minor | Wheel SHA256 not reproducible (zip timestamps); uv build only in CI | yes | none yet | — | open | No change found |
| H-15 | Reproducibility | minor | DESERT image digest truncated; holo_desert commit not given | partly | none yet | — | open | Docker not run by reviewer |

## 2. Counts

### By severity

| Reviewer | critical | major | minor | total |
|---|---|---|---|---|
| A Literature | 0 | 5 | 20 | 25 |
| B Physics | 1 | 10 | 7 | 18 |
| C Battery | 0 | 6 | 10 | 16 |
| D Component | 0 | 11 | 11 | 22 |
| E Numerical | 0 | 8 | 17 | 25 |
| F Exp. design | 1 | 8 | 12 | 21 |
| G Hostile SIMPAT | 4 | 13 | 8 | 25 |
| H Reproducibility | 0 | 3 | 12 | 15 |
| Total | 6 | 64 | 97 | 167 |

### By resolution

| Reviewer | fixed + regression test | fixed (no test) | design change | documented limitation | claim to correct | open | total |
|---|---|---|---|---|---|---|---|
| A Literature | 1 | 2 | 0 | 1 | 1 | 20 | 25 |
| B Physics | 0 | 2 | 2 | 2 | 3 | 9 | 18 |
| C Battery | 3 | 0 | 0 | 0 | 0 | 13 | 16 |
| D Component | 2 | 2 | 1 | 1 | 1 | 15 | 22 |
| E Numerical | 8 | 3 | 0 | 0 | 0 | 14 | 25 |
| F Exp. design | 0 | 0 | 2 | 2 | 1 | 16 | 21 |
| G Hostile SIMPAT | 0 | 0 | 0 | 1 | 3 | 21 | 25 |
| H Reproducibility | 0 | 0 | 0 | 0 | 0 | 15 | 15 |
| Total | 14 | 9 | 5 | 7 | 9 | 123 | 167 |

Confirmed? yes: 116; partly: 51; not reproduced: 0.

'yes' = the reviewer gave a reproduction, recomputation or direct source reading and nothing found in the repo contradicts it. 'partly' = evidence is reviewer judgement, an agent page extraction or a code reading only.

## 3. Open findings

### 3a. Block paper claims

| ID | Sev. | Affects |
|---|---|---|
| A-02 | major | 'no published data' wording |
| B-09 | major | station-keeping numbers |
| B-10 | major | layout/baseline percentages |
| B-11 | major | proxy-profile claims |
| B-12 | minor | VEC30 results |
| B-13 | minor | validity labels |
| C-02 | major | L1 energy overstated above 12 V |
| C-05 | major | battery-fidelity claim |
| C-06 | major | thermal results |
| D-02 | major | RQ4 strategy effect |
| D-04 | major | payload-suite results |
| D-09 | major | S5 sonar on 4S bus |
| D-12 | minor | RX energy claims |
| D-19 | minor | independence claim |
| F-05 | major | single-run conclusions |
| F-07 | major | ablation claim |
| F-08 | major | layout ranking |
| F-10 | minor | validity labels |
| G-05 | major | grading validity |
| G-06 | major | closed-loop claim |
| G-07 | major | baseline claims |
| G-08 | major | generality |
| G-09 | major | UQ claim |
| G-10 | major | battery results |
| G-11 | major | propulsion grade B |
| G-12 | major | comm contribution |
| G-13 | major | verification claim |
| G-14 | major | related-work claim on drag defect |
| G-15 | major | generality |
| G-16 | major | journal fit |
| H-02 | major | reproducibility claim |

### 3b. Do not block a paper claim (mostly minor or advisory)

A-07, A-08, A-09, A-10, A-11, A-12, A-13, A-14, A-15, A-16, A-17, A-18, A-19, A-20, A-21, A-22, A-23, A-24, A-25, B-14, B-15, B-16, B-17, C-07, C-08, C-09, C-10, C-11, C-12, C-13, C-14, C-15, C-16, D-13, D-14, D-15, D-16, D-17, D-18, D-20, D-21, D-22, E-11, E-12, E-13, E-14, E-15, E-16, E-17, E-18, E-19, E-20, E-21, E-22, E-23, E-24, F-11, F-12, F-13, F-14, F-15, F-16, F-17, F-18, F-19, F-20, F-21, G-18, G-19, G-20, G-21, G-22, G-23, G-24, G-25, H-04, H-05, H-06, H-07, H-08, H-09, H-10, H-11, H-12, H-13, H-14, H-15

Open total: 123 (blocking 36, non-blocking 87). The split is the drafter's judgement from the finding text.
