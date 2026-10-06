# Contributing and release policy

Keep `main` stable and develop on topic branches. Preserve history; no force push
is needed for this workflow. Run pytest, Ruff lint/format and package build before
merging. CI runs Python 3.10–3.13 on Linux and Windows without Unreal/worlds/GPU.
Native HoloOcean verification is an explicit manual check described in
[verification.md](docs/verification.md), never an ordinary unit test.

Use semantic versions: patch for compatible fixes, minor for compatible model/API
extensions, major for breaking contracts. Synchronize `pyproject.toml`,
`holoenergy.__version__` and `CITATION.cff`. Tag `v0.1.0` only on a clean, verified
commit; subsequent research datasets reference version, commit and resolved config
hash. A release number establishes software state, not experimental accuracy.

New scientific equations/parameters need primary sources or a recorded calibration
dataset, clear units, domains and simplifications. Unknown hardware values remain
unconfigured. Synthetic fixtures belong in tests and must be labelled as such.
Do not overwrite manufacturer source bytes or hide processing discrepancies.
Keep experimental runs disjoint by cycle/mission; record identification, model
selection and final validation in a verified manifest before evaluating results.

The core remains external to HoloOcean. Added fidelity requires evidence that the
simpler model is insufficient; RC branches, enclosure nodes and inflow corrections
need identifiable measurements and held-out improvement. No hardware-control
interface is part of this package.
