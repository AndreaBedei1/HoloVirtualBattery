# Scientific hardening phase: status (2026-11-13)

This file tracks the hardening phase after v0.2.0 (tag on bd11c98). The reviewer reports A–H and
the evidence search are in `docs/reviews/`. `docs/RESEARCH_STATUS.md` predates the reviews: its
claims RQ1–RQ6 still have to be revised against them (see "Claims to correct").

## Done (commits 050a61f … 81b91ea on `feature/provenance-aware-energy-framework`)

- Eight independent reviews: A literature, B physics, C battery, D components, E numerical, F experiment
  design, G hostile SIMPAT, H reproducibility. Plus a focused evidence search.
- Fixed with regression tests:
  - C-01/E-05: voltage latch only when OCV ≤ cutoff.
  - C-03, C-04: stale resistance links; voltage dependence.
  - E-01/02/03: intervals.
  - E-06: virtual layouts limited to the native wrench.
  - E-08, E-09 (`power_irls` in the env), E-25.
  - B-02: allocation at the voltage under rated current.
  - D-05/06/07/10.
  - A-01 (T200 status DATASHEET), A-03 (battery-loss link proxy; audit prints the stricter relation),
    A-04 (Gemini 19–74 V supply; converter declared as an unconfigured gap).
  - B-03: the damping form is $v(1-c\,\Delta t)$.
- Evidence added:
  - 6T vertical spacing 221.0 mm (A);
  - 4S 18Ah cell identity (B);
  - LUMA 250 kbit/s;
  - S2C M Ethernet +0.5 W.
- Machine-readable parameter audit: `data/evidence/final_parameter_audit.*` (54 records).
- Paper tables: `docs/paper/tables/`.
- `docs/paper/MODEL_EQUATIONS.md`.
- Final design fixed before the runs: `docs/paper/FINAL_EXPERIMENTS.md`.
- Runners refuse dirty trees. The comm matrix runs 20 seeds with a Wilson interval.
- 328 tests passed locally; CI green on 7c20915.

## Offline sensitivity results (EXP10; `experiments/run_sensitivity.py`)

These were checked on the pre-hardening cross-layer durations and must be regenerated from the final
cross-layer run.

| Part | Result |
| --- | --- |
| 1, drag model | Propulsion power relative to HoloOcean drag: Gabl et al. 2021 gives 0.11–0.22×; von Benzon et al. 2022 gives 0.87–1.29× (beyond 0.72 m/s it is flagged as extrapolated). |
| 2, acoustic share | 1.37 % as simulated (2.8 W TX, RS-232, DESERT 4.8 kbit/s). 2.6 / 8.3 / 12.1 % at 8 / 35 / 55 W. 1.07–5.6 % at the device bitrate. Ethernet adds 0.5–0.6 points. "At most 1.37 %" is therefore not supported. |
| 3, allocator | Pseudoinverse, redistributed and power-IRLS agree within 0.13 % on all final layouts in steady currents. IRLS is not better on L8-VEC30 (+0.13 % head-on). |
| 4, drag anisotropy (von Benzon vs isotropic) | The ranking of layouts within each current direction is unchanged in 5 of 8 cases. The changes are a load crossover at 0.2 m/s head-on (L4-2H2V) and the ordering of the angle variants under oblique current. The sway/head-on cost ratio changes strongly (L8-HV at 0.5 m/s: 1.20 → 1.77; a30: 2.82 → 4.30). Orientation conclusions are conditional on the drag law. |

## Final runs (from clean commit 81b91ea; results committed in b73ae9f and 65a06da)

- **EXP1.** Patched build PASS: drag 1.000000, step ratio 1.000000. Unpatched control build FAIL:
  drag ×0.0100.
- **Native matrix.** 36 runs, all with chain closure PASS. The independent energy recomputation
  agrees to ≤ 1.9e-13 relative.
- **Analysis.** `experiments/results/final/final_runs.{json,csv}`: whole-run and steady-window
  feasibility, tracking, Unreal damping share.
- **Comm matrix.** 9 configurations × 20 seeds. 8 of the 9 are identical across seeds. B2 delivers
  61/200 (Wilson 95 % interval 0.245–0.372).
- **Cross-layer.** 8 strategies, running into `experiments/results/final/crosslayer.json`.

## Next steps

1. `run_sensitivity.py` (final cross-layer). Report the Unreal damping share of every transit from the
   traces: $m c v$ versus $\tfrac12\rho C_D A|v_r|v_r$ (B-07).
4. Copy summaries and 0.1 s traces to `experiments/results/final/`. Regenerate figures and tables with
   manifests.
5. Write `docs/reviews/REVIEW_CONSOLIDATION.md`, `docs/paper/CLAIM_EVIDENCE_MATRIX.md`, threats to
   validity, the related-work correction (DESERT already counts TX/RX energy, G-04) and
   `docs/reviews/FINAL_SIGNOFF.md`.
6. Manuscript draft under `paper/`, only if the sign-off allows it. Then Reviewers I and J.

## Claims to correct (from the reviews)

- RQ1: the baselines are a model-versus-model comparison, not validation. The −15 to +13 % spread
  comes from the current direction (forward or reverse branch) and from Unreal damping, not from
  drag isotropy (B-06).
- Equal layout energies and zero still-water propulsion are properties of the decoupled, neutrally
  buoyant body (B-03).
- "Acoustic modem adds at most 1.37 %" is wrong: the figure is a conditional point estimate (EXP10
  part 2).
- Transit energies include Unreal ground-referenced damping, which is 19–79 % of the resistance
  depending on the phase (B-07).
- Related work: DESERT `uwphysical` already tracks TX/RX energy (G-04). The HoloOcean drag defect
  is still present in v2.4.0.

## Pending user approvals

- Downloads:
  - 30Q OCV dataset (Mendeley doi 10.17632/g7ncmhrcrz.2);
  - BlueROV2 R4 CAD (376 MB);
  - Lam et al. 2023, doi 10.1109/oceanslimerick52467.2023.10244513 (institutional access).
- Merge to `main`, and the upstream HoloOcean issue: not authorised; not done.
