# Final sign-off

## Generality and V&V phase (2026-11-18, HEAD after bce982b)

**Verdict: NOT READY for submission.** The work is close to READY WITH LIMITATIONS. The items below
that are marked partly are what remains.

| Gate item (brief §42) | State | Evidence |
| --- | --- | --- |
| I-02 resolved (decision relevance) | yes, in software; still contested | EXP11 (C23–C25): a nominal ranking the evidence does not support; certification blocked by named contributions; grade (`min_grade`) and strict-dynamics policies change verdicts. Reviewer 5 still finds the case narrow (0.02–0.05 Wh margins on a 2 Wh mission); the policies were added after that review and have not been re-reviewed. |
| Formal V&V added | yes | VERIFICATION_VALIDATION_FRAMEWORK.md; EXP9 relabelled as an external consistency check (R4-08) |
| T200 inflow judgement resolved | yes | Grade B kept. Bias quantified at +13–16 % at fixed thrust (C26, R2-01). Lam et al. 2023 is insufficient for an inflow-aware model. |
| Battery placeholder reduced or excluded from the main conclusions | excluded | No 30Q OCV data are available (the download needs the author's decision). No endurance claim; C15 and C16 carry the caveat. |
| Hydrodynamic evidence treated explicitly | yes | `dynamics_evidence` reported apart from the electrical grades (C22); `dynamics_policy="strict"` |
| Related work verified | partly | Comparators read in full (Danielis, LOTUSim-Energy, Tun, Lam). Reviewer 1: prior art in the local library not discussed (R1-05) and references missing for headline records (R1-02). |
| Existing-tool comparison complete | yes, as a model comparison | COMPARATOR_MATRIX.md, C27. Tool execution was not possible; reviewer 1 asks for less general wording (R1-04). |
| Custom robot configurability demonstrated | yes | Builder API, 5- and 7-actuator robots, user evidence (C21); 363 tests |
| Paper-critical outputs reproducible | partly | Offline chain byte-identical (reviewers 3 and 6); clean provenance stamps. The patched HoloOcean binary and the 100 Hz traces are not deposited (archive ready, upload is the author's decision). |
| Hostile reviewer has no fatal finding fixable in software/evidence | partly | R5-01 (no measurement) needs data. R5-02 and R5-03 were addressed in software after the review and need a re-review. |

## Remaining before READY WITH LIMITATIONS

1. Related work (R1-05): read and position De Carolis 2018, Potokar 2024 (JOE), the HoloOcean 2.0
   preview, the ICAR 2025 survey and parameter-pedigree schemes. Add the missing references (R1-02)
   and the Oculus and Ping360 records to the audit (R1-03).
2. Re-review the decision case with the grade and dynamics policies (reviewers 3 and 5). Add a
   headroom column for each leg target (R3, minor).
3. Optional: a per-rail converter model (R3-02), so that 5 V loads and pack-voltage loads can carry
   different efficiencies.
4. Author decisions:
   - deposit the trace archive (`tools/make_trace_archive.py`);
   - download the 30Q OCV dataset;
   - obtain a measured mission-energy dataset (OpenEI MHKDR 646, 18 GB of ROS bags, battery topics
     unverified);
   - the upstream HoloOcean issue;
   - the merge to `main`.

---

## Previous sign-off (hardening phase, 2026-11-13)

**Verdict: NOT READY for submission.** Drafting the manuscript may start, restricted to
`docs/paper/CLAIM_EVIDENCE_MATRIX.md`.

The verdict is not forced towards READY. The software, its verification and the provenance layer
meet the bar. The paper does not yet: one critical finding cannot be resolved without hardware, and
several required deliverables are missing.

## Gate

| Gate item | State | Evidence |
| --- | --- | --- |
| Final results from a clean commit | met | Native runs from 81b91ea, cross-layer from b73ae9f, all `dirty: false` |
| Independent recomputation of every energy | met | `energy_verification.json`: 36/36, ≤ 2.5e-13 |
| Backend check discriminates patched from unpatched | met | EXP1 PASS / FAIL (×0.0100) |
| Seeds for stochastic experiments | met | 20 seeds, Wilson intervals |
| Parameter audit and traceability | met | 54 records, grades capped by relation |
| Review findings reproduced and resolved or declared | partly | 167 findings (`REVIEW_CONSOLIDATION.md`). The critical and major findings that affect the final numbers are resolved or turned into stated conditions. Many minor findings remain open. |
| External validation against a physical vehicle | **not met** | No measured BlueROV2 mission energy exists in the evidence (G-01, critical). It cannot be resolved by software. |
| Hydrodynamics behind the dominant energy term | **not met** | Propulsion follows HoloOcean drag. Published BlueROV2 resistance changes it to 0.11–0.22× or 0.87–1.29× (G-03, EXP10 part 1). Every absolute energy is simulator-conditional. |
| Figures and tables regenerated from the final results, with a manifest | met | `docs/figures/final/` FF1–FF6 with plotted CSVs and `manifest.json` (input SHA256, result commits). `final_runs.csv` and `docs/paper/tables/` hold the tables |
| Related work verified (G's prior-art list) | partly | `docs/paper/RELATED_WORK_VERIFICATION.md`. Read at the source: S1, S3 (abstract only), S4, S6, S7, S8 (abstract only; 2021, not 2022), S13 (Blattnig et al. 2008, not NASA-STD-7009 itself), S16. S12 and S14 must not be cited as described; S2 and S11 need their records checked. No source found grades parameter provenance. |
| README with three usage modes; structured API scientific warnings (brief §50–51) | met | README "Usage modes"; `evidence["scientific_warnings"]` (unknown, grade D, proxy, upper-bound only; non-blocking; test `test_scientific_warnings_are_structured_and_non_blocking`) |
| Hostile and methods reviews of the manuscript (Reviewers I, J) | done; not passed | **Reviewer I** (SIMPAT): reject in present form; 3 fatal, 11 major, 6 minor. About 25 numbers spot-checked, no mismatch. **Reviewer J** (methods): partly reproducible; 6 major, 7 minor. Offline outputs and figures are byte-identical on rerun. |
| Reviewer I/J findings fixed in the text | partly | Fixed: I-05 (terminal vs propulsion energy), I-06 (ranking 3 of 6), I-03, I-04, I-07 wording; J-01 (steady values now the 30 s window mean, with a drift column), J-02 (cross-layer provenance disclosed), J-08, J-09, J-12 (figure CLI), J-04 to J-07 (rerun procedure documented). Open: I-01 (no measurement), I-02 (show that grading changes a decision), I-03 (graded coverage excludes hydrodynamics), I-08/G-16 (V&V framing), I-12/G-11 (T200 grade), J-05 to J-07 (patched build and 100 Hz traces not public). |

## What can be claimed now

A provenance-aware energy layer for HoloOcean with:
- traceable component models and automatic grade capping;
- an accounting closed to machine precision;
- a backend check that detects the HoloOcean drag-units defect;
- a set of simulator-conditional case studies (C5–C20).

The defensible contribution is **methodology and verification**: making the evidence level and the
unsupported assumptions of a mission energy estimate visible. It is not a validated BlueROV2 energy
model.

## What must not be claimed

Everything in the "Claims removed or rewritten" table of the claim matrix. Also:
- any accuracy figure for mission energy;
- any endurance figure;
- any statement that layout or orientation results transfer to a physical vehicle.

## Required before submission

1. Read S3 (LOTUSim-Energy) and S8 (Danielis et al. 2021) in full; check the S2 and S11 records.
   Rewrite the related work around DESERT's existing TX/RX counters.
2. Resolve the two open judgements in `REVIEW_CONSOLIDATION.md` section 4: G-11 (T200 grade in
   inflow) and G-16 (journal framing). Every other blocking finding there is resolved, withdrawn or
   deferred with a stated limitation.
3. Revise `paper/manuscript.md` against Reviewer I's fatal findings. The most actionable is I-02: a
   case in which the evidence report changes a design or mission decision, or shows that it does
   not. Add a formal V&V framing (I-08) and a comparison with an existing tool's energy output on the
   same mission.
4. Publish the 100 Hz traces and a recipe for the patched build, or state why they cannot be
   published (J-05 to J-07). This needs the author's decision.
5. Optional, pending the user's approval to download:
   - the 30Q OCV dataset, to replace the grade D OCV curve (C-02);
   - Lam et al. 2023, for T200 data at advance speed (A-02).
