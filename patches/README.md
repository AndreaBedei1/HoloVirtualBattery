# HoloOcean 2.3.0 drag-unit patch

`holoocean-2.3-drag-units.patch` (SHA256 `00f1b30383f4f40544a44c8660b84c4ade31c25bf6409b0d662a21728ab488fa`)
corrects the magnitude of the native vehicle drag force of HoloOcean buoyant agents.
It is kept in this repository even if upstream integrates an equivalent fix.

## Affected version

| Item | Value |
| --- | --- |
| Release | HoloOcean 2.3.0 (client + Ocean world package) |
| Source | tag `v2.3.0`, commit `49e70552dfd97273b7dfbe755fbe65d7738b24b7` |
| File | `engine/Source/Holodeck/HolodeckCore/Private/HolodeckBuoyantAgent.cpp`, `AHolodeckBuoyantAgent::ApplyBuoyancyDragForce` (lines 87–96) |
| Official binary | Ocean `Holodeck.exe` SHA256 `8c206c9cc05c640fb2efea6bd43bda33c585536ab16a931c55780855e7602253` |
| Agents | every subclass of `AHolodeckBuoyantAgent` (BlueROV2, HoveringAUV, TorpedoAUV, CougUV, SurfaceVessel, FixedWing; drag scales with the submerged ratio); runtime-audited for BlueROV2 only |
| Unreleased `develop` | same omission in `ApplySurfaceBuoyancy`, `ApplyUnderwaterBuoyancy`, `ApplyWavelessForces` (commit `f3d1230c`, 2026-10-07); not runtime-tested |

## Bug

The drag equation `-0.5 * rho * |v_rel|^2 * Cd * A * normal(v_rel)` is evaluated with
SI inputs (m/s, kg/m³, m²) and yields newtons, already in UE world axes. It is passed
directly to `AddForceAtLocation`, whose raw force unit with centimetres and kilograms
is kg·cm/s² (1 N = 100 units). Gravity, buoyancy and thrusters convert N to UE units
(`ConvertLinearVector(..., ClientToUE)`); drag does not. The applied drag is therefore
1/100 of the SI equation, for currents and for a vehicle moving in still water.

## Fix

```cpp
// DragForce is SI newtons in UE world axes: scale units without reflecting Y.
DragForce *= UEUnitsPerMeter;   // UEUnitsPerMeter == 100.0f (Conversion.h)
```

inserted after the drag equation, before `AddForceAtLocation`. It is not
`ConvertLinearVector(DragForce, ClientToUE)`: the relative velocity is already in
UE world axes (the current getter reflects Y), so that helper would reflect Y a
second time. Coefficients, gravity, buoyancy, thrusters, damping and the debug
drawing (which does not draw the drag vector) are unchanged.

## Evidence

* Source review and dimensional analysis: [drag units report](../docs/holoocean_drag_units_report.md).
* BEFORE (official binary): applied/expected drag `0.0099999997` over 153 cases
  (17 cases × 60/100/200 Hz × 3 repeats); absolute thruster and gravity references pass.
* Control (unpatched rebuild from the same tree and toolchain): audit data
  bit-identical to the official binary (same raw SHA256), so the rebuild changes
  nothing observable.
* AFTER (patched rebuild, `Holodeck.exe` SHA256 `4d6c2d46…`): applied/expected drag
  `1.0000000074` over the same 153 cases (currents ±X/±Y/±Z, yawed vehicle,
  quadratic law unchanged) and `1.0000001686` on the first step / `1.0000000180` on
  every step for a vehicle moving in still water (117 cases); thruster 10 N,
  gravity, neutral buoyancy, angular stability bit-identical to the control build.
* Upstream `test_currents_underwater` scenario (HoveringAUV, 1 m/s, 60 Hz): official
  0.06320976 m/s² (= the upstream expected constant = 0.01 × SI), patched
  6.32097578 m/s² (1.0000000104 × SI).
* Full report: [verified backend report](../docs/verified_backend_report.md); data:
  [`sources/verified_backend`](../sources/verified_backend).

## Application

On a separate checkout, never on an installed package. Clone with LF line endings:
with Git for Windows' default `core.autocrlf=true` the checkout has CRLF and the
patch (LF) does not apply.

```powershell
git -c core.autocrlf=false clone --depth 1 --branch v2.3.0 https://github.com/byu-holoocean/HoloOcean.git holoocean-2.3.0
git -C holoocean-2.3.0 apply --check <repo>/patches/holoocean-2.3-drag-units.patch
git -C holoocean-2.3.0 apply <repo>/patches/holoocean-2.3-drag-units.patch
```

The HoloOcean repository requires access granted by its maintainers (it is
private on GitHub as of 2026-10-07).

## Revert

```powershell
git -C holoocean-2.3.0 apply --reverse --check <repo>/patches/holoocean-2.3-drag-units.patch
git -C holoocean-2.3.0 apply --reverse <repo>/patches/holoocean-2.3-drag-units.patch
```

or keep using the installed package (tools default to it when `--binary` is omitted).

## Build

[docs/holoocean_patched_build.md](../docs/holoocean_patched_build.md): UE 5.3.2 from
source, the official binary's toolchain (MSVC 14.44.35207, Windows SDK 10.0.22621.0),
a code-only rebuild of `Holodeck.exe` next to the official cooked containers, and an
unpatched control build. Automated by `tools/build_patched_holoocean.py`.

## Verification

```powershell
python tools/check_holoocean_backend.py --binary <package>/Windows/Holodeck/Binaries/Win64/Holodeck.exe
python examples/verify_holoocean_drag_units.py --source-dir <patched checkout> --binary <...>/Holodeck.exe
```

`check_holoocean_backend.py` prints `PASS` for a backend that applies its SI drag
equation and integrates the client step, or
`FAIL: detected ~0.01 drag scaling associated with unpatched HoloOcean 2.3.0`.

## Upstream

Existing issue: [byu-holoocean/HoloOcean#368](https://github.com/byu-holoocean/HoloOcean/issues/368)
("Question - Unit Ocean Currents", open). Prepared comment and PR text:
[docs/holoocean_drag_issue_draft.md](../docs/holoocean_drag_issue_draft.md). Nothing
has been posted by this project. The upstream test
`client/tests/scenarios/test_currents.py::test_currents_underwater` hard-codes
0.06320982 m/s², which is the 0.01-scaled value; with the fix it becomes
6.320976 m/s², so the proposed PR changes that expectation together with the fix.

`holoocean-develop-drag-units.patch` (SHA256
`3f5508dfa7b40690884d1cb0266399b0edc84cf91fb828d3e6d90a448711c02e`) is the proposed
upstream change for the unreleased `develop` branch at
`f3d1230c4050b57982d122fa2093e1097c21111a`: the same line in
`ApplySurfaceBuoyancy`, `ApplyUnderwaterBuoyancy` and `ApplyWavelessForces`, plus
the `test_currents_underwater` expectation. It applies and reverses cleanly on that
commit but has **not been built or run**; the empirical `test_currents_surface`
values must be regenerated on a patched build with the TestWorlds package before a
PR. Use the 2.3.0 patch for the released package.

## License

Both patches contain context from HoloOcean's MIT-licensed code
(`engine/Source/Holodeck`; the `develop` diff also `client/tests`).
Copyright (c) 2024 BYU-FRoStLab; the source file also carries its original
2021 BYU FRoStLab notice. The upstream MIT terms are retained in
[HOLOOCEAN_LICENSE.txt](HOLOOCEAN_LICENSE.txt). No Epic engine code is redistributed.
Building/using UE and HoloOcean assets requires the relevant Epic licensing.
