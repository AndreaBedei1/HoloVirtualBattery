# Reviewer C: electrical systems and batteries

Independent review of HoloEnergy v0.2.0 (`feature/provenance-aware-energy-framework`, commit
`bd11c98`), prepared for submission to Simulation Modelling Practice and Theory. Nothing in the
repository was modified apart from this file. HoloOcean and Docker were not run. Every number below
comes from the package itself (`uv run --no-sync python`), from the archived campaign outputs in
`experiments/results/native/`, or from manufacturer documents that were read directly. Where a
number is the reviewer's own estimate, the text says so.

## Scope

- `holoenergy/models/battery.py`: L0 `EnergyBucketBattery` and L1 `RintBattery`.
- `holoenergy/models/thermal.py`, `power_manager.py`, `converters.py`, `hotel_load.py`.
- `holoenergy/accounting.py`.
- Bus coupling, limits and cutoff handling in `holoenergy/env_wrapper.py`.
- `with_fidelity` and `model_warnings` in `config.py`.
- Battery and thermal evidence links in `evidence/runtime.py` and `uncertainty.py`.
- Profiles: `profiles/batteries/*.yaml`, and the battery, thermal, converter and hotel sections of
  `bluerov2_heavy_holoocean.yaml`, `bluerov2_standard_6t.yaml` and `bluerov2_heavy.yaml` (v0.1).
- Records: `evidence/data/parameters/batteries.yaml`, plus the battery entries of
  `proxy_vehicles.yaml` and `vehicle_electronics.yaml`.
- Docs: `docs/scientific_sources.md`, and the battery statements in `docs/paper_outline_smpat.md`
  and `docs/RESEARCH_STATUS.md`.
- Campaign evidence: the `N6_battery` and `N4_mission` tables and the N6 traces.

### External documents read

- **Samsung SDI, *Introduction of INR18650-30Q* (Aug. 2014)**, the copy hosted by Blue Robotics
  (S5). Pages read:
  - p. 3: 45.6 g typical (48.0 g max); DC IR (10 A to 1 A) 19.94 ± 2 mΩ typical, specification
    ≤ 30 mΩ; rated 3.0 Ah at 0.2C; discharge end voltage 2.5 V.
  - p. 4: at 0.2C, 3.040 Ah, 11.0 Wh, 3.61 V average; at 10 A, 2.983 Ah, 10.1 Wh.
  - p. 6: discharge curves and end-of-discharge cell temperatures; at 10 A, 60.9 °C after
    17.7 min from 23 °C.
  - p. 7: energy and average voltage at 1C/5/10/15/20 A, all to 2.5 V. At 1C, 10.44 Wh and
    3.53 V; at 10 A, 9.98 Wh and 3.39 V.
  - p. 8: 73.8 % capacity after 300 cycles at 15 A.
- **Blue Robotics 18 Ah 4S product page (D003/S5).**
  - Confirms: 18.0 Ah / 266.4 Wh, 14.8 V, 4S6P, 60 A continuous (3.3C), 132 A for 10 s,
    "Minimum Safe Voltage" 12 V (3.0 V/cell), and 1152 g.
  - States no cell model, no internal resistance and no BMS.
  - The only temperature statement besides the thermistor range is the safety sentence "Do not
    expose batteries to temperatures above 50 °C".

### Numerical check scripts

The scripts are kept outside the repository, in
`C:\Users\ANDREA~2.BED\AppData\Local\Temp\claude\945244cbcba3dc8b\50891df7-d4df-47f1-ad45-e3fefca5e7b6\scratchpad\reviews\C\`:

- `t1_battery.py`: Rint algebra, the latch, and constant-power discharge for L0 and both L1 packs.
- `t2_env.py`: the wrapper with a fake backend. It checks accounting closure, low-SOC behaviour,
  auxiliary shortage, provenance links and the proxy L0 power limit.
- `t3_thermal.py`: exact versus Euler integration, steady state, threshold `k`, and monotonicity.
- `t4_pm.py`: derating as a function of SOC and temperature, and L0 versus L1 propulsion power.

Short inline snippets also checked the T200 power-versus-voltage dependence, delivered energy at
constant current, and the timing of the voltage-domain check.

## Parameter classification (BlueROV2 profiles)

Profile v0.2 is `bluerov2-heavy` / `bluerov2_heavy_holoocean.yaml`; `bluerov2-standard` inherits
its battery, thermal and converter sections. Profile v0.1 is `bluerov2-heavy-v0.1` /
`bluerov2_heavy.yaml`.

Classes used in the table:
- **measured**: experimental data for the configured hardware.
- **manufacturer**: pack-level manufacturer rating.
- **cell proxy**: derived from data for one cell.
- **pack proxy**: derived from data for a different pack.
- **placeholder**: a declared illustrative value.
- **unknown**: omitted, defaulted or null.
- **user**: a scenario input or policy.

| Parameter | v0.2 value | v0.1 value | Class | Where it acts / leak risk |
| --- | --- | --- | --- | --- |
| `model` | rint (L1); with_fidelity gives energy_bucket (L0) | rint | modelling choice | — |
| `capacity_Ah` | 18.0 | 18.0 | manufacturer (nominal; rate and cutoff not stated on the pack page, cell basis is 0.2C to 2.5 V) | SOC denominator, L0 266.4 Wh. Combined with OCV(0)=12 V it over-states energy above 12 V (C-02) |
| `nominal_voltage_V` | 14.8 | 14.8 | manufacturer | L0 bus voltage feeding the T200 tables, L0 current, init domain check |
| `cells` | 4S6P, 30Q "implied" | — | manufacturer (4S6P); the cell model is an inference (cell proxy) | metadata only; no code scales by it |
| `initial_soc` | 1.0 (N6: 0.03) | 1.0 | user | sets the bus voltage through the OCV curve (C-05) |
| `cutoff_voltage_V` | 12.0 | 12.0 | manufacturer ("minimum safe voltage") applied as an instantaneous loaded-voltage latch, which is a policy | end of the L1 mission (C-01) |
| `max_current_A` | 60 | 60 | manufacturer (continuous; the 132 A burst is not used) | power ceiling: 888 W in L0, 960 W in L1 at full SOC |
| `internal_resistance_ohm` | 0.01329 | 0.04 | v0.2: cell proxy (C, lower bound, interconnect excluded). v0.1: placeholder | losses, sag, heat, cutoff SOC (C-03, C-04, C-07) |
| `ocv_curve` | 6 knots, 12.0 to 16.8 V | same | placeholder (D). Only the 16.8 V endpoint (4.2 V/cell CC-CV charge voltage, datasheet p. 3) has a physical anchor | bus voltage for every T200 lookup, cutoff timing, energy (C-02, C-04, C-05) |
| `capacity/resistance/max_current_temperature_curve` | [[25, 1]] | same | placeholder (identity) | none numerically; the calibration flag is always on (C-12) |
| `entropy_curve_V_per_K` | absent, so 0 | absent | unknown (omitted) | reversible heat |
| `max_power_W` | absent, so ∞ | absent | unknown | — |
| `low_soc_threshold` | 0.2 | 0.2 | user policy | label only |
| `thermal.water_temperature_C` / `initial_temperature_C` | 15 / 20 | 15 / 20 | user | — |
| `thermal.thermal_capacity_J_per_C` | 1200 | 1200 | placeholder. Plausible for the 1152 g pack alone (reviewer estimate, assuming c_p ≈ 0.9–1.1 kJ kg⁻¹ K⁻¹; enclosure excluded) | temperature, derating (C-06) |
| `thermal.cooling_coeff_W_per_C` | 2.0 | 2.0 | placeholder | decides whether derating ever occurs (C-06) |
| `thermal.derating_temperature_C` | 40 | 40 | placeholder (policy) | current ramp |
| `thermal.cutoff_temperature_C` | 50 | 50 | manufacturer statement about exposure, used as an average-node operating cutoff (representative at best) | thermal latch (C-11) |
| `thermal.minimum_temperature_C` | null | null | unknown | no cold cutoff |
| `converters.propulsion_efficiency` | 1.0 | 1.0 | assumption: the T200 data include the ESC; cable and PSM losses are omitted | C-07 |
| `converters.payload_efficiency` / `hotel_efficiency` | 1.0 / 1.0 | 0.9 / 0.9 | v0.2: unknown (record `bluerov2.bec_5v_efficiency` is null/D). v0.1: placeholder | C-08 |
| `hotel_load.constant_W` | 0 (itemised components; tether interface and ESC standby unconfigured) | 15 | v0.2: user (0 plus D gaps). v0.1: placeholder | — |
| `evidence.battery_losses` | record `dc_resistance_cell_derived`, `relation: exact` | none, so D | cell proxy mislabelled as exact | C-04 |
| L0 `capacity_Wh` (from with_fidelity) | 266.4 | 266.4 | manufacturer nominal (A record), flagged placeholder by with_fidelity | L0 endurance |

### Proxy batteries (L0 only)

| Profile | Energy | Voltage | Limit | Class / issue |
| --- | --- | --- | --- | --- |
| `proxy_mares_600wh` | 600 Wh (2.16 MJ, P017) | 24 V | null | energy: literature proxy (C). Voltage: placeholder, flagged. Limit: unknown, none enforced (C-09) |
| `proxy_remus_1000wh` | 1000 Wh (P022) | 24 V from the 1997 lead-acid bus | null | energy: C. Voltage: pack proxy of a different chemistry, **not** listed in `placeholders` (C-10). Limit: unknown |
| `proxy_tethys_13kwh` | 13 kWh (P025) | 24 V | null | energy: C. Voltage: placeholder, flagged. Limit: unknown |
| `proxy_alr6000_38kwh` | 38 kWh installed (P024) | 25.2 V (7 × 3.6 V, arithmetic consistent) | null | C. Recoverable energy is 27 kWh at 25 W (−29 %), so the bucket over-states it by about 41 %; the load domain (8.4–134.4 W) is not enforced (C-09) |

### Placeholder leakage paths

- **OCV curve (D).** It sets the L1 bus voltage, and the bus voltage selects T200 power. It
  therefore drives:
  - the 3.8 % L0/L1 difference;
  - the 60 A power-limited tick share in RQ2;
  - every L1 cutoff time;
  - the energy that L1 delivers.

  The energy-weighted grade coverage still credits that propulsion energy as grade B.
- **`cooling_coeff_W_per_C`.** It alone decides whether thermal derating occurs at all (C-06).
- **R = 0.04 Ω.** This placeholder from v0.1 remains selectable from the catalogue (C-16).

## Findings

Severity counts: critical 0, major 6, minor 10.

| ID | Severity | Location | Issue | Numeric evidence / how checked | Suggested fix |
| --- | --- | --- | --- | --- | --- |
| C-01 | major | `battery.py` L227–238, L271–275; `env_wrapper.py` L502–507; `power_manager.py` L53–58 | **Voltage-limited operation is unreachable: whenever the voltage limit binds, the pack latches off.** `current_limit` caps I at (U−V_cut)/R, so V equals V_cut at the start of the tick. The end-of-tick check reuses the same I with U(SOC_end) < U(SOC_start), so V_end ≤ V_cut and the latch is guaranteed. A single 10 ms load transient therefore ends the mission. The graded voltage-limited action factor computed by the power manager (0.85 down to 0.065 between SOC 0.05 and 0.001, see `t4_pm.py`) is never applied for more than one tick. The pack has no BMS according to the profile and the BR page, so the latch is a modelling policy, not a pack property. | (1) v0.2 at SOC 0.03 with 8 × 25 N: the first tick is voltage-limited (factor 0.604, V = 12.000000000017 V) and goes straight to CUTOFF; there are 0 POWER_LIMITED ticks (`t2_env.py` b). (2) Archived N6 low-SOC trace: LOW_SOC, then CUTOFF at t = 9.2 s with SOC 0.0279, and no POWER_LIMITED state in between. The `derated_tick_fraction` of 0.694 counts post-cutoff ticks. (3) A single 60 A tick latches the pack at SOC 0.0498 for v0.2 (11.1 Wh of OCV energy stranded) and at SOC 0.30 for v0.1 (73.8 Wh of 266.8 Wh, 28 %; `t1_battery.py` §2). | Separate the *limit* from the *latch*. Either (a) latch only when the OCV, or the loaded voltage at the minimum service load, falls below cutoff, or when V < V_cut persists for a configurable time (ArduSub-style low-voltage failsafe); or (b) check the end-of-tick voltage at the current that the next tick would actually use. Rename the N6 run "voltage-cutoff latch" in the paper, and exclude CUTOFF ticks from `derated_tick_fraction`. |
| C-02 | major | `bluerobotics_4s18ah_v2.yaml` (`capacity_Ah`, `ocv_curve`); `batteries.yaml` `bluerobotics_4s_18ah.ocv_curve` | **Inconsistent SOC-0 definition, so L1 over-states the energy available above 12 V.** Q = 18 Ah is 6 × 3.0 Ah rated at 0.2C down to **2.5 V/cell**, but the OCV curve puts SOC 0 at OCV = 12.0 V = **3.0 V/cell**. Discharging to the 12 V cutoff, the model delivers at least as much energy as the manufacturer's cells deliver down to 2.5 V/cell, which is physically impossible. The model's average discharge voltage is also 0.12–0.15 V/cell above the datasheet value, which means the OCV is too high, R is too low, or both. | Model, at constant current to 12 V (inline snippet): 265.3 Wh at 0.6 A/cell, 259.3 Wh at 3 A/cell, 242.2 Wh at 10 A/cell. Datasheet × 24 cells, to 2.5 V/cell: 264 Wh (0.2C, p. 4), 250.6 Wh (1C, p. 7), 239.5–242.4 Wh (10 A, p. 7 / p. 4). The 1C model value is therefore ≥ 3.5 % high even before removing the 2.5–3.0 V tail. Average voltage per cell: model 3.65 V (1C) and 3.54 V (10 A), datasheet 3.53 V and 3.39 V. The cell-to-pack comparison assumes ideal 4S6P, and the datasheet cells self-heat to 61 °C at 10 A, which favours the cells. | Re-anchor the convention. Either define Q as the charge deliverable to 3.0 V/cell, or set OCV(0) to the relaxed OCV at the 2.5 V loaded end point. Fit OCV and R jointly to the datasheet discharge curves (pp. 6–7) as an interim **C-grade cell-proxy** curve instead of the unanchored D curve. State the bias in the limitations. |
| C-03 | major | `evidence/runtime.py` `_check_links` L136–140 | **Stale-link detection misses resistance overrides.** Only `internal_resistance_ohm` is compared with the record. A user-supplied `resistance_temperature_curve`, or an `R(SOC,T)` map (which replaces `R_ref` entirely), keeps the grade-C cell-derived link with no warning. Changing `ocv_curve`, `nominal_voltage_V` or the cell configuration also leaves the link intact. | `t2_env.py` d: with an R(T) factor of × 3, R_used = 0.0399 Ω and the grade is C with no stale link. With an R(SOC,T) map of 0.05 Ω, R_used = 0.050 Ω and the grade is still C. A control case changing `internal_resistance_ohm` to 0.04 correctly drops to D. A 5S override (OCV 15–21 V) also keeps grade C. | Compare the *effective* resistance actually used: `resistance_ref × f_R(T)` over the configured support, and the presence of a map. Invalidate the link when any battery field the record derivation depends on changes. |
| C-04 | major | `bluerov2_heavy_holoocean.yaml` L69, `bluerov2_standard_6t.yaml` L40; `evidence/runtime.py` `summarize` | **Battery-loss provenance is over-stated, and the coverage metric ignores the D-grade parameters that set state.** (a) The vehicle profiles link `battery_losses` with `relation: exact`, but the record itself is `relation: proxy`, `bound: lower_bound`. (b) The I²R loss scales with I² = (P/V)², and V comes from the D-grade OCV; that dependence is not propagated. (c) The coverage counts only consumed Wh. OCV, capacity, cutoff and thermal parameters decide the bus voltage feeding the B-grade T200 tables, the power ceiling, the derating and the end of the mission, yet none of them appears in it. A run can therefore report 0 % D-share while its timing and voltage-dependent propulsion energy rest on a D curve. | `t2_env.py` a (600 ticks, 8 × 15 N): energy by grade A 0.031 Wh, B 7.590 Wh, C 0.173 Wh, D 0.000 Wh, even though propulsion power at that bus voltage differs by +4.8 % from the nominal-voltage value (`t4_pm.py`). The outline states this limit only in prose (§9). | Set `relation: proxy`. Add a "state-parameter provenance" block to the summary (OCV, Q, R, V_cut, C_th, k, with grade and bound) that is reported next to the energy coverage. Grade voltage-dependent propulsion energy as min(T200 grade, OCV grade) whenever V ≠ nominal, or report it separately. |
| C-05 | major | `paper_outline_smpat.md` §10; `RESEARCH_STATUS.md` L57; N6 vs N4 tables | **The reported L0–L1 difference ("3.8 %") does not measure battery fidelity.** The I²R loss, the only L1-specific consumption term, is excluded from the compared terminal energy. The whole difference comes from T200 power(F, V) evaluated at 16.5 V (L1, OCV near 16.8 V at SOC ≈ 1) instead of 14.8 V (L0). Its sign reverses during the discharge. L0 and L1 also have different power ceilings at the same SOC. | N4 vs N6 transit at c = 0.2: propulsion 1.5193 vs 1.4579 Wh (+4.2 %), tracking identical to 1e-8 m, L1 losses 0.0173 Wh (1.06 % of terminal energy) not compared. Fixed 8 × 15 N relative to L0 (`t4_pm.py`): +4.76 % at SOC 1.0, +0.93 % at 0.8, −0.88 % at 0.5, −1.79 % at 0.3, −1.97 % at 0.1. Ceilings: L0 60 A × 14.8 V = 888 W; L1 at SOC 1 is 960 W. | Report the L0/L1 difference split into (i) bus-voltage effect on the actuator tables and (ii) battery losses and cutoff, at several initial SOCs, or over a full discharge. Avoid "L0 is 3.8 % below L1" as a battery-model result. |
| C-06 | major | `thermal.py`; thermal sections of both BlueROV2 profiles | **Placeholders decide the thermal behaviour, and the model heats roughly half as much as the manufacturer's single-cell test.** At 60 A continuous, the v0.2 pack settles at 38.9 °C with k = 2 W/K, just below the 40 °C derating onset. Derating needs k < 1.91 W/K and cutoff needs k < 1.37 W/K, so a 5 % change in a placeholder flips the qualitative result. With v0.1, R = 0.04 Ω gives a steady state of 87 °C. The per-cell-equivalent model heats far less than the datasheet cell at the same current. Plausible reasons: DC-IR-only heat with entropy omitted, and a k that is generous for cells packed inside a sealed air-filled tube. | `t3_thermal.py` and an inline snippet. 60 A for 1062 s from 23 °C: the model rises **19.9 K**; the datasheet single cell at 10 A (= 60 A/6P) for 17.7 min rises **37.9 K** (23 → 60.9 °C, p. 6). The adiabatic bound with DC-IR heat only is 42.3 K. Model rise for k = 1.0 and 0.5 W/K: 28.1 K and 34.2 K. Over 30 min at 40 A with v0.1, the end temperature is 45.7 / 65.8 / 84.9 °C for k = 2 / 1 / 0.5 W/K. | Present thermal results only as a sensitivity over k ∈ [0.5, 2] W/K and C_th. Add a datasheet-based sanity case. Identify C_th and k from a pack-in-enclosure test before stating derating behaviour. |
| C-07 | minor | `batteries.yaml` `dc_resistance_cell_derived`; `converters.propulsion_efficiency` = 1 | **High-current path resistance is under-represented twice.** R excludes interconnects, wiring, connectors, penetrator and PSM, and propulsion η = 1. The record's range (11.96–14.63 mΩ) uses the typical ± 2 mΩ spread only. The datasheet *specification* is ≤ 30 mΩ per cell (pack ≤ 20 mΩ), the value is "initial" (fresh cell), and cells lose capacity with cycling (73.8 % after 300 cycles, p. 8), which implies resistance growth. The DC-IR pulse duration is not stated. The cell value itself is consistent with the datasheet sag (see the verified items). | Reviewer arithmetic: each 1 mΩ of extra series resistance at 60 A adds 3.6 W and 60 mV of sag. 4 × 30/6 = 20 mΩ is the specification ceiling. | Keep `bound: lower_bound` visible in reports, add the specification ceiling as `value_max`, and add an explicit (placeholder) distribution resistance term. |
| C-08 | minor | `bluerov2_heavy_holoocean.yaml` converters; `config.model_warnings` | **η = 1.0 is a declared gap but triggers no warning.** The converters section has no `placeholders` entry, so the runtime warning list (checked) says nothing about the missing 5 V supply losses. The converter category shows 0 Wh, graded D but carrying zero weight, so the gap is invisible in the coverage. Constant η also misrepresents light-load efficiency. | Runtime warnings listed for `bluerov2-heavy`: placeholders for OCV, temperature and thermal parameters, and unconfigured tether/ESC loads, but nothing about converters. | Mark the converters `status: unconfigured` with a warning, or list the efficiencies as placeholders. |
| C-09 | minor | `battery.py` L321–331, L358–370; proxy batteries | **Proxy L0 packs with `max_power_W: null` impose no physical limit.** The whole pack can be drained in a single tick. A warning is emitted, but the power-limit feedback (a claimed feature) is disabled for all four proxies. ALR installed energy over-states recoverable energy by about 41 % at 25 W. Pack capacity does not enter any provenance coverage. | `t2_env.py` e: REMUS can deliver 360 MW for one 0.01 s tick and MARES 216 MW; SOC goes from 1 to 0 in one step. | Require an explicit `max_power_W` (with the D grade surfaced) or a domain cap (ALR 134.4 W), or refuse power above a declared domain. Report the capacity grade. |
| C-10 | minor | `proxy_remus_1000wh.yaml` | **The REMUS 24 V label comes from the 1997 lead-acid pack yet is not in `placeholders`.** MARES and Tethys list theirs. Logged currents (P/24 V) for all proxies are placeholder-derived. The P022 "300 Wh lead-acid" figure also differs from the 480 Wh rating of the 1997 pack in record `remus.bus_voltage_1997`. | Profile and record text. | List the voltage as a placeholder, suppress or flag current outputs for proxies, and annotate the 300 vs 480 Wh discrepancy. |
| C-11 | minor | `thermal.cutoff_temperature_C`; record `bluerobotics_4s_18ah.max_temperature` | **The 50 °C value is a safety statement about exposure, not an operating cutoff.** It is applied to an *average* node, so the hottest cell exceeds it. No cold limit is configured (`minimum_temperature_C: null`). | BR page safety section; profile. | Use `relation: representative`, or `policy` for the mapping. Document the average-node versus hot-spot gap and add a margin or a hot-spot factor as a policy parameter. |
| C-12 | minor | `battery.py` L181–188 and L278–286; identity temperature curves | **Cold-capacity convention and calibration flag.** (a) The accessible-tail convention removes cold capacity as an abrupt `available_charge` latch at SOC_ref = 1 − f_Q while the OCV is still high: demo pack at 0 °C, latch at SOC 0.2 with OCV 24 V against a 20 V cutoff. Combined with R(T) this can double-count; this is documented. (b) For the BlueROV2 profiles the single-knot identity curves make `temperature_outside_calibration` true at every temperature except exactly 25 °C. The flag is therefore permanently on and carries no information. | Code reading; `temperature_outside_calibration(20)` returns True. | Report "uncharacterised" separately from "outside calibration", and add a test that the cold-capacity convention does not also double R. |
| C-13 | minor | `accounting.py` `endurance`; `battery.remaining_energy_Wh` | **Endurance estimates are optimistic.** They use the OCV-work upper bound divided by terminal power, including losses and charge stranded by the load-dependent cutoff, and they read 0 after the latch. The fields are labelled as upper bounds, but `instantaneous_s` is easy to misread. | 600 W constant (`t1_battery.py` §4): the initial bound is 266.8 Wh, while delivery is 248.0 Wh for v0.2 (+7.6 % optimistic) and 218.5 Wh for v0.1 (+22 %). | Add a load-aware estimate: integrate U − I R at the current power down to V_cut, or report both. |
| C-14 | minor | `env_wrapper.py` L549, L726 | **`minimum_voltage_V` logs the start-of-tick terminal voltage.** The lower end-of-tick voltage that triggers the latch is never logged, so logs cannot show a violation of V_cut. | N6: `min_voltage_V` = 12.000000000008837. At dt = 0.01 s the error is about 1.5e-4 V at 60 A near SOC 0, which is negligible. | Log the end-of-tick loaded voltage, or the cutoff voltage, at latch. |
| C-15 | minor | `env_wrapper.py` L76–79; `power_manager.py` L48–51 | **The OCV range is not checked against the thruster-table voltage domain at configuration time.** Only `nominal_V` is checked, so an incompatible pack fails mid-mission at the first non-zero action. | Inline: a 5S override (nominal 18.5 V, OCV 15–21 V) with T200 tables (10–20 V) initialises, and zero action steps. The first non-zero action raises `ValueError: Battery OCV exceeds the thruster profile voltage range`. | Validate min/max of `ocv_curve` (and of the OCV tables) against the actuator domain in `__init__`. |
| C-16 | minor | `catalog.py` (`bluerov2-heavy-v0.1`, `bluerobotics-4s-18ah-v0.1`) | **The legacy v0.1 pack (R = 0.04 Ω placeholder) remains selectable, and switching to it changes conclusions qualitatively.** | At 600 W: 218.5 vs 248.0 Wh delivered (−12 %); thermal derating active (T_max 43.7 °C) vs none (27 °C) (`t1_battery.py` §4). | Mark it regression-only in `list_profiles`, or emit a warning when it is selected. |

## Verified correct

- **Rint terminal power.** P = I(U − IR) is solved on the high-voltage branch with the stable form
  I = 2P/(U + √(U² − 4RP)). The residual is 0 at every limit point tested (SOC 1/0.5/0.2/0.05,
  both packs). Requests above U²/4R raise an error. R = 0 falls back to I = P/U. The current limit
  includes U/(2R), (U − V_cut)/R, the charge available per tick, the temperature map and the
  optional power cap.
- **Units.** The L1 SOC update is in Ah on reference capacity and the L0 update is in Wh; units are
  consistent. Charge-per-tick limits prevent overdraw in both models.
- **Energy conservation.**
  - The terminal energy summed over categories (losses excluded) equals the battery's
    `energy_used_Wh` to 6e-15 Wh over 600 ticks.
  - Terminal energy plus losses equals the OCV work (`chemical_energy_Wh`) exactly.
  - In the auxiliary-shortage branch, loss = available − served, so power is conserved (hotel
    1500 W: service 0.638 at 960.2 W).
  - E_chem + remaining(end) = remaining(start) to 0.02 Wh at dt = 1 s (left-Riemann OCV).
- **`remaining_energy_Wh`.** The trapezoid rule over the union of knots is exact for piecewise-linear
  OCV, including bilinear temperature tables. The placeholder curve integrates to 266.76 Wh against
  the nominal 18 × 14.8 = 266.4 Wh (+0.13 %).
- **Thermal model.**
  - The analytic step matches the closed form and a 1 ms Euler integration: 37.293294 vs 37.293299 °C.
  - Units are consistent (J/K, W/K, W).
  - The heat-limited current is the algebraically equivalent stable root of R I² − aI ≤ H.
  - The no-overshoot property holds: a step from 49 °C ends at exactly 50.000000000 °C. The linear
    current derating keeps the system in equilibrium below cutoff, so the thermal latch is
    practically unreachable.
- **Reversible heat sign.** Q = I²R − I T_K dU/dT for positive discharge current matches the Bernardi
  convention.
- **Monotonic derating.** The derating factor is monotone in temperature. The power-manager action
  factor is monotone in SOC (0.995 down to 0.065) and in temperature (0.995 at 40 °C down to 0.0025
  at 49.99 °C). The current bisection runs on the monotone branch because i_max ≤ U/2R.
- **Cell-to-pack scaling.** 4 × 19.94 mΩ / 6 = 13.29 mΩ, with the range 11.96–14.63 mΩ, is correct
  for 4S6P with equal sharing. The source values (19.94 ± 2 mΩ DC, 10 A to 1 A) match datasheet
  pp. 3 and 5. Average-voltage sag on datasheet pp. 4 and 7 implies an effective 17–23 mΩ per cell
  (reviewer arithmetic, confounded by self-heating), consistent with the DC-IR value at cell level.
- **Pack ratings.** 18.0 Ah, 266.4 Wh, 14.8 V, 4S6P, 60 A continuous, 132 A for 10 s and the
  12 V minimum safe voltage all match the BR product page. The 132 A burst is correctly not enabled.
- **Converters.** P_in = Σ P_out/η per rail follows S9, and the conversion loss is the residual.
- **Proxy arithmetic.** MARES 2.16 MJ = 600 Wh; ALR 7 × 3.6 V = 25.2 V and 7s80p; the 41 % ALR
  over-statement is stated in the profile.
- **Documentation honesty.** Placeholders are declared and warned for OCV, temperature maps and
  thermal values; `scientific_sources.md` documents the latch, the Rint simplifications and the
  missing RC dynamics; the paper outline lists placeholder OCV/R and missing thermal data as
  threats to validity.
