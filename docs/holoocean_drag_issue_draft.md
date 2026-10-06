# Draft only — Native buoyant-agent drag misses N-to-UE force magnitude conversion

Prepared 2026-10-06. **Not submitted.** This evidence could be added to
[existing issue #368](https://github.com/byu-holoocean/HoloOcean/issues/368)
instead of opening a duplicate.

## Version and source

Python client and Ocean package 2.3.0 on Windows, `SimpleUnderwater`, native
BlueROV2 control scheme 0. Official `v2.3.0` commit
`49e70552dfd97273b7dfbe755fbe65d7738b24b7`. The inspected local critical C++
files and installed client modules match the official tag byte for byte.
The exact build commit of the cooked Ocean executable is unknown; runtime
identity is SHA256
`8c206c9cc05c640fb2efea6bd43bda33c585536ab16a931c55780855e7602253`.

Affected source: `engine/Source/Holodeck/HolodeckCore/Private/HolodeckBuoyantAgent.cpp`,
lines 87–96 in that tag. Gravity/buoyancy convert newtons to centinewtons;
drag is passed directly to `AddForceAtLocation`.

## Dimensional analysis

Velocity is `GetUnrealWorldVelocity()/100` in m/s, current is m/s, density
997 kg/m³, Cd 0.8 and BlueROV2 area 0.45 m². The expression
`-0.5*rho*|v_rel|²*Cd*A*normal(v_rel)` yields N. Raw UE physics force with
length cm and mass kg requires kg·cm/s², hence a magnitude factor 100.
Relative velocity is already in UE world axes; a second handedness conversion
would be incorrect.

## Minimal reproduction

Only HoloOcean and NumPy are needed; no HoloEnergy, PID or controller.
Use 100 Hz to stay below the physics step cap. The source linear damping is
1/s, so the first-step force from rest is `mass*a/0.99`. A separate known
net 10 N pulse verifies this conversion rather than fitting a drag coefficient.

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

## Expected and measured

Independent campaign: 17 cases, 60/100/200 Hz, three repetitions, eight
steps per case. Known 10 N force maximum error after damping removal:
6.19e−7 N; gravity 9.8 m/s² maximum error 7.17e−7 m/s². No collisions,
neutral zero-current vehicle remains stationary, negligible angular velocity.
Sign and world axes checked with ± currents and yaw 90°.

| Current m/s | Expected drag N | Measured `m*a` N at 100 Hz | Inferred applied drag N |
| ---: | ---: | ---: | ---: |
| 0.1 | 1.794600 | 0.017766539 | 0.017945999 |
| 0.2 | 7.178400 | 0.071066157 | 0.071783997 |
| 0.4 | 28.713600 | 0.284264627 | 0.287135987 |
| 0.8 | 114.854400 | 1.137058507 | 1.148543946 |

Mean inferred/source-SI ratio: **0.009999999703068724**. All three doubling
ratios are approximately 4: quadratic shape correct, absolute magnitude wrong.
The 10 N reference produces `m*a=9.8999994 N` and reconstructed force about
10 N. The drag/thruster normalized ratio also gives 0.01 without using a fitted
damping correction. A diagnostic at 20 Hz fails the absolute references and
is retained as inconclusive: it is consistent with the UE5.3 default physics
step cap of 1/30 s. It must not be used with the 100 Hz reconstruction formula.

## Proposed minimal fix and verification status

After computing the SI drag vector, before `AddForceAtLocation`:

```cpp
// SI newtons in UE world axes: scale magnitude without reflecting Y.
DragForce *= UEUnitsPerMeter;
```

Do **not** use `ConvertLinearVector(DragForce, ClientToUE)` because the axes
have already been converted. This proposal leaves gravity, buoyancy, thrusters
and coefficients unchanged. Apply/reverse checks passed on an isolated source
copy. No usable UE5.3 development installation was available for a separate
rebuild; **no after-patch runtime results are claimed**. The installed binary
was not modified. Other native buoyant agents share the base path but were
not independently runtime-audited; Fossen is a separate dynamics contract.

The full audit, raw hashed JSONL/CSV, source fingerprints and reproducible
tooling are in `docs/holoocean_drag_units_report.md` and
`sources/holoocean_drag_audit/` on the HoloVirtualBattery investigation branch.
This verifies implementation consistency, not measured BlueROV2 hydrodynamics.
