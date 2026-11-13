# Final sign-off (hardening phase, 2026-11-13)

**Verdict: NOT READY for submission.** Drafting the manuscript may start, restricted to
`docs/paper/CLAIM_EVIDENCE_MATRIX.md`.

The verdict is not forced towards READY. The software, its verification and the provenance layer
meet the bar. The paper does not yet: one critical finding cannot be resolved without hardware, and
several required deliverables are missing.

## Gate

| Gate item | State | Evidence |
| --- | --- | --- |
| Final results from a clean commit | met | Native runs from 81b91ea, cross-layer from b73ae9f, all `dirty: false` |
| Independent recomputation of every energy | met | `energy_verification.json`: 36/36, ≤ 1.9e-13 |
| Backend check discriminates patched from unpatched | met | EXP1 PASS / FAIL (×0.0100) |
| Seeds for stochastic experiments | met | 20 seeds, Wilson intervals |
| Parameter audit and traceability | met | 54 records, grades capped by relation |
| Review findings reproduced and resolved or declared | partly | 167 findings (`REVIEW_CONSOLIDATION.md`). The critical and major findings that affect the final numbers are resolved or turned into stated conditions. Many minor findings remain open. |
| External validation against a physical vehicle | **not met** | No measured BlueROV2 mission energy exists in the evidence (G-01, critical). It cannot be resolved by software. |
| Hydrodynamics behind the dominant energy term | **not met** | Propulsion follows HoloOcean drag. Published BlueROV2 resistance changes it to 0.11–0.22× or 0.87–1.29× (G-03, EXP10 part 1). Every absolute energy is simulator-conditional. |
| Figures and tables regenerated from the final results, with a manifest | met | `docs/figures/final/` FF1–FF6 with plotted CSVs and `manifest.json` (input SHA256, result commits). `final_runs.csv` and `docs/paper/tables/` hold the tables |
| Related work verified (G's prior-art list) | partly | `docs/paper/RELATED_WORK_VERIFICATION.md`. Read at the source: S1, S3 (abstract only), S4, S6, S7, S8 (abstract only; 2021, not 2022), S13 (Blattnig et al. 2008, not NASA-STD-7009 itself), S16. S12 and S14 must not be cited as described; S2 and S11 need their records checked. No source found grades parameter provenance. |
| README with three usage modes; structured API scientific warnings (brief §50–51) | met | README "Usage modes"; `evidence["scientific_warnings"]` (unknown, grade D, proxy, upper-bound only; non-blocking; test `test_scientific_warnings_are_structured_and_non_blocking`) |
| Hostile and methods reviews of the manuscript (Reviewers I, J) | **not met** | Require a draft |

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
3. Draft under `paper/` following the claim matrix. Then run Reviewer I (SIMPAT rejection
   perspective) and Reviewer J (methods reproducibility).
4. Optional, pending the user's approval to download:
   - the 30Q OCV dataset, to replace the grade D OCV curve (C-02);
   - Lam et al. 2023, for T200 data at advance speed (A-02).
