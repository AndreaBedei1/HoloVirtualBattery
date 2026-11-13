# Final results (hardening phase)

All native runs come from commit 81b91ea with a clean tree. The comm matrix comes from 81b91ea; the cross-layer run started from commit b73ae9f with a clean tree. Documentation and result files were committed while it ran, so the per-strategy EnergyReports record HEAD at report time (b73ae9f, 275e226, 5d9e102) with a dirty tree; between b73ae9f and 5d9e102 the only code change is the new analysis script, which the run does not use (review J-02). All runs use the drag-patched HoloOcean 2.3.0 build at 100 Hz. The design is in `docs/paper/FINAL_EXPERIMENTS.md`.

| Path | Content | Producer |
| --- | --- | --- |
| `native/EXP*/<label>.summary.json` | per-run summary, configuration SHA256, evidence, EnergyReport, provenance | `experiments/run_final_experiments.py` |
| `native/EXP*/<label>.trace10.jsonl.gz` | 0.1 s trace (every 10th tick) | same |
| `final_runs.{json,csv}` | one row per run: energies, steady state, feasibility, tracking, Unreal damping share | `experiments/analyze_final_experiments.py` |
| `energy_verification.json` | independent recomputation of every energy from the 100 Hz traces (tolerance 1e-9 relative) | `experiments/verify_final_energy.py` |
| `backend/` | EXP1 backend checks: patched build (PASS) and unpatched control build (FAIL, drag ×0.01) | `tools/check_holoocean_backend.py` |
| `comm_matrix.json` | EXP7, 9 configurations × 20 seeds | `experiments/run_comm_matrix.py` |
| `crosslayer.json` | EXP7 cross-layer, 8 strategies | `experiments/run_crosslayer.py` |
| `sensitivity.json` | EXP10 parts 1–4 | `experiments/run_sensitivity.py` |

The 100 Hz traces (74 MB) are not committed. Each summary records their SHA256 (`traces.full_per_tick`),
and rerunning the same commit regenerates them.
