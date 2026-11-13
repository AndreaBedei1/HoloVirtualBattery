# Reviewer J: methods reproducibility of `paper/manuscript.md`

Repository HEAD 6155c65, branch `feature/provenance-aware-energy-framework`. Nothing in the repository was edited or committed. No simulator, container or DESERT engine was started. Regenerated outputs are in `C:\Users\ANDREA~2.BED\AppData\Local\Temp\claude\945244cbcba3dc8b\50891df7-d4df-47f1-ad45-e3fefca5e7b6\scratchpad\reviewerJ\`.

## Verdict: partly reproducible

- Everything computable offline from the committed files reproduces exactly: `final_runs.json`, `final_runs.csv`, `sensitivity.json` and `energy_verification.json` are byte-identical on regeneration, and the six figures are byte-identical across runs with matplotlib 3.9.4.
- The native HoloOcean and DESERT runs cannot be rerun by a third party from the documents as they stand (J-04 to J-06).
- The steady-power numbers in the manuscript do not use the window the manuscript states (J-01).

## Findings

| ID | Severity | What | Evidence | Required change |
| --- | --- | --- | --- | --- |
| J-01 | major | The steady propulsion powers (245.9 W, 13.4 W, 608.9 W, 101.7 W) are means over the last 10 s, not the "last 30 s" window stated in Sec. 6 and in FINAL_EXPERIMENTS.md. | The 100 Hz trace of EXP3-L8-HV-headon0.5 gives 249.250 W for the last 3000 ticks (equal to `metrics.steady_mean_propulsion_W`) and 245.905 W for the last 1000 ticks (equal to `metrics.mean_tail_propulsion_W`, defined in `run_native_campaign.py:403` as `10.0/DT`). `analyze_final_experiments.py:129` copies `mean_tail_propulsion_W` into `steady_propulsion_W`. For EXP8-lowsoc the two windows give 125.09 W and 101.66 W, a 23 % difference (the 0.313 derating case, C16). The 0.11 to 1.29 ratios in `sensitivity.json` also depend on the window. | Either state "last 10 s" everywhere (Sec. 6, 7.1, 7.2, 7.5, C5, C12, C16) or switch the analysis to `steady_mean_propulsion_W` and regenerate the numbers, the figures and `sensitivity.json`. Report both windows for the low-SOC run. |
| J-02 | major | The mixed-commit provenance of the cross-layer results is not disclosed. | Top-level `git` is b73ae9f (clean). Per strategy: `none` b73ae9f clean; `direct` b73ae9f with untracked files; `ack` 275e226; `multihop`, `flooding`, `optical`, `relay-vehicle`, `relay-fixed` 5d9e102, all marked `dirty: true` (status `?? experiments/results/final/crosslayer.json` only, i.e. the output file). README and the manuscript say only "one clean commit" for the native runs. The `refuse dirty trees` guard evidently ignores untracked files. | Add to the README and Sec. 6 a statement that the cross-layer strategies ran on three commits that differ only in documentation and style (see Provenance below). Make the guard reject untracked files outside the output directory, or state that it does not. |
| J-03 | minor | The code at HEAD is not the code that produced the results. | `git diff --stat 81b91ea HEAD` shows changes to `holoenergy/evidence/runtime.py` (+65, structured warnings, f8307a4), `tests/test_review_regressions.py`, `README.md` and the new `analyze_final_experiments.py` and `make_final_figures.py`. Commits 81b91ea to 5d9e102 differ in code only by `analyze_final_experiments.py`. The evidence summaries in the committed runs predate the warning change. | State the result commit (81b91ea) and the tag of the code that matches the reported results. Check that `runtime.py` does not change any energy or share value, or rerun. |
| J-04 | major | `docs/native_runs.md` describes the earlier campaign, not the final one. | It points to `experiments/results/native`, `run_native_campaign.py`, `analyze_native_campaign.py` and `make_paper_figures.py`. It never mentions `run_final_experiments.py`, its flags (`--binary`, `--source-dir`, `--output-dir`, `--runs`), the `logs/final` layout, or `run_crosslayer.py --binary $after --port 5571` with its extra arguments. No document gives the command sequence for EXP1 to EXP10. The `--runs` group names are not listed. | Add a "Final runs" section with the exact commands in order: EXP1 backend check, `run_final_experiments.py`, comm matrix, cross-layer, `analyze_final_experiments.py`, `verify_final_energy.py`, `run_sensitivity.py`, `make_final_figures.py`. |
| J-05 | major | The simulator build cannot be recreated from the documents. | Commands use `C:/HOB/packages/patched-after` and `C:/HOB/src/after`, which exist only on this machine. `holoocean_patched_build.md` is referenced, but `environment.json` records only "sha256 recorded per run". The patch SHA256 (`00f1b303…`), HoloOcean commit (`49e70552`) and toolchain appear only inside the per-run provenance and are truncated in `native_runs.md`. The patch file is not named in the final README. The Unreal engine and package source are not obtainable without a licence and build. | List in `environment.json` the HoloOcean commit, the full patch SHA256 and file path, the toolchain, the package SHA256 and the build command. State which parts are not redistributable. |
| J-06 | major | The DESERT engine cannot be recreated by a third party. | The image `holo-desert-engine:4.0.0-v2` (id `sha256:dce313c4…`) is built from `uwsignet/desert:4.0.0` through the sibling repository `F:/Andrea/HoloWithDesertCommunications` (editable install at 635b99a, outside this repository). The `docker run` line, port 5571 and the fingerprint `755d96a2c67be143` appear only in `native_runs.md`. `environment.json` has the image id but no build recipe and no fingerprint. | Cite the repository URL and commit of `holo_desert`, the build command, the base image digest, and put the fingerprint in `environment.json`. |
| J-07 | major | The 100 Hz traces are not available, so the headline verification (1.9e-13 over 36 runs) cannot be repeated by a third party. | `logs/final` is git-ignored (`git check-ignore logs/final/full` returns the path); `README.md` says rerunning "regenerates them", which needs J-04 to J-06. The summaries store an absolute local path `F:\Andrea\...\logs\final\full\...` and the SHA256 of the uncompressed content. The manuscript lists "0.1 s traces" in the data statement without mentioning that the 100 Hz ones are absent. On this machine `verify_final_energy.py` passed (see below). | Archive the 74 MB of traces (Zenodo or release asset) with the SHA256 list, or state in the data statement that the verification needs a rerun. Store relative paths in the summaries. |
| J-08 | minor | Sec. 7.6 gives "0.96 % to 13.2 % over published device settings", but the lower value is a different strategy. | In `sensitivity.json` part 2 the minimum row is `relay-fixed` (the vehicle only listens; 0.0171 Wh), 2.8 W, RS-232, DESERT airtime. The maximum is `direct` with the 55 W maximum setting and Ethernet. The direct-link, as-simulated value is 1.45 %. The range therefore mixes strategy and device setting. | Give the range for the direct link only (about 1.45 % up to 13.2 %) or label the 0.96 % as the fixed-relay case in the abstract and in Sec. 7.6. |
| J-09 | minor | "Nothing in those scenarios is stochastic" (comm matrix) is not exact. | In `comm_matrix.json`, all nine configurations show 20 different mean latencies over the 20 seeds. Delivery and energy are constant in eight configurations; B2 has 4 distinct delivered counts. | Write "delivery and communication energy do not depend on the seed in eight configurations; latency does". |
| J-10 | minor | matplotlib is not a declared dependency and the figure bytes depend on its version. | `grep matplotlib pyproject.toml uv.lock` returns nothing. `environment.json` and `environment_freeze.txt` give 3.9.4. The figures regenerated with matplotlib 3.10.8 (Python 3.14, default `python`) differ in all PDF, PNG and SVG files. | Add an optional `figures` extra pinned to 3.9.4, or state the version in `make_final_figures.py` and in the README. |
| J-11 | minor | `make_final_figures.py` has no command-line interface: `--help` is ignored and the script overwrites `docs/figures/final`. | Running it with `--help` rewrote 19 tracked files (my mistake, restored with `git checkout -- docs/figures/final`; `git status` shows no change to tracked files). `manifest.json` also changes with every commit because it stores `code_commit`. | Add argparse with `--output-dir`; keep `code_commit` out of the byte comparison or document the difference. |
| J-12 | minor | Seeds and defaults are not recorded in the documents. | `run_comm_matrix.py` defaults (`--messages 10`, `--interval-s 5`, `--drain-s 20`, `--seeds`) and `run_crosslayer.py` defaults (0.2 m/s, 2 s period, 32 B) are visible only in the code; FINAL_EXPERIMENTS.md says "seeds 1..20" and gives no commands with flags. | Give the exact command lines used for `comm_matrix.json` and `crosslayer.json` (the `traffic` block records the values, so they can be copied from there). |
| J-13 | minor | The method description in Data availability says "0.1 s traces" and the text elsewhere says "100 Hz traces". | `traces.downsampled_0.1s` is committed (`*.trace10.jsonl.gz`, 10 Hz); `traces.full_per_tick` is 100 Hz. The 0.1 s traces give 249.24 W for the last 30 s, close to but not equal to the 100 Hz value. | State which trace each number uses. |

## Provenance check

| Item | Commit | Dirty flag |
| --- | --- | --- |
| 36 native summaries, `provenance.git` | 81b91ea (all 36 identical) | false (36 of 36) |
| 5 native summaries, `energy_report.provenance.git` | 81b91ea | true, status `?? experiments/results/final/` only (EXP3 sway0.5 of 2H2V and HV, EXP3 headon0.8, EXP3 oblique0.5 VEC30, EXP8 lowsoc). The untracked output directory only. |
| `final_runs.csv` | 81b91ea | false |
| `comm_matrix.json` | 81b91ea | false |
| `crosslayer.json` | b73ae9f at top level; b73ae9f, 275e226 and 5d9e102 per strategy | strategies other than `none` flagged dirty (untracked output or script) |

`git diff --stat` between the commits, code paths only (`holoenergy`, `experiments/*.py`, `tests`, `pyproject.toml`, `uv.lock`):
- 81b91ea to b73ae9f: empty.
- 81b91ea to 275e226 and to 5d9e102: only `experiments/analyze_final_experiments.py` (+202), an analysis script that does not produce the runs.
- 275e226 to 5d9e102: empty.
- 81b91ea to HEAD 6155c65: also `holoenergy/evidence/runtime.py` (+65), `tests/test_review_regressions.py` (+18), `README.md`, `experiments/make_final_figures.py`.

The runs therefore come from effectively the same code. Commit 81b91ea is an ancestor of b73ae9f.

## Offline reruns

| Script | Command | Result |
| --- | --- | --- |
| `analyze_final_experiments.py` | `uv run --no-sync python experiments/analyze_final_experiments.py --output-dir <tmp>` | `final_runs.json` and `final_runs.csv` byte-identical (`cmp`). |
| `run_sensitivity.py` | `... run_sensitivity.py --crosslayer experiments/results/final/crosslayer.json --output <tmp>/sensitivity.json` | byte-identical. |
| `verify_final_energy.py` | `... --output <tmp>/energy_verification.json` (default `--final-dir logs/final`, 36 traces present locally) | 36 PASS, worst relative error about 1.9e-13, output byte-identical to the committed file. |
| `make_final_figures.py` | no CLI. Copy of the script with `OUT` and `ROOT` replaced, run twice with the matplotlib 3.9.4 interpreter (`HoloWithDesertCommunications/.venv`) | 24 of 25 files byte-identical to the committed figures, and both runs identical to each other. Only `manifest.json` differs (`code_commit`). With matplotlib 3.10.8 every PDF, PNG and SVG differs (J-10). |

## Numbers reproduced by hand

| Manuscript number | Source | My value | Match |
| --- | --- | --- | --- |
| 0.4897 Wh (0.2 m/s) and 6.5295 Wh (0.5 m/s), L8-HV, L6-STD and L4-H45 | summaries | 0.48966; 6.52954 for the three layouts (L6 and H45 equal to 1e-10) | yes |
| L4-2H2V 14 % less, 5.5988 Wh; L8-VEC30 23 % more, 8.0398 Wh | summaries | -14.25 %, 5.59877 Wh; +23.13 %, 8.03978 Wh | yes |
| Steady propulsion 245.9 W at 0.5 m/s | 100 Hz trace | 245.905 W (last 10 s); 249.250 W (last 30 s) | only for 10 s (J-01) |
| 13.4 W and 608.9 W; 101.7 W | `mean_tail_propulsion_W` | 13.42 W (30 s: 13.42); 608.88 W (30 s: 610.18); 101.66 W (30 s: 125.09) | 10 s window only |
| 0.1438 Wh still water | EXP5-station-c0 | 0.14375 Wh | yes |
| Transit 0.647, 1.763, 5.220 Wh | EXP5 | 0.6469, 1.7626, 5.2196 | yes |
| Payload saving 33 % (3.146 to 2.116 Wh); 10 % (2.036 to 1.823 Wh) | EXP6 | 32.74 % (3.14638 to 2.11636); 10.46 % (2.03584 to 1.82294) | yes |
| L1 is 4.4 % above L0 (1.6396 against 1.5710 Wh); L1 battery loss 0.0201 Wh | EXP5 and EXP8 | +4.37 % (1.63962 against 1.57101); 0.02005 Wh | yes |
| Acoustic share 1.45 % | `crosslayer.json` direct | 0.025990 Wh / 1.78851 Wh = 1.4532 % | yes |
| Vehicle energy 0.0171 (fixed relay), 0.0253 (forward), 0.0260 (direct) Wh; optical 0.0111 Wh | `crosslayer.json` | 0.01711; 0.02531; 0.02599; 0.01108 | yes |
| B2 delivery 61/200, Wilson 0.245 to 0.372 | `comm_matrix.json` and formula | 61/200; my Wilson interval 0.24536 to 0.37199 | yes |
| 36 runs | file count | 36 summaries | yes |
| 0.96 % to 13.2 % | `sensitivity.json` part 2 | 0.9615 % to 13.216 % | numerically yes; interpretation J-08 |

## What a third party can and cannot do

Can: install with `uv sync --locked`, regenerate the analysis, sensitivity and (with a pinned matplotlib) the figures from the committed summaries. Verify the energy with the traces only if they obtain them from the authors.

Cannot, from the documents alone: build the patched HoloOcean package, build the DESERT engine image, run EXP1 to EXP8, EXP7 (J-04 to J-06). Missing steps: HoloOcean source and patch location, the binary build command, the DESERT image recipe and fingerprint, seeds (comm matrix seeds 1..20 are in the output only), ports (5571 appears in a single document), and the ordered command list for the final campaign.
