# Round 2, Reviewer 4: numerical methods and V&V

Scope: docs/paper/VERIFICATION_VALIDATION_FRAMEWORK.md, paper/manuscript.md (Sections 3.3, 5.5, 5.6, 7, 9.1, 10, 12, 13.2),
experiments/verify_final_energy.py, experiments/results/final/energy_verification.json, experiments/analyze_final_experiments.py,
holoenergy/decision.py, holoenergy/uncertainty.py, tests/test_decision.py. Probes: scratchpad r4/probes.py (offline, synthetic
report dicts, `uv run --no-sync python`; no simulator started). No source file was modified.

## Verdict

MAJOR REVISION for the numerical and V&V parts. The framing is honest: nothing is called physical validation and the "absent"
rows are explicit. The remaining problems are (a) two reproducible soundness defects in `decision.py` that can produce a
SUPPORTED verdict the stated rules do not justify, (b) a headline V&V number that does not match the committed artifact,
(c) a few loosely used terms (EXP9 "validation attempt", "Calculation verification", interval analysis grouped with
one-at-a-time sensitivity), and (d) default "SUPPORTED" verdicts that hold propulsion at its nominal value although propulsion is
52-100 % of mission energy and EXP9 shows factors of 0.11-1.29. The core argument (bus-side scaling, zero for missing lower
bounds, open upper sides, common unverified scale s >= 1) is mathematically sound; the defects are at its edges.

## Findings

| ID | Severity | Location | Finding | Evidence / probe | Required change |
| --- | --- | --- | --- | --- | --- |
| R4-01 | High | decision.py `assess_energy_requirement` l.118-123; uncertainty.py scale | The supported lower bound uses the nominal bus scale 1/eta of an unverified rail. The documented argument is that on an unverified rail only s >= 1 is known, so the lower side must use s = 1. A configured but unevidenced efficiency (for example 0.5, `rail_verified` False) inflates the lower bound and can yield SUPPORTED_FAIL. | Probe P1: payload rail unverified, nominal scale 2, device energy 1.0 Wh, limit 1.5 Wh. Result SUPPORTED_FAIL, low = 2.0. Evidence admits s = 1, i.e. 1.0 Wh <= 1.5, so INDETERMINATE is required. No test covers it (the unverified test case uses efficiency 1.0). | For every rail with `rail_verified == False`, compute the lower side with scale 1 (subtract (scale-1)*E_device of that rail). Same for `low` in `energy_intervals`. Add a regression test with an unverified, non-unit efficiency. |
| R4-02 | High | decision.py `_same`, `compare_energy` l.242-250, 300-309 | Cancellation of "identical" contributions ignores rail verification status. If a rail is unverified in A only, an identical contribution C is s*C in A and C in B and does not cancel; `_lower_supported` constrains only the differing sums, so it cannot see this. A false A_LOWER_SUPPORTED results. The pairing is plausible: same nominal efficiency, one with an evidence record, one without. | Probe P2: DVL 1.0 Wh identical (scale 1.0) in both runs; payload unverified in A only; B also has a sonar 0.5 Wh [0.4, 0.6]. Result A_LOWER_SUPPORTED, difference_high = -0.4. Truth: A - B = (s-1)*1.0 - [0.4, 0.6], unbounded above in s. Expected RANKING_NOT_SUPPORTED. | Require equal verification status of the contribution's rail in both runs in `_same`; otherwise treat it as differing with s unknown. Add a test. Check, not only state, the "same converter in both runs" precondition. |
| R4-03 | Medium | decision.py `assume_verified` | No boundary validation. A bare string iterates by character, a typo or unknown rail is silently accepted, and the assumption text lists garbage. The failure direction is conservative (stays INDETERMINATE) but silent. | Probe P3: `assume_verified="payload"` gives "conversion treated as verified for: a, a, d, l, o, p, y"; `("payloads",)` accepted. | Reject str; require a subset of {"payload", "hotel"}; raise ConfigurationError otherwise; test both. |
| R4-04 | Medium | manuscript 5.5, Table 1 row "One-at-a-time sensitivity; evidence intervals", 8, 13.2; framework table | The EnergyReport interval is not one-at-a-time. Eq. (15) and `energy_intervals` move all records to their low (high) ends simultaneously: a joint worst-case hull, non-probabilistic, parameters independent. EXP10 is OAT over alternative models. Describing everything as "one-at-a-time and deterministic" is inaccurate for the intervals. The ranges are published ranges, not coverage-qualified bounds, so "supported" means "within published ranges". | uncertainty.py l.86-95 sums deltas over all states. | Split the two in Table 1 and 13.2: EXP10 = OAT model-alternative sensitivity analysis; EnergyReport = deterministic interval analysis (non-probabilistic UQ), joint worst case, no probability or coverage. State that the bound is only as good as the published ranges. |
| R4-05 | Medium | manuscript 5.5, 5.6, Table 3; decision.py default | Default verdicts exclude propulsion uncertainty although propulsion is 52-100 % of energy and EXP9 gives 0.11-1.29x. SUPPORTED_PASS/FAIL under the default is conditional on the simulator's nominal dynamics, which the paper says conflict with external data. "Supported" and the test comment "certified" over-read this. The N-legs case states nominal propulsion in prose only. | decision.py l.128 `dynamics = "excluded: ..."`; Table 3 labels rows plainly "Supported". | Add a qualifier field and Table 3 wording ("supported, conditional on nominal propulsion"). Run the leg-target assessment once with the EXP9/EXP10 factor range to show which verdicts survive. |
| R4-06 | Medium | manuscript l.20, 448, 538, 914; CLAIM_EVIDENCE_MATRIX C2; framework table | Headline "worst relative error 1.9e-13" does not match the artifact. `energy_verification.json` has worst 2.49e-13 (EXP3-L4-2H2V-sway0.5 and EXP5-station-c0, check `phases.sum_terminal`); 1.9e-13 is the EXP6 worst. | Max of `worst_relative_error` over the 36 runs = 2.4946711363327267e-13. | Correct to 2.5e-13 everywhere (or regenerate and explain). |
| R4-07 | Medium | verify_final_energy.py | (i) Docstring "Independent" overstates: traces come from the same run and power model. (ii) TOL = 1e-9 is unjustified and four orders looser than the observed 2.5e-13, so a 1e-10 accounting error would pass; naive summation error is about N*eps, so about 1e-11 is defensible. (iii) `rel` falls back to an absolute difference when the reference is below 1e-15, and 212 of 780 checks are 0 vs 0 (trivial). (iv) The 72 conservation and 72 phase checks compare summary values with summary values, not with the trace. (v) The I^2 R recomputation covers 35 of 36 runs. | JSON counts: category 252, component 241, conservation 72, phases 72, I2R 35. | Reword "independent"; justify or tighten the tolerance and report observed vs bound; report the number of nonzero checks; say which checks are trace-based; state the 35/36 I2R coverage. |
| R4-08 | Low | Table 1 "Timestep audit ... Calculation verification" | Calculation verification means estimating numerical error for the runs used. The row is a 20-200 Hz audit with 100 Hz chosen; the manuscript gives no energy difference, no order, no tolerance. The zero-order hold of Eq. (1) and the bisection tolerance of Eq. (4) are not reported. | Only the cited holoocean_timestep_report.md. | Report the 100 vs 200 Hz energy difference and the bisection tolerance, or relabel as "time-step selection check". |
| R4-09 | Low | Table 1, framework: EXP9 "Sub-model validation attempt" | Data of different vehicles and conditions, references disagreeing 6-9x, no measurement uncertainty: this is an external-consistency or benchmark comparison, not a validation attempt. The label lets a reader count it as a failed validation. Section 5.4 already uses "external consistency: conflicting". | Framework "Consequences" says nothing is called validation except EXP9. | Rename to "external consistency check (drag)"; then "nothing is called validation" becomes literally true. |
| R4-10 | Low | Terminology, citations | "Input verification" and "model verification" are project-defined, not ASME V&V 10/20 or Oberkampf and Roy terms; the accounting row is "Code and model verification" (blurred). The manuscript says activities are rated "following the idea of a credibility assessment (Blattnig 2008)" but no scale is applied. The framework records that no standard has been read or cited. | Framework l.3-6. | Define the categories once as the paper's own, cite standards after reading them, and apply a rating or delete the sentence. Assign the accounting recomputation to one category. |
| R4-11 | Low | Consistency | Test count: framework 344, manuscript Table 1 and matrix C21 355. Eq. (15) omits the 1/eta bus scale that the code and Section 5.6 use. "Regression test for each defect" is contradicted by R4-01/02 having no test. | grep. | One source for the count; add the scale to Eq. (15) or say device side. |
| R4-12 | Low | decision.py `_close` | The tolerance is `tol*max(|p|,|q|,1.0)`: absolute 1e-9 Wh below 1 Wh, not relative as documented. A different tiny contribution is cancelled. Physically negligible. | Probe P6: 1e-12 vs 9e-10 Wh gives differing == (). | Use a relative test with a small absolute floor; document it. |
| R4-13 | Info | Verified sound | Correct on inspection and by probe: bus scale on deltas; subtracting the bus energy of open_low items (equals zero); `max(low, 0)`; open upper side gives high None; propulsion factor scaling both sides; shared unverified rail rule (term <= 0 at all s >= 1 is necessary and sufficient with independent per-rail s); X-only rule (x_hi must be 0); Y-only rule (s = 1 worst case); antisymmetry. | Probes P4, P5, P7. | Keep P4 and P5 as regression tests (absent from test_decision.py). |

## Probes (scratchpad r4/probes.py)

1. P1 unverified rail with non-unit placeholder efficiency: SUPPORTED_FAIL where INDETERMINATE is required (R4-01).
2. P2 identical contribution on a rail unverified in one run only: false A_LOWER_SUPPORTED (R4-02).
3. P3 `assume_verified` as a string or misspelt rail: silently accepted (R4-03).
4. P4/P5 shared unverified rail, cross-rail trade-off: correct, nominal tie gives not supported.
5. P6 tolerance floor: 1e-12 vs 9e-10 Wh treated as identical (R4-12).
6. P7 propulsion factor with an open-low item: correct.

## Test gaps (tests/test_decision.py)

Integration style on the real EnergyAwareEnv with a null backend, no mocking of the system under test: good. Missing: unverified
non-unit efficiency, asymmetric verification in a pair, `assume_verified` validation, `propulsion_factor_range` with a
SUPPORTED_FAIL or a reversed range, shared-rail sign cases (P4/P5), antisymmetry of `compare_energy(a, b)` vs `(b, a)`, and
high == limit.

## Determinism

Native runs are described as deterministic and the replay difference is 0.0, which supports reproducibility of the accounting.
No statement is made about floating-point summation order or platform; add one sentence (same interpreter and machine) or a
repeat-run hash check.
