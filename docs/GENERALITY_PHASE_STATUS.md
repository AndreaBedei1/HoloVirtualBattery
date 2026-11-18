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

## In progress / remaining

- Code reviews running: adversarial-coach, integration-enforcer, test-authenticator. Apply the
  confirmed fixes, then regenerate decision_case.json, tool_comparison.json and sensitivity.json.
- Dashboard: show `scientific_warnings` and `dynamics_evidence`; fix the comms-panel modem
  classification; add an actuator legend. Profile-builder page if feasible.
- Docs: generic_framework.md (builder, evidence workflow §30), README update.
- Claim matrix (decision relevance, generic configuration, tool comparison, V&V); manuscript
  restructure (RQ1–RQ6, sections §37).
- Reviewers 1–6 and the final gate.

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
