# HoloOcean backend compatibility

HoloEnergy accounts for the effort a controller submits to the backend; the backend
owns the vehicle dynamics. This table states what has been verified at runtime on
this project's machine (Windows 11, Ocean package, `SimpleUnderwater`, BlueROV2,
control scheme 0, 2026-10-07). Untested versions are not declared correct.

| HoloOcean backend | Vehicle drag | Physics step | HoloEnergy status |
| --- | --- | --- | --- |
| 2.3.0 stock Ocean package (`Holodeck.exe` SHA256 `8c206c9c…`) | **incorrect**: applied drag = 0.0100 × its own SI equation, with currents and in still water (153 + 117 runtime cases; upstream `test_currents` scenario on HoveringAUV) | consistent with the client clock at ≥ 30 Hz; capped at 1/30 s below 30 Hz | supported **with warning**: energy under currents or vehicle motion is software-coupling evidence only; `tools/check_holoocean_backend.py` reports FAIL |
| 2.3.0 + [`patches/holoocean-2.3-drag-units.patch`](../patches/README.md), separate build (`4d6c2d46…`) | **verified**: applied/expected 1.0000000 ± 1e-7 (currents ±X/±Y/±Z, yawed vehicle, moving vehicle in still water); thrust, gravity, buoyancy bit-identical to the unpatched control build | same as stock | **recommended**, at 100 Hz; drag-to-electrical-demand chain closed per tick in closed loop |
| 2.3.0 rebuilt without the patch (control, `f52999de…`) | bit-identical audit data to the stock package | same as stock | verification control only |
| `develop` (unreleased, `f3d1230c`, 2026-10-07) | same omission in `ApplySurfaceBuoyancy`, `ApplyUnderwaterBuoyancy`, `ApplyWavelessForces` (source review only, not run) | not tested | unknown, not supported |
| 2.4.x | not released as of 2026-10-07 | not tested | run the check and the audits before use |
| < 2.3.0 | not tested | not tested | unknown |

Rules for any backend:

* Run `python tools/check_holoocean_backend.py [--binary <package Holodeck.exe>]`
  before quantitative energy studies with currents or vehicle motion. Its last line
  is `PASS`, or `FAIL: detected ~0.01 drag scaling associated with unpatched
  HoloOcean 2.3.0`; it also checks that the physics step equals the client step at
  100 Hz. It verifies; it never compensates.
* Use `ticks_per_sec >= 30` (UE 5.3 `MaxPhysicsDeltaTime = 1/30 s` without
  substepping). The native examples default to the verified 100 Hz and refuse an
  energy step longer than 1/30 s before starting the simulator.
* HoloEnergy never rescales drag, currents, effort or energy to compensate a
  backend. A corrected backend is the only supported correction.
* Other buoyant agents (TorpedoAUV, CougUV, SurfaceVessel, FixedWing) share the
  drag code path but have not been runtime-verified here; Fossen-based dynamics is a
  separate contract and is not covered.

Evidence: [verified backend report](verified_backend_report.md),
[timestep report](holoocean_timestep_report.md),
[build procedure](holoocean_patched_build.md),
[`sources/verified_backend`](../sources/verified_backend).
