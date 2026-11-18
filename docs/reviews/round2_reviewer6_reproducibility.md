# Round 2, Reviewer 6: reproducibility

Repository HEAD 9d4d657 (clean tree, branch `feature/provenance-aware-energy-framework`, pushed). Regenerated outputs were written to the session scratchpad `r6/` directory only. No HoloOcean, Docker or DESERT was started.

## Verdict: PARTLY reproducible

The offline analysis chain (native analysis, sensitivity, decision case, tool comparison, energy verification, figures, trace archive contents) reproduces the committed files exactly from the committed summaries and the local 100 Hz traces. The simulation itself (native runs, DESERT matrix, cross-layer) cannot be rerun by a third party today: the patched HoloOcean binary, the DESERT image and the 100 Hz traces are not public, and the cross-layer provenance is mixed. The manuscript is honest about most of this; the findings below are documentation and provenance gaps.

## Regeneration results

| Output | Command (repo root, `uv run --no-sync python`) | Result |
| --- | --- | --- |
| final_runs.json, final_runs.csv | `experiments/analyze_final_experiments.py --output-dir r6/a` | byte-identical (`cmp`); 36 runs, one commit 81b91ea, any_dirty false |
| sensitivity.json | `experiments/run_sensitivity.py --output r6/sensitivity.json` | byte-identical |
| decision_case.json | `experiments/run_decision_case.py --output r6/decision_case.json` | byte-identical; the 36 full traces are present in `logs/final/full` (git-ignored) |
| tool_comparison.json | `experiments/run_tool_comparison.py --output r6/tool_comparison.json` | byte-identical |
| energy_verification.json | `experiments/verify_final_energy.py --output r6/energy_verification.json` | byte-identical; PASS 36/36, worst 1.8e-13 |
| docs/figures/final | `make_final_figures.py --output-dir r6/figs` (matplotlib 3.9.4 venv) | all 24 png/svg/pdf/csv files byte-identical; `manifest.json` differs (R6-02) |
| trace archive | `tools/make_trace_archive.py --output r6/traces.zip` | 38 members, member contents identical to `dist/holoenergy_final_traces.zip`; zip bytes differ (sha256 277b54ca... vs 03fd...), see R6-05. MANIFEST: 36 gzip SHA256 match the files, every hash and commit matches its summary, all commit 81b91ea, dirty false |
| 100 Hz traces | uncompressed SHA256 of each `logs/final/full/*.gz` against `summary.traces.full_per_tick.content_sha256` | 36/36 match |

## Provenance of result files

| File | Commit / dirty |
| --- | --- |
| native/*/summary.json (36) | 81b91ea, clean |
| comm_matrix.json | 81b91ea, clean |
| crosslayer.json | top level b73ae9f clean; per-strategy reports: none b73ae9f clean, direct b73ae9f dirty, ack 275e226 dirty, multihop/flooding/optical/relay-vehicle/relay-fixed 5d9e102 dirty |
| sensitivity.json, decision_case.json, tool_comparison.json, energy_verification.json | none recorded |
| docs/figures/final/manifest.json | code_commit 6155c65, stale (R6-02) |

## Hand-recomputed manuscript numbers (from committed `final_runs.json` and `crosslayer.json`)

All agree with the text.

1. L8-HV 0.5 m/s head-on: terminal 6.5295 Wh, propulsion 6.3858 Wh, steady 249.2 W, last 10 s 1.34 % lower (Section 9.2).
2. L4-2H2V vs L8-HV: 5.5988/6.5295 = -14.3 %, propulsion -14.6 %; L8-VEC30 8.0398 Wh = +23.1 %, propulsion +23.7 %.
3. Transit 0.647 / 1.763 / 5.220 Wh, tracking 0.025 / 0.000 / 0.236 m, damping 21 / 12 / 5 % (9.3).
4. L1 vs L0 propulsion 1.6396/1.5710 = +4.4 %; battery loss 0.0201 Wh; low-SOC 125.1 W and 101.7 W, derating 0.313 (9.4).
5. Payload scheduling: inspection 3.146 to 2.116 Wh = -32.7 % (text 33 %); AI 2.036 to 1.823 Wh = -10.5 % (text 10 %) (9.5).
6. Modem share, direct strategy: 1.4532 % of 1.7885 Wh (text 1.45 %) (9.6). Angle trade-off 4.81/13.18, 6.53/7.78, 10.92/5.70 Wh match. L8-HV at 0.8 m/s: allocation saturation 92.7 %, error 12.1 m.

## Findings

| ID | Severity | What | Command and result | Required change |
| --- | --- | --- | --- | --- |
| R6-01 | Medium | `crosslayer.json` provenance is mixed: the top-level `git` says b73ae9f clean, but 7 of 8 per-strategy EnergyReports record a dirty tree and three different commits. Disclosed in the results README and manuscript Section 8, but the file cannot be tied to one commit mechanically and cannot be repeated offline (needs DESERT). | Python read of `results.*.energy_report.provenance.git` | Rerun the cross-layer experiment from one clean commit with nothing committed meanwhile (preferred), or add a `provenance_note` field and keep the disclosure. State that this result is not bit-reproducible offline. |
| R6-02 | Medium | The committed figure `manifest.json` is stale: it records `sensitivity.json` SHA256 84b07815... but the committed file hashes to 85659aa3...; `code_commit` is 6155c65, not the commit of the committed code. Figure bytes are identical. | `diff docs/figures/final/manifest.json r6/figs/manifest.json`: 2 lines | Regenerate the manifest at the release commit after the last change to `sensitivity.json`; add a check that manifest hashes equal the committed inputs. |
| R6-03 | Medium | The "Reproducing the final runs" procedure is incomplete. It omits `run_decision_case.py`, `run_tool_comparison.py` and `tools/make_trace_archive.py`, though the manuscript uses decision_case and tool_comparison results. It does not say that `run_final_experiments.py` writes to `logs/final/results` while `analyze_final_experiments.py` reads `experiments/results/final/native` (identical now; the copy step is undocumented), and gives no dependency order (decision_case needs final_runs, sensitivity, crosslayer and the full traces). `results/final/README.md` lists sensitivity as "parts 1-4" (part 5 exists) and omits decision_case.json and tool_comparison.json. | `grep decision_case docs/paper/FINAL_EXPERIMENTS.md`: no match; `diff -rq logs/final/results experiments/results/final/native`: empty | Add the three commands, the copy or `--output-dir` step, an ordered list and an expected-output table (file, producer, byte-identical or not). Update the results README. |
| R6-04 | Medium | `sensitivity.json`, `decision_case.json`, `tool_comparison.json` and `energy_verification.json` carry no commit, dirty flag or input hashes. They reproduce at HEAD 9d4d657 (verified here), but a reader cannot tell which commit produced them. | key listing of each file | Add `git.commit`, `dirty` and SHA256 of each input to these outputs. |
| R6-05 | Medium | The 100 Hz traces (74 MB) and the archive are not public: `logs/` and `dist/` are git-ignored. The archive zip is not byte-deterministic (members identical, container differs, presumably entry timestamps), so quoting the zip SHA256 is fragile. | sha256 03fd... (committed dist) vs 277b... (regenerated); 0 of 38 members differ | Deposit the archive (release asset or Zenodo) and cite the DOI. Fix `ZipInfo.date_time` or use the per-file hashes in MANIFEST as the integrity reference. Keep the manuscript sentence "not yet deposited" until done. |
| R6-06 | Medium | The simulation backend cannot be rebuilt from the repository alone. The patched HoloOcean package is local (`C:/HOB`); the cooked Ocean worlds are not public, so the procedure needs the official installed package plus an Unreal Engine 5.3.2 source build (Epic account). The DESERT image (`holo-desert-engine:4.0.0-v2`) and `holo_desert` 1.1.0 at 635b99a come from a separate repository (HoloWithDesertCommunications) that is not in this history and has no URL in the docs. The manuscript availability paragraph does not mention DESERT or `holo_desert`. | `git cat-file -t 635b99a`: fatal; `environment.json` | In the availability section and rerun procedure, name the second repository (URL, commit or tag), say whether the image is distributed or how to build it, and state that EXP3-EXP8 need these external pieces and that only the analysis layer is rerunnable without them. |
| R6-07 | Low | Summaries embed absolute local paths (`F:\Andrea\HoloVirtualBattery\logs\final\full\...` in `traces.full_per_tick.path`; `C:/HOB/...` in `environment.json`). | read of a summary | Store repository-relative paths or drop them; the SHA256 identifies the file. |
| R6-08 | Low | The manuscript Data and code availability section is accurate on every checkable point (branch exists and is pushed; commits 81b91ea and b73ae9f exist; trace SHA256 in summaries; downsampled traces committed; archive prepared, not deposited; patch, build procedure, hashes and backend check exist under `patches/`, `docs/holoocean_patched_build.md`, `sources/verified_backend/build_provenance`). It is incomplete rather than wrong: no tag or DOI, no licence, no statement that the analysis was rerun at a later commit (9d4d657) with identical bytes, no interpreter and lock-file statement (runs used Python 3.10 in the HoloWithDesertCommunications venv; `uv.lock` governs offline reanalysis). | read of manuscript lines 932-940; `environment.json` | Add a release tag and DOI, the licence, the interpreter and lock-file statement, and one sentence on which outputs are byte-reproducible offline (this review: five JSON/CSV files, 24 figure files, 36 energy checks, archive contents). |
| R6-09 | Info | Figure bytes depend on matplotlib; they matched with matplotlib 3.9.4 from the run venv. `FINAL_EXPERIMENTS.md` and `environment.json` already say so; the default repo environment may not provide it. | `make_final_figures.py` with the HoloWithDesertCommunications venv | Pin matplotlib 3.9.4 in an optional extra or note it in the README. |
