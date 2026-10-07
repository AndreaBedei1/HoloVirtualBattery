# HoloOcean upstream contribution — prepared, not posted

Updated 2026-10-08. **Nothing has been posted.** Publishing is an outward-facing
action that needs the author's explicit go-ahead; this file holds the exact text.

| Item | Status |
| --- | --- |
| Target | comment on the existing issue [byu-holoocean/HoloOcean#368](https://github.com/byu-holoocean/HoloOcean/issues/368) ("Question - Unit Ocean Currents", open; a maintainer suspected a bug on 2026-08-05), not a duplicate issue |
| Patch for 2.3.0 | [`patches/holoocean-2.3-drag-units.patch`](../patches/holoocean-2.3-drag-units.patch): built and verified at runtime |
| Diff for `develop` | [`patches/holoocean-develop-drag-units.patch`](../patches/holoocean-develop-drag-units.patch), against `f3d1230c` (2026-10-07): applies and reverses cleanly; **not built, not run** |
| Pull request | prepared below, **not opened**: needs a fork of the private repository and regenerated `test_currents_surface` values (requires the TestWorlds package) |
| Upstream state | [`upstream_status.json`](../sources/verified_backend/upstream_status.json): repository private, user permission `pull`, forking allowed, latest release v2.3.0 |

## 1. Comment for #368 (final text)

````markdown
I think I found the cause of the very small current-induced motion reported here,
and verified a one-line fix by rebuilding Ocean 2.3.0.

**Cause.** In `AHolodeckBuoyantAgent::ApplyBuoyancyDragForce()`
(`engine/Source/Holodeck/HolodeckCore/Private/HolodeckBuoyantAgent.cpp`, v2.3.0
lines 87–96) the drag is computed from SI inputs (`GetUnrealWorldVelocity()/100`
and the current in m/s, `WaterDensity` kg/m³, `AreaOfDrag` m²), i.e. in newtons,
and passed directly to `AddForceAtLocation`, whose raw unit is kg·cm/s²
(1 N = 100 units). Gravity and buoyancy in the same function, and the thrusters,
convert with `ConvertLinearVector(..., ClientToUE)`; the drag does not, so it is
applied at **1/100** of its own equation, both for currents and for a vehicle moving
in still water.

**Fix** (magnitude only: `RelativeVel` is already in UE world axes because
`GetOceanCurrentVelocity()` reflects Y, so `ConvertLinearVector` would reflect it
twice):

```diff
     FVector DragForce = -0.5 * WaterDensity * RelativeVel.SizeSquared()
         * CoefficientOfDrag * AreaOfDrag * RelativeVel.GetSafeNormal();
+    // DragForce is SI newtons in UE world axes: scale units without reflecting Y.
+    DragForce *= UEUnitsPerMeter;
     RootMesh->AddForceAtLocation(
         DragForce * ratio,
```

On `develop` (f3d1230c) the same expression is in `ApplySurfaceBuoyancy`,
`ApplyUnderwaterBuoyancy` and `ApplyWavelessForces`; the same line applies there
(I have not built or run develop).

**Verification** (Windows, Ocean 2.3.0, `SimpleUnderwater`, BlueROV2 scheme 0;
native only, no controller). I rebuilt `Holodeck.exe` from v2.3.0 with UE 5.3.2
and the toolchain recorded in the official PDB (MSVC 14.44.35207, SDK 10.0.22621.0),
next to the official cooked content, twice: unpatched (control) and patched.
Applied force is inferred from the first step from rest,
`F = m·(v1/(1 − c·dt) − v0)/dt` (UE ether drag `c = 1/s` from `SetLinearDamping`),
validated by a known 10 N thruster force and by gravity in air.
17 cases × 60/100/200 Hz × 3 repetitions = 153 cases, 8 steps each:

| Current (m/s) | SI equation (N) | Official binary (N) | Patched (N) |
| ---: | ---: | ---: | ---: |
| 0.1 | 1.7946 | 0.017946 | 1.794600 |
| 0.2 | 7.1784 | 0.071784 | 7.178400 |
| 0.4 | 28.7136 | 0.287136 | 28.713600 |
| 0.8 | 114.8544 | 1.148544 | 114.854401 |

* applied/expected: official **0.0099999997**, patched **1.0000000074**
  (also for ±X/±Y/±Z currents and a vehicle yawed 90°; quadratic law unchanged);
* vehicle moving in still water (0.2–0.8 m/s, all axes, 117 cases): official
  0.0100001, patched 1.0000002 on the first step (every-step mean 1.00000002);
* the unpatched control rebuild produces **bit-identical** data to the official
  binary, so the rebuild itself changes nothing;
* thrust (10 N on X/Y/Z), gravity, neutral buoyancy, angular stability: identical
  between control and patched builds (|Δv| = 0 on the first step of every case
  without drag);
* in closed-loop station keeping and a transit/yaw/return mission on the patched
  build, the per-tick momentum balance (thrusters + SI drag) closes to float32
  precision (largest residual 5e-5 N against drag up to 88 N).

Your `client/tests/scenarios/test_currents.py::test_currents_underwater` expects
0.06320982 m/s² for HoveringAUV in a 1 m/s current at 60 Hz. That value is exactly
`0.01 × 0.5·ρ·Cd·A·u²/m × (1 − c·dt)` with the HoveringAUV literals
(m = 31.02 kg, Cd = 0.8, A = 0.5 m²); with the fix it becomes 6.320976 m/s².
Reproduced in Ocean/SimpleUnderwater with the same sequence: official binary
0.06320976 m/s² on X, Y and Z (0.0100000000 × the SI value), patched build
6.32097578 m/s² (1.0000000104 × the SI value). `test_currents_surface` uses
empirical values that also include the vehicle-level drag, so they would need
regenerating on a patched build (I don't have the TestWorlds package).

<details>
<summary>Minimal reproduction (HoloOcean + NumPy only)</summary>

```python
import math
import holoocean
import numpy as np

cfg = {
    "name": "Drag units repro",
    "package_name": "Ocean",
    "world": "SimpleUnderwater",
    "main_agent": "rov0",
    "ticks_per_sec": 100,
    "frames_per_sec": False,
    "agents": [
        {
            "agent_name": "rov0",
            "agent_type": "BlueROV2",
            "control_scheme": 0,
            "location": [0, 0, -5],
            "rotation": [0, 0, 0],
            "sensors": [{"sensor_type": "DynamicsSensor", "configuration": {"UseCOM": True}}],
        }
    ],
}
zero = np.zeros(8)
with holoocean.make(
    scenario_cfg=cfg, ticks_per_sec=100, frames_per_sec=False, show_viewport=False
) as env:
    for u in (0.1, 0.2, 0.4, 0.8, 0.0):
        env.reset()
        env.set_ocean_currents("rov0", [0, 0, 0])
        env.agents["rov0"].set_physics_state(
            np.array([0, 0, -5]), np.zeros(3), np.zeros(3), np.zeros(3)
        )
        previous = env.step(zero)
        v0 = previous["DynamicsSensor"][3:6].copy()
        assert np.linalg.norm(v0) < 1e-8
        env.set_ocean_currents("rov0", [u, 0, 0])
        action = zero if u else np.array([0] * 4 + [10 / (2 * math.sqrt(2))] * 4)
        velocity = env.step(action)["DynamicsSensor"][3:6].copy()
        force = 11.5 * (velocity - v0) / 0.01 / 0.99
        expected = 0.5 * 997 * 0.8 * 0.45 * u * u if u else 10
        print(f"u={u:.1f}, expected={expected:.6f} N, observed={force[0]:.6f} N")
```

Official 2.3.0 prints observed 0.017946 / 0.071784 / 0.287136 / 1.148544 N and
9.999999 N for the 10 N thrust check; the patched build prints 1.794600 / 7.178401 /
28.713602 / 114.854408 N and 9.999999 N.
</details>

**Separate note (not part of this bug):** below 30 Hz the physics integrates less
time than the client clock reports. `AHolodeckWorldSettings::FixupDeltaSeconds` makes
the world delta `1/ticks_per_sec` and the Python clock advances `1/ticks_per_sec`,
but UE 5.3 integrates `min(DeltaSeconds, MaxPhysicsDeltaTime)` without substepping
(`FChaosScene::SetUpForFrame`), default `MaxPhysicsDeltaTime = 1/30 s`. Measured with
gravity, a known thrust, the damping ratio and kinematics: physics/client step
0.6666667 at 20 Hz, 1 within 1.7e-7 at 30, 40, 60, 100 and 200 Hz (official and
patched builds). The scenario docs give the default (30) but no minimum; documenting
`ticks_per_sec >= 30` or raising `MaxPhysicsDeltaTime`/enabling substepping with
`AdjustTPS` would avoid the silent mismatch. With the corrected drag the step size
also matters numerically: explicit integration of the BlueROV2 drag (K/m = 15.6 1/m)
from 2.5 m/s reverses the velocity in one step at 30 Hz and under-predicts the
first-step speed by 15% at 100 Hz and 4% at 200 Hz versus the exact solution.

Not claimed: anything about the realism of Cd = 0.8 and A = 0.45 m² for the
BlueROV2 — with the fix those coefficients make station keeping saturate the
thrusters above ≈0.67 m/s of current.

Tooling, raw data (hashed JSONL), build manifests and the patch:
https://github.com/AndreaBedei1/HoloVirtualBattery/tree/fix/verified-holoocean-drag-backend
(`docs/verified_backend_report.md`, `sources/verified_backend/`). Happy to open a PR.
````

The numbers in the comment come from
[`sources/verified_backend`](../sources/verified_backend): `drag_before_after.csv`,
`autodrag_*/report.json`, `upstream_test_*.json`, `minimal_repro.json`,
`chain_*/chain_closure.json`, `timestep_*/report.json`
([verified backend report](verified_backend_report.md), §10–§18 and §24).

## 2. Proposed pull request (not opened)

**Title:** `Fix native buoyant-agent drag force unit conversion`

**Base:** `develop`. **Changes:** exactly
[`patches/holoocean-develop-drag-units.patch`](../patches/holoocean-develop-drag-units.patch)
(SHA256 `3f5508dfa7b40690884d1cb0266399b0edc84cf91fb828d3e6d90a448711c02e`, against
`f3d1230c4050b57982d122fa2093e1097c21111a`): one `DragForce *= UEUnitsPerMeter;` in
each of the three vehicle-level drag paths, and the `test_currents_underwater`
expectation 0.06320982 → 6.320976 m/s² on X, Y and Z. No refactor, no other files,
no HoloEnergy code. The per-triangle wave model of `develop`
(`CalculateSubtriangleForces`) is a separate model with its own coefficients and is
not touched.

**Before opening:** regenerate the two `test_currents_surface` expectations
(currently 0.00679156 and 0.00680996 m/s², empirical, `rtol=2e-2`) on a patched
`develop` build with the TestWorlds package, or ask the maintainers to do it in the
PR; build and run `develop` with the patch (this project ran only 2.3.0).

**Body:**

> The vehicle-level drag in `AHolodeckBuoyantAgent` is computed in newtons (SI
> inputs: m/s, kg/m³, m²) and passed directly to `AddForceAtLocation`, whose raw unit
> is kg·cm/s². Gravity, buoyancy and thrusters convert N to UE units; the drag does
> not, so it is applied at 1/100 of its own equation (see #368).
>
> This multiplies the SI drag by `UEUnitsPerMeter` in `ApplySurfaceBuoyancy`,
> `ApplyUnderwaterBuoyancy` and `ApplyWavelessForces` (magnitude only: `RelativeVel`
> is already in UE world axes, so `ConvertLinearVector` would reflect Y twice), and
> updates `test_currents_underwater`, whose expected 0.06320982 m/s² is exactly 0.01
> of `0.5·ρ·Cd·A·u²/m·(1 − c·dt)` for HoveringAUV, to 6.320976 m/s².
>
> Verified on Ocean 2.3.0 (Windows, BlueROV2 scheme 0) by rebuilding Holodeck.exe
> from v2.3.0 with UE 5.3.2 and the official toolchain (MSVC 14.44.35207): the
> unpatched control rebuild gives bit-identical audit data to the official binary;
> the patched build applies 1.0000000074 of the SI drag over 153 current cases
> (60/100/200 Hz, ±X/±Y/±Z, yawed vehicle) and 1.0000002 for a vehicle moving in
> still water; 10 N thrust, gravity and neutral buoyancy are unchanged; the
> HoveringAUV `test_currents_underwater` sequence gives 6.32097578 m/s². The same
> one-line change is applied here to the three `develop` drag paths.
> `test_currents_surface` values {regenerated values / to be regenerated with TestWorlds}.
> Audit tooling and data: AndreaBedei1/HoloVirtualBattery,
> branch fix/verified-holoocean-drag-backend, `sources/verified_backend`.
>
> Not addressed here: hydrodynamic coefficients; the physics-step cap below 30 Hz
> (separate note in #368).

## 3. Publication checklist (requires the author's explicit authorization)

1. Push the branch of this repository (the comment links to it).
2. Post section 1 as a comment on #368, unchanged.
3. For the PR: fork `byu-holoocean/HoloOcean`, branch from `develop`, apply
   `patches/holoocean-develop-drag-units.patch`, build and run the patched
   `develop`, regenerate the surface expectations, then open the PR with the title
   and body above.
