# Claim–evidence matrix

Every statement the manuscript may make is listed here with the evidence that supports it and the
conditions that limit it. Numbers come from the final results in `experiments/results/final/`:
- native runs from commit 81b91ea, clean tree;
- cross-layer run started from commit b73ae9f with a clean tree. Documentation and result files were committed while it ran, so the per-strategy EnergyReports record HEAD at report time (b73ae9f, 275e226, 5d9e102) with a dirty tree; between b73ae9f and 5d9e102 the only code change is the new analysis script, which the run does not use (review J-02);
- design fixed in `docs/paper/FINAL_EXPERIMENTS.md`.

A claim that is not listed here must not appear in the paper.

**Status values:**
- **S**: supported as stated.
- **SC**: supported under the stated condition only.
- **N**: not supported; removed or rewritten.

## Software, verification and provenance

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C1 | The drag-patched HoloOcean 2.3.0 build applies its declared SI drag and integrates the client step at 100 Hz. The unpatched build applies 0.01× the declared drag. | `backend/check_patched_after.json`: PASS, observed/expected 1.000000 (current and still water), step ratio 1.000000. `backend/check_rebuilt_before.json`: FAIL, ×0.0100. | S | Verifies the simulator's implementation of its own equation, not vehicle hydrodynamics. The defect is still present in HoloOcean 2.4.0 (source reading only, review G). |
| C2 | Every reported energy can be recomputed from the per-tick power trace, and the accounting is closed. Bus energy equals the sum of the categories; OCV work equals bus energy plus battery loss. | `energy_verification.json`: 36/36 PASS, worst relative error 1.9e-13 (tolerance 1e-9). Cross-layer: bus minus modem-adapter energy ≤ 1e-15 Wh for all 8 strategies. | S | Numerical verification of the implementation, not validation. |
| C3 | Every parameter used in the final experiments is traceable to a registry record with source, location, relation and grade. Unknown values remain unconfigured. | `data/evidence/final_parameter_audit.*`: 54 records. Effective grades: A 24, B 12, C 3, D 15. 8 are upper bounds only; 14 are unconfigured or unlinked. | S | A grade states traceability and relation to the modelled device, not accuracy. Grade D values are user scenario choices or placeholders. |
| C4 | Evidence grades are capped by the relation between record and application (exact → A, representative → B, proxy → C, user → D), and the cap is applied automatically. | `holoenergy.evidence.cap_grade`; tests in `tests/test_evidence_links.py`; audit columns `applied_relation` and `effective_grade` (review A-03 fix). | S | The grading scheme is a convention defined by this work, not a validated metric of uncertainty (review G-05). |

## Actuation and layout (EXP3, EXP4)

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C5 | In head-on current, L8-HV, L6-STD and L4-H45 need the same energy over 90 s: mission (terminal) energy 0.4897 Wh at 0.2 m/s and 6.5295 Wh at 0.5 m/s, of which propulsion is 0.3459 and 6.3858 Wh. Steady propulsion (mean of the last 30 s) is 249.2 W at 0.5 m/s; the last 10 s mean is 1.3 % lower. | `final_runs.csv` | SC | The equality is a property of HoloOcean's decoupled, neutrally buoyant body: drag acts at the centre of mass and the horizontals lie in the CoM plane. Only the four vectored horizontals work (review B-03). It is not a statement about physical vehicles. |
| C6 | L4-2H2V needs 14 % less mission energy than L8-HV in head-on current at 0.5 m/s (5.5988 vs 6.5295 Wh terminal; propulsion 5.4550 vs 6.3858 Wh, −15 %) but cannot hold sway or oblique current. Its final tracking error is 31.4 m (sway) and 26.9 m (oblique). | `final_runs.csv` | SC | Geometry grade D (benchmark design); isotropic simulator drag. |
| C7 | L8-VEC30 needs 23 % more mission energy than L8-HV in head-on current at 0.5 m/s (8.0398 vs 6.5295 Wh terminal; propulsion 7.8960 vs 6.3858 Wh, +24 %). | `final_runs.csv` | SC | Geometry grade D. |
| C8 | Horizontal thruster angle trades head-on against sway cost. Mission (terminal) energy over 90 s at 0.5 m/s: 30° 4.81 / 13.18 Wh (head-on / sway), 45° 6.53 / 7.78 Wh, 60° 10.92 / 5.70 Wh. Each includes 0.144 Wh of hotel load. | `final_runs.csv` (EXP4, EXP3) | SC | The size of the trade-off depends on the drag law. With the identified anisotropic damping the sway/head-on cost ratio at 45° rises from 1.20 to 1.77 (EXP10 part 4). Report the direction of the trade-off, not the magnitudes. Excluding the trivial heave cases, the layout ranking within each horizontal current direction is the same under both laws in 3 of 6 cases (review I-06). |
| C9 | All final layouts hold an oblique 45° current of 0.5 m/s in the steady window, except L4-2H2V. The start-up transient saturates the thrusters for 21.6 % of the run, and the oblique runs are still settling in the window: the last 10 s mean is 6.2–7.3 % below the 30 s mean (217.5 W for L8-HV). | `final_runs.csv`: `steady_window_request_met` True, `request_met` False | S | Saturation occurs in the transient only. |
| C10 | The choice among the three implemented allocators changes steady propulsion power by at most 0.13 %. | `sensitivity.json` part 3 | SC | Steady pure-force cases within the clamp only. |
| C11 | L8-HV cannot hold a 0.8 m/s head-on current. The allocation saturates for 92.7 % of the run and the final tracking error is 12.1 m. | `final_runs.csv` | SC | Simulator drag (115 N required vs 81.3 N available at the clamp). |

## Environment and mission (EXP5)

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C12 | In simulation, station-keeping propulsion (30 s window mean) grows steeply with current: 13.4 W at 0.2 m/s, 249.2 W at 0.5 m/s, 610.2 W at 0.8 m/s (the last one infeasible). In still water only hotel loads consume energy (0.1438 Wh in 90 s). | `final_runs.csv` | SC | Absolute values follow HoloOcean drag. Using published BlueROV2 resistance instead changes the propulsion power to 0.11–0.22× (Gabl et al. 2021) or 0.87–1.29× (von Benzon et al. 2022, inside its identified range) (EXP10 part 1). |
| C13 | Transit energy (same mission, settled end) is 0.647, 1.763 and 5.220 Wh at 0, 0.2 and 0.4 m/s current. | `final_runs.csv`; final tracking error 0.025 / 0.000 / 0.236 m | SC | Includes Unreal linear damping, a ground-referenced term with no physical counterpart in current. It is 21 % (calm), 12 % (0.2 m/s) and 5 % (0.4 m/s) of the time-mean resistance, and up to 81 % in single phases (review B-07). |

## Payload (EXP6)

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C14 | Switching the payload on only in the mission phases that use it reduces mission energy on the 0.2 m/s transit by 33 % for the inspection suite (3.146 → 2.116 Wh) and by 10 % for the AI suite (2.036 → 1.823 Wh). | `final_runs.csv` | SC | Scenario choice of phases. OFF is rail gating (0 W). Powers are datasheet values; the sonar and the lights are upper bounds. The Gemini sonar needs a 19–74 V supply: its step-up converter is unconfigured, so the inspection energy is a lower bound with respect to conversion loss (review A-04). |

## Battery (EXP8)

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C15 | Over the 0.2 m/s transit, L1 propulsion is 4.4 % above L0 (1.6396 vs 1.5710 Wh). The difference comes from the T200 tables evaluated at the higher L1 bus voltage. L1 battery loss is a separate 0.0201 Wh. | `final_runs.csv` | SC | This is not a battery-model validation (review C-05). The difference depends on SOC and changes sign during a discharge (review C-05 offline check). |
| C16 | From SOC 0.03 the L1 pack keeps operating voltage-limited at the 12.0 V cutoff. It derates to 0.313 and does not latch off. Propulsion falls as the voltage falls: 125.1 W over the last 30 s and 101.7 W over the last 10 s, against 249.2 W for the same request at full charge. | `final_runs.csv` (EXP8-lowsoc) | SC | Model behaviour only. The OCV curve is grade D and its SOC-0 point is inconsistent with the rated capacity (review C-02). No endurance or available-energy claim is made. |

## Communication (EXP7, EXP10 part 2)

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C17 | On the 0.2 m/s transit the acoustic modem takes 1.45 % of terminal energy as simulated (direct link, 2.8 W TX at the 1000 m setting, RS-232, DESERT 4.8 kbit/s PHY, 2 s period). Across published TX settings, interface and airtime basis the direct-link share is 1.13–13.2 %. The lowest share over all strategies, 0.96 %, is the fixed-relay case, in which the vehicle does not transmit (review J-08). | `crosslayer.json`, `sensitivity.json` part 2 | SC | A conditional point estimate, not a bound. RX/LISTEN is priced at the published upper bound (0.8 W). DC/DC conversion from the 24 V supply is not modelled. |
| C18 | Relay choice redistributes modem energy between nodes. With a fixed relay the vehicle spends 0.0171 Wh, against 0.0253 Wh when it forwards and 0.0260 Wh on the direct link. Network-wide modem energy is 0.0860 and 0.0855 Wh with relays, against 0.0431 Wh direct. Delivery is 37/39 (fixed relay), 34/39 (vehicle relay) and 39/39 (direct). | `crosslayer.json` | SC | One geometry, one traffic pattern, one seed per strategy in the cross-layer run. |
| C19 | In the communication matrix, 8 of 9 configurations give identical delivery and energy across 20 seeds. Multi-hop with MAC ACK (B2) delivers 61/200 messages (Wilson 95 % interval 0.245–0.372). | `comm_matrix.json` | SC | In the other configurations the seed changes latency but not delivery or energy; B2's ACK and backoff make delivery seed-dependent (review J-09). The B2 result is a property of that protocol configuration, not a general one. |
| C20 | The optical link (LUMA 250LP at 5 m, 250 kbit/s) uses 0.0111 Wh against 0.0260 Wh acoustic on the same mission. | `crosslayer.json` | SC | 5 m link inside the rated 7 m range. TX is priced at the profile's maximum. |

## Generality, evidence separation and decision relevance (generality phase)

| # | Claim | Evidence | Status | Conditions and limits |
| --- | --- | --- | --- | --- |
| C21 | A robot unlike the reference vehicle can be configured without core changes. The tests and example cover 5 and 7 actuators in arbitrary layouts, user thrusters with their own tables, a custom pack, library components selected by name and the user's own evidence (measurement, datasheet, dataset, assumption). That evidence reaches component and actuator grades, battery losses, intervals and the report. | `tests/test_generic_robot.py`, `tests/test_robot_profile.py`, `examples/custom_robot_from_components.py` (355 tests pass at 15d8826) | S | Software capability. The dynamics remain those of the simulator backend; one payload-rail efficiency is modelled. |
| C22 | Electrical-model evidence and dynamics evidence are reported separately. In the final BlueROV2 missions, 52–100 % of mission energy is propulsion (78–98 % for the transits and the scheduled payload missions). Its value follows dynamics that are simulator-literal, conflict with the published external measurements, and have no physical validation. | `evidence.dynamics` (de69564); `final_runs.json`; EXP9 | S | The electrical grade shares say nothing about the accuracy of the thrust demand (review I-03) |
| C23 | Parameter-level evidence changes a design decision. On the final inspection mission: (i) the nominal values rank the Gemini 720is below the Oculus M750d, but the published ranges do **not** support that ranking; (ii) the Ping360 is supported as lower than both, by at least 0.052 Wh relative to the Gemini; (iii) no payload configuration can be certified for any leg target from 40 to 100 per charge, and the blocking contributions are named: payload-rail conversion, the DVL's typical value, and the Gemini's step-up converter. If a measurement put the rail efficiency at 0.80–0.95, the Oculus would be certifiable for 81–85 legs and the Ping360 for 88–91, while the Gemini would remain blocked. | `decision_case.json` (EXP11 part A); replay equals the native run (relative difference 0.0) | SC | The leg targets and the 30 % reserve are scenario choices. The hypothetical efficiencies are what a measurement would need to show, not evidence. Propulsion enters at its nominal value. |
| C24 | "The optical link uses less modem energy than the acoustic link" is supported by the published power records on the same mission: optical [0.0108, 0.0111] Wh against acoustic [0.0124, 0.0260] Wh. | EXP11 part B | SC | Recomputed from the recorded state durations; one geometry and one traffic pattern |
| C25 | The layout choice "L4-2H2V needs less propulsion than L8-HV in head-on station keeping" is supported at 0.5 m/s under all four dynamics alternatives (native run, isotropic steady, identified anisotropic damping, T200 inflow correction). It is not supported at 0.2 m/s. It holds only if the current is known to be head-on, because L4-2H2V cannot hold sway or oblique current. | EXP11 part C | SC | Simulator body; the alternatives are published models, not validated ones |
| C26 | The static T200 tables under-predict head-on station-keeping propulsion by about 7–9 % (L8-HV 1.071 at J = 0.139; L4-2H2V 1.087 at J = 0.165). The 0.5 m/s layout ranking survives the correction. | `sensitivity.json` part 5; Lam et al. 2023 Figs. 16–17 (record `bluerobotics_t200.advance_ratio_series_34p5rps`) | SC | Assumptions: one tow-tank series (one command level, 14.8 V), propeller similarity, axial inflow without hull wake. The grade B (representative) of the static tables is kept, with this bias quantified (review G-11). |
| C27 | Structures reproduced from existing approaches cannot represent the effect of current on propulsion. A constant-power state machine (Danielis et al. 2021) and a Gazebo-style constant thruster load, both calibrated exactly on the calm transit, give 0.52 and 0.55 Wh for the 0.4 m/s transit against 5.10 Wh. For 0.5 m/s station keeping they give 0.05 and 0.64 Wh against 6.39 Wh. Their communication energy is close to HoloEnergy's (0.0241 vs 0.0260 Wh). | `tool_comparison.json`; docs/paper/COMPARATOR_MATRIX.md | SC | A model comparison (published structures reproduced), not tool execution. HoloEnergy's propulsion follows unvalidated simulator drag. |
| C28 | The V&V activities are classified as code, calculation, input and model verification, sub-model validation attempt, and uncertainty or sensitivity analysis. Model validation and predictive validation of mission energy are absent. | docs/paper/VERIFICATION_VALIDATION_FRAMEWORK.md | S | No suitable public measured mission-energy dataset was found (docs/literature/mission_energy_datasets.md) |
| C29 | `assess_energy_requirement` and `compare_energy` return physical verdicts on the bus side. Unknown contributions, unverified conversion and upper-bound-only values are carried as open sides, never as assumed values. | `holoenergy/decision.py`; `tests/test_decision.py` (including the adversarial-review regressions) | S | Propulsion has no published uncertainty; it is a point value unless the caller passes a dynamics factor range |

## Claims removed or rewritten

| Former claim | Why | Replacement |
| --- | --- | --- |
| "An acoustic modem adds at most 1.37 %" | Not an upper bound: it uses the lowest TX setting and the simulator PHY (reviews D-01, A-05) | C17 |
| Baseline comparison (speed-cubic, constant power) as validation | Model versus model; the error is set by current direction and Unreal damping, not by drag isotropy (reviews B-06, G-02) | Not in the final set; may be mentioned only as a sensitivity of a simple model, without validation wording |
| "L0 is 3.8 % below L1" as a battery-fidelity result | Bus-voltage effect on the actuator tables (review C-05) | C15 |
| Layout energy equality as a design finding | Simulator body property (review B-03) | C5 |
| "Component level validated by construction from manufacturer tables" | Manufacturer tables are model input (review A-01) | Called input traceability |
| "No published T200 data at advance speed" | Lam et al. 2023 reports such data; it has not been accessed (review A-02) | "One peer-reviewed source reports non-bollard T200 data; it was not accessed." |
| "DESERT simulates protocols, not electrical energy" | DESERT `uwphysical` counts TX/RX energy (review G-04) | The contribution is listen/idle states, evidence grading, and coupling to the battery and the vehicle dynamics |
| Any validation of mission energy against a physical BlueROV2 | No measured mission energy is available (review G-01). Tun et al. 2026 reconstruct energy from the static T200 curve, and the dataset search found no suitable public measurement. | None |
| "No published T200 data at advance speed" | Lam et al. 2023 reports a tow-tank series (now read and recorded) | C26 |
