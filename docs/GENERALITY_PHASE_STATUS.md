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

## Planned work (in order)

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
