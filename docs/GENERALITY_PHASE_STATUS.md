# Generality and V&V phase: status (started 2026-11-18, from ba72ade)

The brief is the user's 44-point prompt of 2026-11-18. It asks for a generic robot, component and
evidence API, plus resolution of I-02 (decision relevance), I-03 (dynamics evidence), I-08 (V&V
framing), G-11 (T200 grade), C-02 (OCV), D-09 (converters), a tool comparison and reproducibility.

## Decisions taken (with evidence)

| Topic | Decision | Basis |
| --- | --- | --- |
| New sources | 5 PDFs added 2026-11-16, all read in full | docs/literature/ |
| T200 inflow (G-11, A-02) | **No inflow-aware power model.** The static tables stay the propulsion model, relation representative (B). The bias is quantified as a sensitivity: at a fixed command, power per newton is about +5–8 % at J = 0.10–0.13 and about +20 % at J = 0.3 | Lam et al. 2023 Figs 16–17: one command level, 14.8 V only, J ≤ 0.31, no power-vs-J, no uncertainty. Record `bluerobotics_t200.advance_ratio_series_34p5rps`. Station keeping at 0.5 m/s runs at about 16 N per thruster, which is the Lam operating point. |
| Battery OCV (C-02) | **Kept grade D.** No 30Q OCV data are available locally. The Mendeley dataset doi 10.17632/g7ncmhrcrz.2 was not downloaded (download needs the author's approval). | Wu et al. 2026: unpublished 30Q tests at 25 °C, public data from a different cell; no OCV or resistance |
| Thermal | Illustrative only. No quantitative thermal claim. | No defensible pack or enclosure values in any source |
| External validation | Tun et al. 2026 is **not** electrical validation: energy is reconstructed from a polynomial fitted to the static T200 data at 16 V. No public measured mission-energy dataset was found (§23). | docs/literature/tun2026.md, mission_energy_datasets.md |
| Comparators | Danielis 2021: constant-power state machines, no propulsion physics. LOTUSim-Energy: effort-linked battery plugin, no equations in the paper; code on GitHub. | docs/literature/ |
| D-grade review | 15 parameters: 1 structural, 9 non-critical, 5 important (OCV, ESC idle, 5 V BEC and hotel/payload converter efficiencies). Unconfigured converter efficiency becomes an open upper side of the interval. | docs/paper/D_GRADE_PARAMETER_REVIEW.md |

## Done (commits b6312d7 … 52787ac)

- **Literature:** notes and the Lam T200 record (b6312d7). D-grade/upper-bound review (904ee70).
- **Decision API** (6a16a1c):
  - `assess_energy_requirement`;
  - supply-domain check (`supply_V`/`serves`);
  - unverified-conversion open bounds;
  - unconfigured loads become unknown contributions.
- **User evidence and actuators** (dc3aa23):
  - one registry per run (packaged + `evidence.sources/records`);
  - per-actuator links (`evidence.actuators`);
  - actuator `voltage_policy: table_voltage`;
  - user dataset paths;
  - `compare_energy` (paired); EXP11 script.
- **Builder** (e95a899): `holoenergy.robot` (RobotEnergyProfile and the component, thruster, battery,
  converter and evidence specs), `EnergyAwareEnv(energy_profile=)`, `thermal: {model: isothermal}`,
  catalog `actuators()`.
- **V&V framework and comparison** (e3b2d24): `docs/paper/VERIFICATION_VALIDATION_FRAMEWORK.md`;
  `experiments/run_tool_comparison.py`.
- **Dynamics evidence** (de69564): `evidence.dynamics`, reported apart from the electrical grades.
  BlueROV2: simulator_literal / conflicting / absent.
- **Reproducibility** (5c2092a): `tools/make_trace_archive.py` builds a Zenodo-ready archive of 77 MB,
  locally in `dist/`, not uploaded; final-run backend hashes are in `holoocean_patched_build.md`.
- **Example** (594d3ca): `examples/custom_robot_from_components.py` (five actuators, user evidence).
  **Comparator matrix** (95999c2).
- **EXP10 part 5** (52787ac): T200 inflow bias +7.1 % (L8-HV, J = 0.139) and +8.7 % (L4-2H2V,
  J = 0.165). The 0.5 m/s ranking survives.
- **EXP11 results** (from a draft run, to be regenerated after the code reviews):
  - Gemini < Oculus is nominally true but not supported by the evidence.
  - Ping360 is supported as cheaper than both.
  - Every feasibility verdict is INDETERMINATE (5 V rail conversion, DVL typical value, Gemini
    step-up converter).
  - What-if, payload rail efficiency 0.80–0.95: Oculus 69–82 legs, Ping360 74–88 legs, Gemini
    still blocked.
  - "Optical uses less than acoustic" is supported.
- **Same-mission comparison:** state-machine and Gazebo-style models reproduce the calm calibration
  exactly. They miss the current effect (0.4 m/s transit 0.52 vs 5.10 Wh; 0.5 m/s station keeping
  0.05 / 0.64 vs 6.39 Wh).

## Reviews of the new code (all addressed in 701757b and 15d8826)

- **Integration:** modem records now reach the intervals; `serves` names are checked; the summary
  exports per-actuator records; the dashboard and text report show the warnings and the dynamics
  evidence.
- **Adversarial:**
  - C1–C3: bus-side, rail-aware paired comparison; unknown contributions never cancel;
  - H1–H8: open-low and propulsion factor on the bus side; a rail is verified only by a matching
    efficiency record; actuator links validated; an unreadable dataset makes the link stale;
    reference relations cap the grade;
  - M2–M7 fixed.
- **Test audit:** weak tests strengthened. 355 tests pass at 15d8826.

## Final EXP11 numbers (15d8826, `experiments/results/final/decision_case.json`)

- **A. Payload:**
  - Replay equals the native run (difference 0.0).
  - Nominal legs per charge (30 % reserve, 186.5 Wh): Gemini 88, Oculus 86, Ping360 92.
  - Every leg target 40–100 is INDETERMINATE.
  - Blocking contributions: the payload rail has no converter evidence; the DVL's typical value
    is unbounded; for the Gemini, also its step-up converter.
  - What-if (hypothetical measurement of the payload rail efficiency at 0.80–0.95): Oculus
    certifiable for 81–85 legs, Ping360 for 88–91; the Gemini stays blocked.
  - Rankings: Gemini < Oculus is nominally true but NOT supported; Ping360 is supported as lower
    than both (Gemini − Ping360 ≥ 0.0516 Wh).
- **B. Communication:** "optical < acoustic" is supported (optical [0.01082, 0.01108] Wh vs
  acoustic [0.01243, 0.02599] Wh).
- **C. Layout (L4-2H2V < L8-HV, head-on):** supported at 0.5 m/s under all four alternatives
  (native, isotropic, von Benzon, inflow-corrected); not supported at 0.2 m/s (reversed under
  isotropic steady and inflow-corrected). L4-2H2V cannot hold sway or oblique current; L8-HV can.

## Remaining (in order)

1. Docs: `docs/generic_framework.md` and README (builder API, evidence workflow §30, decision
   API, `evidence.dynamics/sources/records/actuators`, `voltage_policy`, `supply_V`/`serves`,
   isothermal thermal model).
2. Claim matrix: add claims for decision relevance (EXP11), generic configuration (tests +
   example), tool comparison, V&V, T200 inflow bias (+7.1 / +8.7 %), dynamics evidence; remove or
   adjust obsolete claims.
3. Manuscript restructure per brief §35–37 (RQ1–RQ6, 14 sections), bound to the claim matrix.
4. Reviewers 1–6, run independently: literature/evidence, physics, electrical, numerical/V&V,
   hostile SIMPAT (with the 10 questions of §41), reproducibility.
5. FINAL_SIGNOFF update with the §42 gate; final report per §43; push; CI.
6. Still pending user decisions: 30Q dataset download (OCV stays D), trace archive upload,
   upstream HoloOcean issue, merge to main, the OpenEI 18 GB ROS-bag dataset.

## Planned work (original order)

1. **Registry threading and builder API** (`holoenergy.builder`). It compiles to the existing config, so
   there is no second model path. User EvidenceRecords reach components, modems and links.
   EnergyAwareEnv gains `energy_profile=`.
2. **Supply-voltage domain check**: components with `supply_V` outside the bus range get a structured
   warning and an open upper side.
3. **Intervals**: unconfigured converter efficiency opens the upper side of the loads it serves;
   unconfigured loads become unknown contributions.
4. **`assess_energy_requirement(report, max_energy_wh, ...)`**: nominal pass,
   evidence-supported pass or fail, or indeterminate, with unknown and upper-bound contributions and
   the dynamics treatment stated.
5. **Decision experiment EXP11**:
   - payload configurations on the final EXP6 mission, replayed from the 100 Hz trace;
   - legs per charge with a stated reserve;
   - layout choice under alternative drag laws and the inflow bias;
   - acoustic versus optical using the cross-layer intervals.
6. **Electrical and dynamics evidence reported separately** in the evidence summary.
7. **Documents**: VERIFICATION_VALIDATION_FRAMEWORK.md, comparator matrix and same-mission model
   comparison (Danielis-style power state machine; Gazebo linear battery with constant loads).
8. **Custom 5- or 7-actuator robot example**, dynamic dashboard check, profile-builder page if feasible.
9. **Reproducibility**: Zenodo-ready archive of the 100 Hz traces (not uploaded); patched-build recipe
   with hashes.
10. **Reruns** only if models change; claim matrix; manuscript restructure (RQ1–RQ6).
11. **Reviewers 1–6** and the final gate.

## Round-2 independent reviews (docs/reviews/round2_*.md)

| Reviewer | Verdict | Fatal | Key findings | Status |
| --- | --- | --- | --- | --- |
| 1 Literature/evidence | major revision | 0 | R1-01: the EXP11 nominal values are published maxima (say so); R1-02: references missing (Gemini, Oculus, Ping360, DVL, RPi, Wu 2018); R1-03: audit lacks the Oculus and Ping360 records; R1-04: comparison generalised from reproductions; R1-05: prior art in the local library not discussed (De Carolis 2018, Cruz, Tethys, Potokar 2024 JOE, HoloOcean 2.0, ICAR 2025) | text fixes pending |
| 2 Physics | major (§12.3) | 0 | R2-01: inflow correction at fixed thrust, (I/I0)/(T/T0)^1.5 | **fixed de15e7c**: factors 1.133 (L8-HV) and 1.162 (L4-2H2V), 0.5 m/s ranking holds. R2-04 (m c u excluded), R2-05 (Gabl range includes noise/infeasible points), R2-06 (oblique windows not stationary), R2-07 (added mass): text pending |
| 3 Electrical | running | – | – | – |
| 4 Numerical/V&V | major | 0 | R4-01/02/03 | **fixed de15e7c**. R4-06: closure 2.49e-13, not 2.5e-13 (fix numbers); R4-07 wording ("separate", tolerance rationale); R4-08: EXP9 is an "external consistency check" | text pending |
| 5 Hostile SIMPAT | major (reject without an empirical anchor) | 3 | R5-01: no measurement (needs data); R5-02: decision case "constructed", decision.py ignores grades, propulsion at nominal; R5-03: dynamics evidence not consumed by the verdicts | software fix planned: `min_grade` and a dynamics policy in decision.py; EXP11 with the propulsion range [0.11, 1.50]. Also: "52–100 %" wrong (three runs at 0 %); 2.5e-13 → 2.49e-13 |
| 6 Reproducibility | partly | 0 | provenance stamps (**fixed**, but outputs regenerated while review files were untracked show dirty=True: commit them and regenerate); procedure omits decision/tool/archive steps; availability section incomplete | pending |
