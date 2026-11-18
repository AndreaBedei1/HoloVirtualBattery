# Verification and validation framework (reviews I-08, G-13)

The terms follow common simulation V&V usage. Verification asks whether the model is solved and
implemented correctly ("are we building the model right"). Validation asks whether the model
represents reality for the intended use ("are we building the right model"). Before citing a standard
(for example ASME V&V 20 or Oberkampf and Roy), read it and record it in RELATED_WORK_VERIFICATION.md;
none is cited yet. The credibility-scale paper that has been verified is Blattnig et al. 2008 [S13].

## Categories

| Category | Question | What would count as evidence |
| --- | --- | --- |
| **Code verification** | Are the equations implemented as written? | Tests against analytical results; regression tests for each defect found |
| **Calculation (solution) verification** | Are numerical errors controlled for the runs used? | Timestep study, integration-error bounds, determinism |
| **Input verification** | Were values transferred correctly from their sources? | Record-by-record traceability, unit checks, hand recomputation |
| **Model verification** | Does the implementation reproduce the intended (conceptual) model? | Closure of the coupled chain, conservation identities, replay equivalence |
| **Model validation** | Does the model reproduce physical measurements of the system it represents? | Comparison with measured electrical energy or power of the vehicle or its sub-models |
| **Predictive validation** | Does it predict measurements under independent conditions? | Hold-out field or tank data not used for any parameter |
| **Uncertainty quantification** | How do uncertain inputs affect outputs? | Propagated ranges, sensitivity analysis, open bounds stated |

## Mapping of the HoloEnergy evidence

| Activity / experiment | Category | Result | Limits |
| --- | --- | --- | --- |
| 363 automated tests, including the regression tests for review findings | Code verification | Pass (CI) | Tests check the implementation against its own equations |
| `verify_final_energy.py`: recomputation of every energy from the 100 Hz traces | Code verification / model verification (accounting) | 36/36 runs, worst relative error 2.5e-13 | Same power model, so it detects accounting errors, not model errors (D-19) |
| Bus energy = Σ categories; OCV work = bus + losses; cross-layer bus = modem adapter | Model verification (conservation) | Closed to ≤ 1e-15 Wh | Identities of the model |
| Chain closure (force residual of the requested → applied wrench) | Model verification (coupling) | Residual < 1e-4 N per tick | Dynamics owned by the simulator |
| EXP11 replay of the native mission (energy-only backend) | Model verification (determinism, replay equivalence) | Relative difference 0.0 | Valid when payload does not feed back (no derating) |
| EXP1 backend check (patched vs unpatched HoloOcean) | Code verification **of the simulator backend** (is the declared drag equation applied?) | PASS 1.000000 / FAIL ×0.0100 | Does not validate the drag coefficients |
| Timestep audit at 20–200 Hz (`holoocean_timestep_report.md`) | Calculation verification | 100 Hz used; 20 Hz rejected | Simulator integrator |
| Parameter audit (54 records), unit conversion, stale-link detection | Input verification | Every final parameter traced to a record with location | Manufacturer tables are **inputs**, not validation (A-01) |
| EXP9: HoloOcean surge resistance vs published BlueROV2 measurements | External consistency check of the drag sub-model (not a validation: different vehicles and conditions; review R4-08) | Restrained-load data give 0.11–0.22×; identified damping 0.87–1.29× | Different vehicles and conditions; the references disagree with each other by a factor of 6–9. Not validated. |
| Lam et al. 2023 tow-tank series | Input evidence for a sensitivity case (inflow bias of the static T200 tables) | About +5–8 % power per newton at J ≈ 0.1–0.13 | One command level, one voltage, no uncertainty |
| Tun et al. 2026 | **Not** validation | Energy reconstructed from the static T200 curve | Usable only as a parameter comparison |
| EXP10: drag model, modem settings, allocator, anisotropy | Uncertainty quantification (sensitivity analysis) | See CLAIM_EVIDENCE_MATRIX C8, C10, C12, C17 | One-at-a-time, deterministic; not probabilistic UQ |
| EnergyReport intervals (published ranges; open sides kept open) | Uncertainty quantification (interval propagation) | Per run | First order; propulsion excluded unless a dynamics range is supplied |
| EXP11 decision case | Decision analysis under evidence uncertainty | A nominal ranking that the evidence does not support; certification blocked by named contributions | Uses the evidence intervals and the stated scenario choices |
| Mission-level energy vs a measured vehicle | **Model validation: absent** | No measured BlueROV2 mission energy is available; no suitable public dataset was found | Stated as the main limitation |
| Independent-condition prediction | **Predictive validation: absent** | None | |

## Consequences for the claims

- Nothing in this work is called validation. The EXP9 drag comparison is an external consistency
  check, and its result is conflicting.
- Manufacturer tables used directly as model inputs are input evidence (traceability), not validation.
- Agreement of the energy recomputation is verification of the accounting.
- The contribution is a verified, evidence-traceable modelling method with simulator-conditional
  case studies. Physical validation is future work and needs measured electrical data from a vehicle.
