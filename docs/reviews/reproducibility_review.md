# Reproducibility review (Reviewer H)

Target: tag `v0.2.0` = commit `bd11c982385b8e9163f97ffbd82f5a1926ff3f1f`, branch
`feature/provenance-aware-energy-framework`. Instructions used: `README.md`, `docs/README.md`,
`docs/native_runs.md`, `docs/holoocean_patched_build.md`, `experiments/README.md` and the script
docstrings and `--help`. Date: 2026-11-12.

Method. All non-native items ran in a `git archive v0.2.0` copy (`$S/src`, where
`$S = C:\Users\andrea.bedei3\AppData\Local\Temp\claude\945244cbcba3dc8b\50891df7-d4df-47f1-ad45-e3fefca5e7b6\scratchpad\reviews\H`).
Every output went to `$S`. Comparisons are byte-level (`cmp`) first, then leaf by leaf (JSON) or
cell by cell (CSV). The only repository file I wrote is this one. I did not commit, did not run
Docker, used only the DESERT engine on `127.0.0.1:5571`, and ran at most one HoloOcean process at a
time, from `C:/HOB/packages/patched-after`.

The branch moved during the review. HEAD advanced from `bd11c98` to `1003aab` (3 commits:
`050a61f`, `71d4a66`, `1003aab`). While my first native run was executing, the working tree was
dirty with someone else's edits to `holoenergy/units.py` and
`holoenergy/evidence/data/parameters/hydrodynamics.yaml`. That run silently picked up the edits:
its summary records 179 registry records instead of 177. I discarded it and repeated items 4 and 5
from the archive copy, and every result below comes from the `v0.2.0` code (see H-03).

## Environment

| Use | Interpreter | Key versions |
| --- | --- | --- |
| `uv sync --extra dev --locked`, tests, analysis, offline campaign | CPython 3.12.13 (uv-managed) | numpy 2.5.4, PyYAML 6.0.3, pytest 9.1.1, ruff 0.16.10 |
| Fresh wheel venv | CPython 3.12.13 | holoenergy 0.2.0 (built wheel), numpy 2.5.4, PyYAML 6.0.3 |
| Native and DESERT (`$py`) | `F:/Andrea/HoloWithDesertCommunications/.venv`, Python 3.10.20 | holoocean 2.3.0, holo_desert 1.1.0, numpy 1.26.4, PyYAML 6.0.2; holoenergy imported from the source tree via `sys.path` |
| Figures (only Python here with matplotlib) | system CPython 3.14.2 | matplotlib 3.10.8, numpy 2.4.2, PyYAML 6.0.3 |

Platform: Windows 11 Enterprise 10.0.26200, uv 0.11.28, git `core.autocrlf=true`. Backend:
`patched-after` Holodeck.exe SHA256 `9575fb02…4120`, build manifest SHA256 `219b74d4…234a`.
DESERT engine fingerprint `755d96a2c67be143`, which matches the package value printed by the
`native_runs.md` §3 check.

## Item status

| # | Item | Status |
| --- | --- | --- |
| 1 | Install, build, wheel, CLI | Reproduced |
| 2 | Unit tests | Reproduced: 317 passed in 95 s (full suite); subset 32 passed; ruff clean |
| 3 | HoloOcean backend check, 100 Hz | Reproduced exactly (all 69 numeric and identity leaves identical; only `created_utc` differs) |
| 4 | Native run `N1-L8-HV-direct-c0.2` | Physics and energy reproduced exactly; evidence-grade block **not** reproduced (stale committed values, H-01) |
| 5 | Comm matrix, configs A and B | Reproduced exactly (only wall-clock `observed_wall_time` differs) |
| 6 | 4/6/8 comparison (`N1_layouts.csv`) | Reproduced exactly from committed summaries; with my fresh run substituted, identical except `real_time_factor` |
| 7 | Offline E4 (`E4_external_drag.csv`) | Within tolerance in the locked env (max rel. 4.5e-16); byte-identical with numpy 2.4.2. Offline E2 grade shares not reproduced (H-01) |
| 8 | Paper figures | Reproduced exactly: 43/43 files byte-identical, also after substituting the fresh native run |
| 9 | Paper table (RQ table, `paper_outline_smpat.md`) | All traced numbers match their CSV/JSON except one, which has no results file (H-10); one wording issue (H-11) |

### 1. Installation and package build: reproduced

```text
cd $S/src && uv sync --extra dev --locked          # exit 0, 30 s, CPython 3.12.13 chosen by uv
uv build --out-dir $S/dist                          # exit 0, sdist 12.5 MB + wheel 232 kB
uv venv $S/wheelvenv --python 3.12 && uv pip install --python $S/wheelvenv/Scripts/python.exe $S/dist/holoenergy-0.2.0-py3-none-any.whl
holoenergy profiles | validate bluerov2-heavy | evidence bluerov2-heavy | audit-sensors PoseSensor RGBCamera   # all exit 0, run from $S/cli
python $S/src/tools/check_installed_wheel.py        # "Installed wheel verified"
```

The CLI output matches the README. `validate` reports 8 actuators, rank 6, native clamp 28.75 N,
the 7 placeholder warnings and the 2 unconfigured loads. `audit-sensors` gives PoseSensor 0 W and
RGBCamera `null` with two representative profiles. Two wheel builds from the same tree have
identical members but different zip timestamps (H-14).

### 2. Unit tests: reproduced

`uv run pytest -q` passed 317 tests in 95.1 s with 4 UserWarnings. The subset
`test_communication_energy`, `test_allocation`, `test_evidence_links`, `test_backend_check` and
`test_review_regressions` passed 32 tests in 13 s. `ruff check` and `ruff format --check` on
`holoenergy examples tools tests` passed, and `ruff check experiments` passed too.

### 3. HoloOcean backend check: reproduced exactly

```text
cd $S/src && $py tools/check_holoocean_backend.py --binary C:/HOB/packages/patched-after/Ocean/Windows/Holodeck/Binaries/Win64/Holodeck.exe --source-dir C:/HOB/src/after --ticks-per-sec 100 --output $S/item3/check_patched_after.json
```

The check printed PASS (drag 1.000000 in current and still water, physics/client 1.000000) and
took 18 s. Against `experiments/results/native/backend/check_patched_after.json`, all values are
identical, including current_ratio 1.0000000096573967, still_water_ratio 1.0000002332166544,
physics_to_client_ratio 0.9999999822475638, the inferred forces, and the binary, PDB, config and
manifest hashes. Only `created_utc` differs.

### 4. Native energy run: physics reproduced exactly, evidence block differs

```text
cd $S/src && $py experiments/run_native_campaign.py --binary $after --source-dir C:/HOB/src/after --runs N1-L8-HV-direct-c0.2 --output-dir $S/item4/native --full-trace-dir $S/item4/full
#  PASS force 8.0e-06 N, equiv 6.0e-12; prop 0.1578 Wh, total 0.2057 Wh, err 0.027 m, RTF 0.48  (83 s)
```

These blocks are identical to the committed summary: `spec`, `layout`, `metrics` (34 keys) and
`chain` (6 keys). For example, propulsion_Wh is 0.15782234071065712, terminal_Wh
0.20573900737732567, final_soc 0.9993187201340494, peak_current_A 1.9428207047140358 and the chain
status PASS. The backend identity is identical. The 0.1 s trace (301 rows × 72 keys) has identical
values, and so does the full per-tick trace (3000 rows × 72 keys) when compared with the
uncommitted original in `logs/native_campaign/`. The decompressed bytes differ only by CRLF versus
LF (H-08).

The `evidence` and `energy_report.evidence` blocks differ:

| Field | Committed | v0.2.0 rerun |
| --- | --- | --- |
| share_percent.A | 84.099 % | 7.484 % |
| share_percent.B | 15.777 % | 92.392 % |
| share_percent.C / upper-bound share / total Wh | 0.1238 % / 4.4500 % / 0.205994 | same (≤ 2e-16 rel.) |
| proxy_share_percent | absent | 0.0 |
| registry version / records / sources | 0.2.0-dev / 124 / 141 | 0.2.0 / 177 / 144 |
| holoenergy_version, git | 0.1.0, `c6976332` dirty | 0.2.0, archive (no git) |

All 42 committed native summaries carry `0.1.0 / 0.2.0-dev / 124 records / c6976332 dirty`. Their
grade blocks therefore show T200 propulsion as grade A, while the README and §9 of the paper
outline state that propulsion is graded B (H-01).

### 5. Communication run: reproduced exactly

```text
cd $S/src && $py experiments/run_comm_matrix.py --port 5571 --configs A B --output $S/item5/comm_matrix.json
# A delivered 10/10 latency 0.7633484227048453 tx 10+0 E 0.03339 Wh check 0.00e+00
# B delivered 10/10 latency 2.1749274382374475 tx 20+0 relays 10 E 0.05122 Wh check 0.00e+00   (36 s)
```

For results A and B against the committed `comm_matrix.json`, 678 leaves are identical. The only
10 differing leaves are `observed_wall_time` wall-clock stamps. The committed file comes from
`c6976332` dirty and holo_desert 1.1.0 (H-01, provenance only).

### 6. 4/6/8 layout comparison: reproduced exactly

```text
cd /f/Andrea/HoloVirtualBattery && uv run --no-sync python experiments/analyze_native_campaign.py --tables-dir $S/item6/tables
```

All 11 outputs, including `N1_layouts.csv` and `analysis.json`, are byte-identical. In a second
run I used a copy of the committed native directory with my fresh `N1-L8-HV-direct-c0.2` summary
and trace substituted (`--native-dir $S/item6b/native`). All tables were identical except
`N1_layouts.csv`, row N1-L8-HV-direct-c0.2, column `real_time_factor` (0.313 vs 0.475, H-07).
Before the repository changed, I ran the analysis from the live tree. The analysis script is pure
Python with no holoenergy import, so the moving tree does not affect this result.

### 7. Offline E4: within tolerance

```text
cd $S/src && uv run --no-sync python experiments/run_offline_campaign.py --output $S/item7/offline   # 93 s
```

In `E4_external_drag.csv`, 18 of 112 cells differ. All of them are `P_std_*` (max rel. 4.5e-16)
or `residual_std_*` (about 1e-13 N, numerically zero). Every force and ratio column is identical.
E1 and E1b show the same last-bit pattern. E0, E3, E4_backend_consistency, E5_ablations and
E5_baselines are byte-identical. Rerunning with system Python and numpy 2.4.2 (the version in the
committed `manifest.json`) makes E1, E1b and E4 byte-identical, so the last-bit differences come
from numpy and the locked environment does not byte-reproduce the committed results (H-04).

`E2_payload_suites.csv` differs in substance: grade_A_percent drops from 91-98 % to 0-23 % and
grade_B rises correspondingly. Energies are identical. The cause is the same stale grading as in
item 4: the committed manifest records holoenergy 0.1.0 and `799b5daa` dirty (H-01).

### 8. Paper figures: reproduced exactly

```text
cd $S/src && python experiments/make_paper_figures.py --output-dir $S/item8/paper      # 8 s, system Python
```

All 43 files (PNG, SVG, PDF, CSV and `manifest.json`) are byte-identical to `docs/figures/paper`.
They stay identical with `--native-dir` pointing at the directory containing the fresh native run,
once its tables are placed under `<native-dir>/tables` (H-06). I did not test whether a different
matplotlib version also gives identical bytes (H-05).

### 9. Paper table: RQ table in `docs/paper_outline_smpat.md`

| Claim | Source value | Match |
| --- | --- | --- |
| RQ1: over-ground cubic −89 % (0.2), −98.7 % (0.5); transits −65 to −91 % | `baselines.csv` speed_cubic_relative_error −0.8946, −0.9868; −0.6548, −0.9055 | yes |
| RQ1: water cubic −15 % to +13 %; heave +68 % | −0.1534 … +0.1300; N3 0.6843 | yes |
| RQ2: 0.158 Wh shared by L8-HV/L6-STD/L4-H45 at 0.2 m/s | `N1_layouts.csv` 0.15782 for all three | yes |
| RQ2: 2 stern thrusters 13-17 % cheaper; 8.7 m sway drift | 2H2V/H45 = 0.8737 (0.5), 0.8314 (0.2); N2 tail error 8.702 m | yes |
| RQ2: 2 verticals +42 % heave; 4H cannot heave | N3 0.0619/0.0436 = 1.419; L4-H45 0 Wh, not satisfied | yes |
| RQ2: 3D vectoring +21-30 % | VEC30/HV = 1.214 (0.5), 1.298 (0.2) | yes |
| RQ2: 30° 2.32/4.67 Wh, 60° 5.47/1.99 Wh; 60 A on 8 % of ticks | N2 2.3176/4.6736, 5.4721/1.9948; peak 60.00 A, derated 0.0753 | yes (7.5 % rounded to 8) |
| RQ3: 67 s; inspection +86 % (2.83 vs 1.52 Wh); AI vision +23 %; hotel 0.048 Wh/30 s | N5 2.8292/1.5198 = 1.862; 1.8639/1.5198 = 1.226; N1 c0 terminal 0.0479; crosslayer duration 67.0 | yes |
| RQ4: acoustic ≤ 1.37 %, optical 0.57 %; multi-hop 27/34, flooding 33/34; 0.8 W | `crosslayer.json` 1.3724-1.3742 %, 0.5740 %; delivered 27, 33 of 34; modem profile note "0.8 W … upper bound" | yes |
| RQ5: 2.62-2.84 Wh, open on both sides | F13 CSV N5-S5 low 2.6245, high 2.8367, both open lists non-empty | values yes, wording no (H-11) |
| RQ6: 3.8-4.5x at 0.4-1.0 m/s | `E4_external_drag.csv` 4.4865, 3.939, 3.988, 3.970, 3.826 | yes |
| RQ6: still-water resistance 1.13-1.21x (0.2-0.6 m/s) | not in any results file; E4 has only the quadratic ratio 0.857-1.095 | hand-derived only (H-10) |

For the 1.13-1.21x figure, recomputing (quadratic drag + 11.5·U) / (13.7·U + 141·U²) gives 1.131,
1.188 and 1.212, so the arithmetic is correct.

## Documentation gaps

No gap was critical: every requested item could be run on this machine. The major gaps either
leave committed results inconsistent with v0.2.0 or prevent an external user from rebuilding the
native environment.

| ID | Severity | What blocked or misled me | Fix |
| --- | --- | --- | --- |
| H-01 | major | Every committed native summary (42), `comm_matrix.json`, `crosslayer.json` (`e118bde9`) and the offline `manifest.json` (`799b5daa`) comes from pre-release dirty trees with holoenergy 0.1.0. The native summaries also use registry 0.2.0-dev with 124 records. At v0.2.0 the evidence-grade fields do not reproduce: N1-L8-HV-direct-c0.2 A 84.1 → 7.5 % and B 15.8 → 92.4 %; offline E2 grade A 91-98 → 0-23 %. These committed grade shares contradict the README and outline statement that propulsion is graded B. Energies and physics do reproduce. | Regenerate the grade blocks at the tag, by rerunning or by recomputing from the traces, and rerun the offline campaign. Alternatively, mark the stale fields in `native_runs.md` and the summaries. Add a check that flags a summary whose registry version differs from the package version. |
| H-02 | major | The native and DESERT interpreter `$py` is not specified anywhere. I found no requirements or lock file, and no instructions for installing the HoloOcean 2.3.0 client (the committed check records a temporary local install origin, `holoocean-client-…/client`) or holo_desert 1.1.0 (source and commit not given). Python 3.10.20 and numpy 1.26.4 are recorded only in outputs. I could only use the pre-provisioned venv. | Add an environment spec or lock for the native environment, with the client source and commit and the holo_desert repository and commit. |
| H-03 | major | The docs never say to reproduce from a clean checkout of `v0.2.0`, and the scripts accept dirty trees silently (they only record the state). During this review the branch moved by 3 commits, and an uncommitted change by another user entered my first native run. | Document `git worktree add <dir> v0.2.0` or `git archive`. Add a `--require-clean` option, or a warning, to the campaign scripts. |
| H-04 | minor | The docs say the offline campaign runs in the locked environment (numpy 2.5.4), but the committed outputs used numpy 2.4.2. E1, E1b and E4 then differ by ≤ 4.5e-16 relative, and are byte-identical only with numpy 2.4.2. | Regenerate in the locked environment, or state the numpy version and a comparison tolerance. |
| H-05 | minor | The figures need "any Python with matplotlib", but matplotlib is not pinned (not in any extra or in `uv.lock`), and the figure `manifest.json` records no matplotlib, numpy or Python version. Byte identity was confirmed only with matplotlib 3.10.8 on Windows. | Add a pinned `figures` extra and record the versions in the manifest. |
| H-06 | minor | `make_paper_figures.py --native-dir` reads its tables from `<native-dir>/tables`, while the analysis script writes to a separate `--tables-dir`. With the scratch layout from `native_runs.md` §4, F08 is silently skipped ("run analyze first"; recorded only in `manifest.json`). | Add `--tables-dir` to the figure script, or document the required layout. |
| H-07 | minor | The N1-N6 tables include `real_time_factor`, which depends on wall clock and machine load, so a rerun campaign can never byte-reproduce them. This was the only difference in item 6. | Move timing out of the results tables, or document the column as excluded from comparison. |
| H-08 | minor | Committed summaries store only the SHA256 of the gzip file, which depends on the gzip header and line endings. The committed traces contain CRLF, while v0.2.0 writes LF. `content_sha256` exists in v0.2.0 but is missing from the committed summaries, so a reproduction cannot be verified by hash. I had to parse and compare values instead. | Regenerate the summaries with `content_sha256`, or document the comparison procedure. |
| H-09 | minor | The `csv` module writes CRLF, while the git blobs hold LF. Byte identity of regenerated CSV files holds only with `core.autocrlf=true`, so `cmp` fails on Linux or macOS checkouts. | Use `lineterminator="\n"` and add `experiments/results/** text eol=lf`, or document line-ending normalisation before comparing. |
| H-10 | minor | The outline says "every number below is … stored in `experiments/results/`", but RQ6 "1.13-1.21x" (quadratic + linear damping) is not in any results file. It is derived by hand in `bluerov2_hydrodynamic_external_comparison.md`, and the cited `E4_external_drag.csv` holds only the quadratic ratio 0.86-1.10x. The arithmetic checks out. | Add a still-water resistance column and ratio to E4. |
| H-11 | minor | RQ5 describes 2.62-2.84 Wh as the interval "for the hotel-load part of the inspection transit". In F13 these values are the terminal-energy interval of N5-S5 (nominal 2.83 Wh), whose width comes only from the hotel loads. | Reword the RQ5 entry. |
| H-12 | minor | The backend-check command in `native_runs.md` §1 writes over the committed `experiments/results/native/backend/check_patched_after.json`, and the scratch-option list in §4 omits it. | Show `--output <scratch>` in §1. |
| H-13 | minor | Several docs disagree. `holoocean_patched_build.md` uses `C:/Users/Andrea/miniconda3/envs/holoocean_joystick/python.exe`, while `native_runs.md` uses `F:/Andrea/HoloWithDesertCommunications/.venv`. The README lists PyYAML as the only core dependency, but numpy is also one. The README says to install HoloEnergy into the HoloOcean environment, yet the scripts import it from the source tree and the environment has no holoenergy installed. | Align the documents. |
| H-14 | minor | `uv build` appears only in CI, not in the docs. Two builds give identical wheel members but different zip timestamps, so the wheel SHA256 is not reproducible. | Document `SOURCE_DATE_EPOCH` for reproducible wheels. |
| H-15 | minor | The DESERT image digest is truncated (`sha256:dce313c4…`), and the image must be built from an external project. I could not verify the image because Docker was not allowed; the engine fingerprint did match. | Give the full digest and the source commit of holo_desert. |

Observations outside the gaps:

- The patched package exists only on this machine. Its build is documented, but rebuilding it
  needs UE 5.3 (Launcher), MSVC 14.44 and an Epic account, so an outside reproduction of items 3-4
  depends on that build.
- E2 contains negative float-residue percentages, for example grade_D_percent −1.1e-15.

## Artefacts

Under `$S`:

- `item3/`: backend check JSON and stdout.
- `item4/`: the native summary, 0.1 s trace and full trace from the clean archive.
- `item4_liverepo_discarded/`: the discarded run from the dirty tree.
- `item5/`: `comm_matrix.json`.
- `item6/` and `item6b/`: tables from the committed summaries and from the fresh run.
- `item7/offline` and `item7/offline_sysnumpy242`: offline outputs in the locked environment and with numpy 2.4.2.
- `item8/paper` and `item8/paper_freshN1`: regenerated figures.
- `pytest_full.txt`: full test log.
- `dist/` and `dist2/`: the two builds.
- `jsondiff.py`, `csvdiff.py`, `csvdiff_detail.py`, `tracediff.py`: comparison helpers.
