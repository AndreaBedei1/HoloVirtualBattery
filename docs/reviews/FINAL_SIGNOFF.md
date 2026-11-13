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
| Figures and tables regenerated from the final results, with a manifest | **not met** | `make_paper_figures.py` still reads the superseded campaign layout |
| Related work verified (G's prior-art list: Gazebo battery, UUV Simulator, LOTUSim-Energy, Stonefish T200 energy, Danielis 2022, ns-3 modem energy, provenance standards) | **not met** | References not yet read. DESERT's TX/RX energy counters are verified (G-04). |
| README with three usage modes; structured API scientific warnings (brief §50–51) | **not met** | Not done in this phase |
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

1. Regenerate the figures from `experiments/results/final/`, with a figure and table manifest.
2. Read and verify every prior-art reference before citing it. Rewrite the related work around
   DESERT's existing TX/RX counters.
3. Close or explicitly defer the remaining major findings in `REVIEW_CONSOLIDATION.md` section 3a.
4. Write the README modes and the API scientific warnings.
5. Draft under `paper/` following the claim matrix. Then run Reviewer I (SIMPAT rejection
   perspective) and Reviewer J (methods reproducibility).
6. Optional, pending the user's approval to download:
   - the 30Q OCV dataset, to replace the grade D OCV curve (C-02);
   - Lam et al. 2023, for T200 data at advance speed (A-02).
