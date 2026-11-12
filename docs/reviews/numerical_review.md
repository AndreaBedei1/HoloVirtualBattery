# Numerical methods and software verification review (Reviewer E)

Target: HoloEnergy tag `v0.2.0` (commit `bd11c98`), branch `feature/provenance-aware-energy-framework`.
Line numbers refer to `v0.2.0` unless marked "HEAD".

During the review the branch advanced to `69bd3d7`. The changes that fall within this review's scope are:
- `rate` unit kind in `units.py` (`14afa42` series);
- new `experiments/verify_final_energy.py`;
- commit `69bd3d7`: voltage-cutoff latch change in `battery.py`, stale-link and voltage-dependence additions in `evidence/runtime.py`.

Every finding was re-checked at HEAD `69bd3d7` with the same probe; findings that HEAD changes say so. `uv run --no-sync pytest -q` at HEAD: 321 passed.

## Scope and method

Modules reviewed: `units.py`, `_validation.py` (`curve`, `interpolate`, `timestep`), `models/propulsion.py`, `models/actuator.py`, `models/battery.py`, `models/thermal.py`, `models/power_manager.py`, `models/converters.py`, `models/payload.py` (state timing only), `allocation.py`, `actuation.py`, `accounting.py`, `env_wrapper.py` (`_one_tick`, `_aggregate`, `step`), `uncertainty.py`, `evidence/runtime.py` (`summarize`, `_check_links`), `report.py`, `experiments/run_native_campaign.py` (`close_chain`, `metrics`, `downsample`), `experiments/analyze_native_campaign.py`, `experiments/verify_final_energy.py` (HEAD) and `tools/verify_energy_chain.py` (`T200Tables`).

Method:
- Read every formula and checked its dimensions.
- Recomputed energies independently from all 42 full per-tick native traces (`logs/native_campaign/*.trace.jsonl.gz`).
- Cross-checked the arithmetic of every `experiments/results/native/N*/*.summary.json`.
- Wrote small probes for edge cases, using the test-suite `FakeEnv` (no HoloOcean, no Docker).
- `uv run --no-sync pytest -q`: 319 passed at v0.2.0, 321 at HEAD.

The probe scripts are in `C:\Users\ANDREA~2.BED\AppData\Local\Temp\claude\945244cbcba3dc8b\50891df7-d4df-47f1-ad45-e3fefca5e7b6\scratchpad\reviews\E\`: `recompute.py`, `check_summaries.py`, `probe_units_interp.py`, `probe_env.py`, `probe_pm.py`, `probe_uncertainty.py`, `probe_aggregate.py`, `probe_state_attr.py`, `probe_alloc_links.py`, `probe_analyzer.py`, `probe_thermal.py`, `probe_latch.py`, `probe_stale.py`, `probe_domain.py` and `probe_verify_final.py`.

**Result: 0 critical, 8 major and 17 minor findings.**
- At HEAD, 1 major (E-04) is fixed.
- E-05 is claimed fixed by `69bd3d7`, but it still reproduces through `EnergyAwareEnv`.
- E-24 and E-25 are new HEAD code.

The core energy integration is exact with respect to the model. Recomputing Σ P·dt from the traces reproduces every summary to within 4·10⁻¹⁴ relative. The defects are in four places:
- the uncertainty intervals;
- the coupling between the power limit, the voltage cutoff and the actuator domain;
- the wrench-equivalent mapping when the native clamp saturates;
- multi-tick aggregation and the analysis scripts.

## Findings

| ID | Sev. | Location (v0.2.0) | Defect | Minimal reproduction: observed vs expected | Suggested fix / regression test |
|---|---|---|---|---|---|
| E-01 | major | `holoenergy/uncertainty.py:75-83` | Interval deltas are added at load-side energy, `wh*(ratio-1)`. They ignore the rail converter efficiency, although the nominal terminal energy includes converter losses. The terminal-energy interval therefore understates the true change by a factor η. | `probe_uncertainty.py`: one `navigator` component (record `bluerobotics_navigator.power_typical`, 0.75 W, `value_max` 0.8025 W), `payload_efficiency: 0.8`, 1000 ticks at 0.01 s. Interval high is 0.002750000 Wh. Re-simulating at 0.8025 W gives a terminal energy of 0.002786458 Wh, so the delta is understated by 20.0 % (= 1−η). With η = 1 the two agree exactly. | Scale each contribution by 1/η of its rail. Store terminal-side state energy, or pass the rail efficiency. **Test:** the interval high must equal a brute-force re-run at `value_max` with η < 1. |
| E-02 | major | `holoenergy/uncertainty.py:56-60`; caller `report.py:59` | The default "used value" is `record.value` whatever the component's `use:` is. A component configured with `use: value_max` or `use: value_min` is scaled relative to the wrong value. `EnergyReport` never passes `used_values`. | Same probe with `states: {ACTIVE: {evidence: bluerobotics_navigator.power_typical, use: value_max}}`. The nominal is already at 0.8025 W, yet the reported high is +7.00 % above it (ratio `(None, 1.07)`). Expected: high = nominal, low from `value_min` (open here). This is latent in the shipped profiles: all six `use: value_max` records have `value: null`, so the fallback to `value_max` happens to be correct. | Have `ElectricalComponent` record the used SI value per state. `EvidenceMap` should expose it and `report.py` should pass it as `used_values`. **Test:** `use: value_max` gives `high == nominal`. |
| E-03 | major | `holoenergy/uncertainty.py:84-94` (and `_ratio_interval` 18-30) | The battery-loss interval reports a finite upper value together with `open_upper: true`. The record has `bound: lower_bound`, but `value_max` (the cell tolerance) closes the upper side. Component records with `bound: lower_bound` plus `value_max` are closed in the same way, but without any flag. | Found in 41 of 42 native summaries. Example: N5-S5 has `interval_Wh: [0.028206, 0.034503]` and `open_upper: true`. Record `bluerobotics_4s_18ah.dc_resistance_cell_derived`: 13.29 mΩ, `lower_bound`, 11.96–14.63 mΩ, and it excludes interconnects. A consumer reading `interval_Wh[1]` would treat 0.0345 Wh as an upper bound. | Use one rule in both paths. For `lower_bound`, set `hi = None` (open), or document `value_max` as a cell tolerance and drop the open flag. **Test:** `open_upper` ⇒ `interval_Wh[1] is None`. |
| E-04 | major | `holoenergy/evidence/runtime.py:13-14, 136-140` | A stale battery-loss link is not detected when resistance comes from `resistance_soc_temperature_curves`. In that case `internal_resistance_ohm` is null and `_matches(record, None)` returns True. Grade C and the record's interval are then credited to a resistance the model does not use. | `probe_stale.py` at v0.2.0: Heavy profile with a 0.05 Ω SOC table. The model uses 0.05 Ω, 3.76 × the record. The link is kept, graded C, with `stale_links == []`. **Status at HEAD:** fixed by `69bd3d7` (`runtime.py:154`). The same probe now reports a stale link graded D, and `tests/test_evidence_links.py:71` was added. | Done. Add the SOC-map case as an explicit test too; the HEAD test covers the temperature-factor case. |
| E-05 | major | `holoenergy/models/battery.py:233` with `:274-275`, and `env_wrapper.py:502-507` | The voltage limiter and the voltage cutoff latch use the same threshold. `current_limit` caps I at (U−V_cut)/R, so a limited tick ends exactly at V_cut. The end-of-tick test `U−IR ≤ V_cut+1e-10` then latches a permanent CUTOFF in that same tick. A voltage-limited (POWER_LIMITED) state can therefore never last beyond one tick. | N6-L8-HV-lowsoc-c0.5 trace: exactly one tick has 0 < factor < 1 (tick 917: factor 0.99942, V = 12.000000000008837 V, SOC 2.789 %, OCV ≈ 12.45 V). It is latched CUTOFF in the same tick, followed by 2082 ticks at zero power. `probe_latch.py` (Heavy, SOC 0.03, 4 × −25 N) latches CUTOFF at tick 0 with factor 0.764. **Status at HEAD:** NOT fixed. Commit `69bd3d7` ("C-01") changed only `RintBattery.step` (HEAD `battery.py:278` now latches on OCV). The duplicate loaded-voltage latch at `env_wrapper.py:502-507` is unchanged. `probe_latch.py` at HEAD still gives 3000/3000 CUTOFF from tick 0. The new test `test_voltage_limited_operation_does_not_latch_while_ocv_remains_above_limit` calls `RintBattery` directly and never goes through `EnergyAwareEnv`, so it passes anyway. | Remove the loaded-voltage latch in `env_wrapper.py:502-507`, or apply the same OCV-only rule there. **Test:** through `EnergyAwareEnv`, low-SOC station keeping stays POWER_LIMITED for more than 1 tick until OCV reaches V_cut. Then re-run N6-lowsoc. |
| E-06 | major | `holoenergy/actuation.py:116-118`; `env_wrapper.py:423-426` | In `wrench_equivalent` mapping, the virtual allocation uses T200 bounds without the native clamp. Propulsion energy is then charged for virtual forces that the native body cannot produce, because the native re-allocation saturates at 28.75 N. | Identical geometry, c = 0.8 m/s: N1-L8-HV-we vs N1-L8-HV-direct. The dynamics are identical (mean tail tracking error 4.224108981609344 m in both), but propulsion is 6.828 vs 6.281 Wh (+8.71 %). 2342 of 3000 ticks have a virtual \|f\| > 28.75 N, and those ticks hold 6.174 Wh. L4-H45, L6-STD and L8-VEC30 at c = 0.8 show the same pattern. The runs are flagged `PASS_WITH_INCONSISTENT_TICKS`, but their energies are still tabulated. | Make the virtual wrench achievable on the native layout before allocating it (scale by `native.max_wrench_along`, or iterate). Otherwise report energy only for consistent ticks. **Test:** L8-HV `we` and `direct` give equal energy when the clamp saturates. |
| E-07 | major | `holoenergy/models/power_manager.py:113-116`; `models/propulsion.py:112-115, 207-231` | The actuator-domain factor is computed at the worst-case voltage over [V_min(I_max), U]. Combined with the min-of-bracket max force, this derates thrust that is feasible at the solved operating point, and the thrust cap jumps at every table voltage. Because `apply_derating_to_actions: true`, both energy and applied thrust are affected. | `probe_pm.py`: Heavy, SOC 0.95 (OCV 16.5 V), H1 = 45 N alone. The plan factor is 0.98652, so 44.393 N is applied. The solved point is 16.256 V and 18.33 A, where max force is 51.44 N and P(45 N) = 302.99 W is defined. Max forward force is 44.39 N at 15.999999 V and 51.44 N at 16.0 V, a −13.7 % step. The impact on the campaign was not isolated. | Solve the operating point first and check the domain at the solved voltage, iterating if needed. Interpolate the max force between tables, for example on normalized force, instead of taking the min. **Test:** the example above gives factor = 1. |
| E-08 | major | `holoenergy/env_wrapper.py:729-738`, `781` | In `_aggregate`, a device that first appears after the first tick of a multi-tick step raises `KeyError`. This happens outside the `try`, after the backend has already advanced and energy has been recorded, so no row is logged and the env is not marked faulted. A device that is absent in the last tick is silently dropped from `component_power_W`. | `probe_aggregate.py`, load source returning `{}` and then `{"modem": {"TX": 1 J}}`, `ticks=2`: raises `KeyError 'modem'` after 2 backend steps and 1 J recorded. The reverse order gives `power_communications_W = 50 W` with `modem2` missing from `component_power_W`. The shipped communications adapter can add ledgers after `attach()` (`env_wrapper.py:308`). | Take the union of names across rows, defaulting missing values to 0, and aggregate inside the guarded block. **Test:** an intermittent device with `ticks > 1`. |
| E-09 | minor | `env_wrapper.py:425`; `allocation.py:188-190` | `allocation.method: power_irls` is accepted by the config, but every wrench step raises, because no power functions are passed. | `probe_env.py`: `power_irls` → `ConfigurationError: power_irls requires one power function per actuator` at step 1. | Pass `lambda f: thruster.power(...)` per actuator, or reject the method at construction. **Test:** a wrench step with `power_irls`. |
| E-10 | minor | `allocation.py:195-205` | IRLS weights use `p(abs(x))`, so direction is lost, yet T200 reverse power is 39–45 % higher than forward. On convergence, `weights` keeps the previous iterate's values, which are then used for redistribution. | T200 at 16 V: 10 N gives 27.67 W forward vs 38.37 W reverse; 30 N gives 160.90 vs 233.48 W. | Pass the signed force to `p`, and set `weights = new` before `break`. **Test:** a reverse-dominated wrench lowers the reported power. |
| E-11 | minor | `run_native_campaign.py:543-544`; `analyze_native_campaign.py:125-135` | `downsample` keeps the last row in addition to every 10th row, and `baseline_energy` integrates `len(rows) × 0.1 s`. This gives 30.1 s for a 30.0 s run (301 rows) and 67.1 s for 67.0 s, i.e. one extra sample. | `probe_analyzer.py`: `trace_vs_summary_relative` is +0.042 % to +0.209 %. Without the extra row it is −0.04 % to −0.17 %. Baseline errors shift by 0.3–0.4 points: for example, N2-L8-HV-sway `speed_cubic_water` is −1.37 % from the 0.1 s trace vs −1.70 % from the full trace, and N1-c0.2 `constant` is +47.15 % vs +46.87 %. | Weight samples by their real interval, or drop the appended row, or use the full trace. **Test:** a constant-power trace integrates to P·T. |
| E-12 | minor | `run_native_campaign.py:434-436` | `initial_soc = ticks[0]["soc"]` is the SOC after the first tick, so `soc_loss` misses one tick. | N5-S5: metric 0.9999993489 vs report `soc_initial` 1.0. N6-lowsoc: 0.0299999289 vs 0.03. | Use `env.battery.initial_soc` or capture the SOC before the first step. **Test:** `metrics.initial_soc == config.initial_soc`. |
| E-13 | minor | `run_native_campaign.py:440` | `derated_tick_fraction` counts CUTOFF ticks (factor 0) as derated. | N6-lowsoc: 0.6943 (2083/3000), of which 2082 are cutoff ticks and only 1 is a power-limited tick. | Report the limited fraction (0 < f < 1) and the cutoff fraction separately. |
| E-14 | minor | `allocation.py:239`; `actuation.py:32`; `run_native_campaign.py:369-373`; `analyze_native_campaign.py:98` | Residual norms are ‖[F; M]‖, mixing N and N·m, so the thresholds (1e-6, 1e-3) depend on the unit of length. | `probe_alloc_links.py`: the same physical residual (5 N, 1 N·m) is 5.099 with lengths in m and 100.12 with lengths in cm. | Report force and moment residuals separately, or normalize by a characteristic length. |
| E-15 | minor | `power_manager.py:110, 170`; `evidence/__init__.py:421` | Converter loss is computed by cancellation, P_in − ΣP_out. With η = 1 this yields rounding noise of either sign: negative `converters` energy and negative grade shares. `coverage()` raises below −1e-12 Wh. | 14 of 42 summaries have negative `converters` energy, the lowest −2.5e-18 Wh. N5-S5 evidence D = −1.1e-18 Wh (−3.9e-17 %). With constant loads (250.7 W + 1000.1 W) the bias is systematic, about −1.1e-13 W per tick, and reaches the −1e-12 Wh guard after about 8.8 h at 100 Hz, but only if that grade bucket holds nothing else. | Compute the loss per rail as P·(1/η − 1), which is exactly 0 for η = 1 and never negative. |
| E-16 | minor | `env_wrapper.py:498-499, 606-609` | State energy is labelled with the state *after* `commit_service`. A tick in which STARTING or PINGING ends is booked entirely to the next state. With dt = 0.1 the result is correct only because ten additions of 0.1 sum to 0.999…9 < 1. | `probe_state_attr.py`, startup 20 W × 1 s then 5 W, dt = 0.25: STARTING 15 J and ACTIVE 7.5 J, expected 20 J and 2.5 J (the totals are correct). The row label also shows ACTIVE for a full STARTING tick. | Have `preview` return the energy split by state, and attribute each part. **Test:** binary-exact dt with a transition on a tick boundary. |
| E-17 | minor | `battery.py:118-134, 278-286` | The default identity curves `[[25, 1]]` mark every temperature other than 25 °C as `temperature_outside_calibration`. | `RintBattery.temperature_outside_calibration(20.0)` is True (and True at 15 °C), so every native tick (19.96–20 °C) is flagged. | Treat the single-point defaults as "no dependence" (do not flag), or flag explicitly as "uncharacterized". |
| E-18 | minor | `env_wrapper.py:76-79`; `power_manager.py:47-51` | Construction checks only the *nominal* voltage against the actuator domain. A pack whose OCV range leaves the domain fails at runtime. | `probe_domain.py`: OCV 15–21 V (nominal 18.5 V) with T200 at 10–20 V constructs, then the first nonzero thrust raises `ValueError: Battery OCV exceeds the thruster profile voltage range`. | Check [OCV(0), OCV(1)], or at least OCV(initial_soc), at construction. |
| E-19 | minor | `units.py:131-141, 149-152, 104-105` (HEAD: +3 lines) | `dbm_to_watt` and `watt_to_dbm` accept NaN and inf, and `dbm_to_watt(1e6)` raises `OverflowError`. `Quantity` and `Quantity.parse` accept NaN. Temperatures below absolute zero are accepted. | `dbm_to_watt(nan)` → nan; `Quantity.parse("nan W")` succeeds; `to_si(-300, "degC")` → −26.85 K. | Add finiteness and range checks (T ≥ 0 K) that raise `ConfigurationError`. |
| E-20 | minor | `_validation.py:54-63`; `propulsion.py:96-110` | `interpolate(points, nan)` raises `IndexError` instead of a validation error. `ThrusterModel.power(nan, V)` behaves the same way. The env path is protected by `validate_action`. | `interpolate(((0,0),(1,10),(2,30)), nan)` → `IndexError: tuple index out of range`. | Reject non-finite x in `interpolate`. |
| E-21 | minor | `analyze_native_campaign.py:173-177` | When the reference energy is 0, `relative_difference` falls back to an absolute Wh value, mixing units in one column. | Currently harmless (both values are 0 at c = 0). | Return `None` (or NaN) instead. |
| E-22 | minor | `env_wrapper.py:508`; `accounting.py:83, 86` | Time and durations are accumulated by repeated addition. | Phase durations come out as 2.99999999999998 s; the total drifts by 1.9e-12 s over 6700 ticks, and the drift grows with mission length (it moves the window edges in `endurance()` and the trace-spacing checks). | Use `time = step_index × dt` (or `math.fsum`). |
| E-23 | minor | `uncertainty.py:96-103` | `terminal_energy_Wh.low` is reported as a number even when `open_low` is non-empty. Open-low devices are treated as exact on the low side, so `low` is not a bound, although P ≥ 0 gives a defensible one. | N5-S5: low = 2.6245 Wh with 6 open-low devices worth 0.8124 Wh. A lower bound valid under P ≥ 0 is 1.8121 Wh. | Also report `low_bound_nonnegative` (open sides at 0 W), or set `low = None` when `open_low` is non-empty. |
| E-24 | minor | HEAD `experiments/verify_final_energy.py:89-94, 36-39, 42` | The new "independent" check computes battery losses as Σ I²·R_ref·dt. This ignores `resistance_temperature_curve` and SOC/temperature maps, so a correct run is reported as FAIL. `rel()` switches to an absolute difference when \|b\| < 1e-15 Wh, yet the same `TOL` is applied. The script re-integrates the logged row powers, so it verifies bookkeeping only; it never re-evaluates P(F, V), and it does not detect negative category energies (E-15). | `probe_verify_final.py` (synthetic `FakeEnv` run, since `logs/final` does not exist yet): the baseline gives PASS (worst 1.2e-14). With `resistance_temperature_curve [[0,1.5],[40,1.0]]` the result is FAIL, with an I²R relative error of 0.200 although the accounting is exact. | Log R per tick (or ΣI²R from the model) and compare with that. Add an independent P(F, V) check like `close_chain`. **Test:** a non-identity R(T) case must PASS. |
| E-25 | minor | HEAD `evidence/runtime.py:246-272` | `voltage_dependence` reports `voltage_dependent_energy_Wh: 0.0` for L0. Yet L0 propulsion is still evaluated from voltage-dependent T200 tables at the nominal voltage, so it does depend on the bus-voltage assumption. | Heavy profile, 200 ticks of 4 × 20 N: L0 reports 0.0 Wh against 0.187 Wh of propulsion. L1 reports 0.19959 Wh = propulsion + losses (correct). | For L0, report propulsion energy as dependent on the nominal-voltage record and its grade. |

## Independent recomputation (full per-tick traces, dt = 0.01 s, rectangle rule)

The integrand is piecewise constant by construction: action, OCV, R and the battery solution are held over each tick. The rectangle rule Σ P_k·dt is therefore the exact integral of the model. A trapezoid would mix adjacent ticks and differ by about P_end·dt/2.

Recomputation uses `math.fsum`. Summary values are taken from `metrics` (`propulsion_Wh`, `terminal_Wh`, `battery_losses_Wh`) and from `energy_report.device_energy_Wh`. Battery losses are recomputed as Σ I²R·dt with R = 13.29 mΩ (identity temperature curve).

| Run | Quantity | Trace Σ P·dt (Wh) | Summary (Wh) | Rel. diff. |
|---|---|---|---|---|
| N5-S5-inspection-transit-c0.2 | thruster H1 | 0.377417578208 | 0.377417578208 | ≤ 3.6e-15 |
| | total propulsion | 1.514364166885 | 1.514364166885 | +1.2e-15 |
| | terminal | 2.829239166885 | 2.829239166885 | +3.4e-14 |
| | battery losses (Σ I²R dt) | 0.031342713117 | 0.031342713117 | −1.1e-15 |
| N4-L8-HV-transit-c0.2 | H1 / propulsion / terminal | 0.378655937340 / 1.519338661269 / 1.626352550158 | same | ≤ 5.1e-15 / −1.0e-15 / −3.6e-15 |
| N1-L8-HV-direct-c0.8 | H1 / propulsion / terminal / losses | 1.570320032917 / 6.281280131668 / 6.329196798335 / 0.274043646392 | same | ≤ 1.3e-15 |
| N1-L8-HV-we-c0.8 | propulsion / terminal | 6.828150573868 / 6.876067240535 | same | −1.3e-15 / −1.6e-15 |
| N6-L8-HV-L0-transit-c0.2 | H1 / propulsion / terminal | 0.363362062183 / 1.457917289095 / 1.564931177983 | same | ≤ 2.3e-15 |
| N6-L8-HV-lowsoc-c0.5 | H1 / propulsion / terminal / losses | 0.112110976211 / 0.448443904844 / 0.463106404844 / 0.010912720424 | same | ≤ 5.0e-16 |
| **All 42 runs (max \|rel\|)** | per thruster / propulsion / terminal | — | — | 5.4e-15 / 4.0e-15 / 3.9e-14 |
| All 41 L1 runs (max \|rel\|) | battery losses; \|final SOC diff\| | — | — | 3.4e-15; 1.1e-14 (absolute) |
| All 42 runs (max per tick) | \|ΔSOC − IΔt/(3600·18 Ah)\|; \|V·I − P\|/P; \|Δt − 0.01 s\| | — | — | 5.6e-17; 4.3e-16; 5.1e-15 s |

The committed 0.1 s traces (`*.trace10.jsonl.gz`) are not equivalent to the full traces: the propulsion energy they yield is +0.04 % to +0.21 % too high (E-11).

## Verified correct

- **Units.** The factors are correct: Wh = 3600 J, mWh = 3.6 J, mAh = 3.6 A·s, kn = 1852/3600 m/s, lbf, kgf and rpm. The HEAD `rate` kind (`1/s`) is separate from `frequency`, so `convert(1, "Hz", "1/s")` is refused. °C↔K offsets are correct. `to_si` and `convert` refuse `dB`, `dBm` and `dB re 1 µPa (@ 1 m)` as electrical power. `C` is rejected as ambiguous. Booleans and non-finite values are rejected by `to_si`.
- **Interpolation.** `interpolate` is piecewise linear, clamps at the end points, is exact at knots and handles single-point curves. `curve` requires strictly increasing, finite x. `timestep` rejects 0, negative and NaN dt.
- **T200 lookups.**
  - The force→power inverse takes the maximum power per force, so power is nondecreasing in force.
  - At fixed force, power is continuous across table voltages: at 30 N it is 160.862 / 160.902 / 161.003 W at 15.99 / 16.0 / 16.01 V.
  - The domain tolerances are ±1e-9 V and +1e-8 N. Out-of-range voltage or force raises an error rather than extrapolating.
  - `force()` over all tables is equivalent to the bracketed interpolation.
- **Rint battery.**
  - `current_for_power` uses the stable root, and P = I(U−IR) holds to 4e-16.
  - Chemical power U·I equals P + I²R.
  - The current limit is restricted to the high-voltage branch (≤ U/2R), so the current bisection in `plan` cannot land on the low-voltage root.
  - The terms `charge·3600/dt` (A) and `Ah·V` (Wh) are dimensionally correct.
  - `remaining_energy_Wh` (trapezoid on the union of knots) matches a 2·10⁵-point midpoint integral to −1.3e-12.
- **Thermal model.**
  - The exact exponential step matches explicit Euler at 1e-5 s to 2e-8 °C.
  - The `cooling = 0` branch gives Q·dt/C (J ÷ J/°C = °C).
  - `current_limit` makes T_end equal the cutoff to 1e-12 °C for an entropy coefficient of 0 and ±3e-4 V/K; both root forms are algebraically equivalent.
  - The heat term I²R − I·T_K·dU/dT is the Bernardi form.
- **Power manager.**
  - The factor bisection (36 iterations, 1.5e-11) and the current bisection (40 iterations) converge.
  - In the main branch, P_in = ΣP_prop/η_p + P_pay/η_pay + P_hotel/η_h. In the shedding branch the sum is `available`.
  - Category sums equal the battery terminal power in every native run (4e-14).
- **Accounting.** All arithmetic agrees across the summaries:
  - terminal = Σ categories (2e-16);
  - total OCV work = terminal + losses;
  - Σ phases = terminal (3e-14);
  - Σ actuator devices = propulsion;
  - Σ component devices = sensors + compute + auxiliaries + communications (9e-15);
  - evidence `total_Wh` = total OCV work (1e-14);
  - grade shares sum to 100 % (3e-14);
  - the upper-bound share is consistent;
  - interval low and high are reproduced exactly from `contributions`.
- **HEAD additions.**
  - `voltage_dependence` (L1) equals propulsion + battery losses exactly.
  - The OCV grade is D for the BlueROV2 pack (`bluerobotics_4s_18ah.ocv_curve` has no value).
  - The new stale-link rules flag both resistance maps and non-identity R(T) factors.
  - `verify_final_energy.verify_run` reproduces 22 bookkeeping checks to 1.2e-14 on a synthetic run.
- **Multi-tick stepping.** 10 single-tick steps and one 10-tick step give bit-identical terminal energy. The mean power of the aggregated row times Σdt equals the energy.
- **Determinism.** No RNG is used. Separate HoloOcean processes produced bit-identical traces for N1-L8-HV-direct-c0.5 and N1-L8-HV-we-c0.5 (positions, velocities, power, SOC). Traces are written as deterministic gzip with mtime 0.
- **`close_chain`.** The power check uses an independent table implementation (`T200Tables`) at the logged terminal voltage; worst residual 4e-12 W. The force residual is at most 3.4e-5 N. Its scope is limited to 3 translational DOF; moments are not closed.

## Observation (not a numerical defect)

For surge current at c ≤ 0.5 m/s, L4-H45, L6-STD and L8-HV produce bit-identical horizontal thruster energies (for example, H1 = 0.795327045 Wh at 0.5 m/s). The horizontal allocation decouples from the vertical thrusters, so these N1 "layout comparisons" do not discriminate between the layouts.
