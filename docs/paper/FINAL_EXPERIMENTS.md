# Final experiment set (EXP1–EXP10)

This file fixes the design before the final runs, so later edits show up in git history. Every
paper-critical run starts from a clean committed tree. Each result records the commit, the backend
hashes and a SHA256 of every resolved configuration and every trace. The review identifiers (B-01,
F-03, ...) refer to `docs/reviews/`.

Scope of every native result: HoloOcean 2.3.0 with the drag-units patch (`C:\HOB\packages\patched-after`,
see `docs/holoocean_patched_build.md`), 100 Hz, BlueROV2 body with `Perfect` mass properties, isotropic
quadratic drag $\tfrac12\rho C_D A|v_r|v_r$ at the centre of mass plus Unreal linear damping
$v \leftarrow v(1-c\,\Delta t)$ on the world velocity. These hydrodynamics are simulator properties and
are not a validated BlueROV2 model (EXP9, EXP10 part 1 and part 4).

| ID | Question | Script | Runs | Output |
| --- | --- | --- | --- | --- |
| EXP1 | Does the backend implement its declared SI drag and integrate the client step? | `tools/check_holoocean_backend.py` (patched build, plus the unpatched control build) | 2 | `experiments/results/final/backend/` |
| EXP2 | Are component values reproduced exactly from their records (T200 tables, sensors, modems)? | `tests/` (input traceability, not validation) and `tools/build_parameter_audit.py` | – | `data/evidence/final_parameter_audit.*` |
| EXP3 | How do actuator count and layout (4/6/8) affect feasibility and propulsion energy? | `experiments/run_final_experiments.py` | 18 | `logs/final/results/EXP3` |
| EXP4 | How does horizontal thruster angle (30°/45°/60°) affect head-on and sway cost? | same | 4 | `.../EXP4` |
| EXP5 | Station keeping and transit energy versus current (0, 0.2, 0.4 m/s) | same | 4 | `.../EXP5` |
| EXP6 | Payload suites, continuous versus mission-phase scheduling | same | 5 | `.../EXP6` |
| EXP7 | Communication energy: acoustic and optical links, ACK, multihop, flooding, relays | `experiments/run_comm_matrix.py --seeds 1..20`, `experiments/run_crosslayer.py` | 9 configurations (A, A2, B, B2, C, C4S, C4F, E, F) × 20 seeds; 8 cross-layer strategies | `experiments/results/final/comm_matrix.json`, `crosslayer.json` |
| EXP8 | Battery fidelity L0 versus L1; voltage-limited operation at low SOC | `experiments/run_final_experiments.py` | 2 | `.../EXP8` |
| EXP9 | How far is HoloOcean surge resistance from published BlueROV2 measurements? | `experiments/run_offline_campaign.py` (E4) | offline | `experiments/results/offline/` |
| EXP10 | Sensitivity: drag model, acoustic modem settings and interface, allocator, drag anisotropy | `experiments/run_sensitivity.py` | offline (part 2 uses the EXP7 cross-layer durations) | `experiments/results/final/sensitivity.json` |

## Native design (EXP3–EXP6, EXP8)

- **Current convention.** Currents are head-on (`HEAD_ON = -1`, the water meets the bow) or oblique at
  45° from the bow quarter. Horizontal thrusters then work on the forward T200 branch. A stern
  current would put them on the reverse branch, which needs 1.38–1.42× the power for the same force
  (review B-01).
- **Station keeping.** 90 s per run. The last 30 s are the steady-state window and are reported apart
  from the transient (review F-03).
- **Transit.** Outbound leg, stop, hold, yaw and return, with a 10 s hold at the start point, so that
  every transit ends at rest at the same place (review B-08). The tracking error at the end is
  reported. A run counts as "request met" only without allocation residual, native saturation or
  derating.
- **Layouts.** L8-HV (simulator-exact, direct mapping), L6-STD, L4-H45, L4-2H2V, L8-VEC30 and the
  angle variants L8-HV-a30 and L8-HV-a60. All except L8-HV are wrench-equivalent virtual layouts on
  the native body and are limited to the wrench that body can apply (review E-06). Geometry grades:
  L8-HV A, L6-STD C, L4-H45 C, the others D (benchmark designs).
- **Controller.** The same wrench PID for every run. It uses simulator ground truth for state
  (review D-08: navigation sensors are not in the loop; their power is charged only when the suite
  includes them).
- **Payload schedules (EXP6).** `inspection-at-site` and `ai-at-site` switch the payload on only in
  the `stop`, `hold_turn` and `yaw` phases. OFF means the rail is gated (0 W). This is a scenario
  choice, not evidence.
- **Battery.** L1 Rint with the cell-derived resistance (proxy, grade C). L0 is the energy bucket at
  nominal voltage. Low SOC starts at 0.03.

## Communication design (EXP7)

- DESERT runs only in the project's own container on port 5571 (`manage_engine=False`). The same 20
  seeds are used for every configuration. Delivery is pooled over seeds with a Wilson 95 % interval;
  energy is given as mean, minimum and maximum over seeds.
- Optical links run at 5 m, inside the LUMA 250LP rated 7 m range, at 250 kbit/s (review D-03).
- The acoustic PHY is the DESERT 4.8 kbit/s model, not the S2C M 18/34 PHY (13.9 kbit/s). EXP10
  part 2 reports the share at the device bitrate and at every published TX setting (review D-01).

## What these experiments do not show

- No result is a validation against a physical vehicle: no measured BlueROV2 mission energy was
  available (review G-01).
- The comparison with simple baselines (speed-cubic and constant power) is model versus model.
- Equal energy of layouts that share the four vectored horizontals is a property of the decoupled,
  neutrally buoyant simulated body (review B-03).

## Reproducing the final runs (review J-04 to J-07)

What a third party needs, and what is not yet public:

1. **HoloOcean.** HoloOcean 2.3.0, rebuilt with the drag-units patch (`patches/`, procedure in
   `docs/holoocean_patched_build.md`, `tools/build_patched_holoocean.py --engine-kind launcher`, Unreal
   Engine 5.3.2). The built package is local and not distributed. Its SHA256 is recorded in every
   summary (`provenance.backend`). Before any run, `tools/check_holoocean_backend.py` must report PASS
   at 100 Hz (EXP1).
2. **Interpreter.** Python 3.10 with HoloOcean 2.3.0, `holo_desert` 1.1.0 (HoloWithDesertCommunications
   at 635b99a) and numpy 1.26.4. See `experiments/results/final/environment.json` and
   `environment_freeze.txt`. Figures use matplotlib 3.9.4: other versions change the bytes, not the
   data.
3. **DESERT.** The `holo-desert-engine:4.0.0-v2` image (id in `environment.json`), built from
   HoloWithDesertCommunications. Run it as a separate container on a non-default port, and use
   `NetworkSession(manage_engine=False)`.
4. **Commands**, from a clean checkout of the recorded commit:
   - `run_final_experiments.py --binary <patched Holodeck.exe> --source-dir <patched sources>`. Use
     `--runs <labels>` to split the run list over at most two processes.
   - `run_comm_matrix.py --port <port> --seeds 1 ... 20 --output experiments/results/final/comm_matrix.json`.
   - `run_crosslayer.py --binary <patched> --port <port> --output experiments/results/final/crosslayer.json`.
   - `verify_final_energy.py` (needs the 100 Hz traces in `logs/final/full`).
   - `analyze_final_experiments.py`.
   - `run_sensitivity.py`.
   - `make_final_figures.py --output-dir <dir>`.
   Default seeds and ports are in each script's `--help`.
5. **Not public yet.** The 100 Hz traces (74 MB) are git-ignored, so the energy verification can be
   repeated only by rerunning or from an archive. Publishing them, for example as a release asset,
   needs the author's decision.
