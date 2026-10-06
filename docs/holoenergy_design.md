# HoloEnergy v0.1 design and usage

## Scope and architecture

External Python package wrapping an already-created environment. No hardware
transport, MAVLink connection, core patch or real-thruster action exists.
One controlled agent with direct per-thruster actions is supported. PID position
commands, custom acceleration actions and multi-agent energy inference are excluded.

    Requested forces + payload states + hotel load
                     |
    Thruster lookup <----- terminal voltage
                     |          ^
    Converter losses |          |
                     v          |
    Power manager <----- battery L0 / Rint limits
                     |          |
       Reduced action           I²R (+ optional entropy)
                     |          |
         HoloOcean.step     thermal node --> temperature feedback
                     |
       Model integration, Energy state, JSONL/CSV

Battery-terminal output is:
P_total=P_propulsion+P_payload+P_hotel+P_conversion_loss.
Propulsion power is electrical drive input; payload/hotel are device-rail power.
Battery ohmic loss is separate: P_ocv=P_total+I²R. Do not add it twice.

The Energy state includes all requested SOC, voltage, current, power breakdown,
temperature, cumulative terminal Wh, derating and battery-state fields. Extra
fields cover available SOC, internal/conversion losses, requested/available/unmet
power, thruster/sensor arrays, requested/applied action, auxiliary service,
cutoff reason, calibration and dynamics-consistency flags.
State priority is CUTOFF, THERMAL_DERATING, POWER_LIMITED, LOW_SOC, NORMAL.

## Installation and checks

Python >=3.10 is required; workspace validation uses 3.13.12. From a fresh checkout:

    py -3.13 -m venv .venv
    .venv\Scripts\python.exe -m pip install -e ".[dev]"
    .venv\Scripts\python.exe -m pytest -q

Alternatively: uv sync --extra dev --locked. The committed uv.lock pins the
resolved dependency graph. The only energy-model runtime dependency is PyYAML.
HoloOcean and its numpy/world dependencies must be installed independently using
its official instructions; package import does not launch a simulator.

## Configuration format

configs/bluerov2_energy.yaml includes the packaged vehicle profile.
Nested YAML/JSON profiles use package:batteries/...yaml or local relative paths.
Local paths resolve against the containing file; nested mappings merge and lists
replace. Unknown fields, nonfinite/negative physical values, invalid curves and
cyclic inclusions fail explicitly.

Required root inputs: schema_version=1, simulation.dt_s, battery, thermal,
propulsion and explicit hotel_load.constant_W. Sensors may be omitted.
Converters default to ideal efficiency; logging and action scaling default off.
Marked placeholders require allow_placeholders=true, emit warnings and remain
listed in every log and metadata sidecar.

Example overrides:

    profile: package:vehicles/bluerov2_heavy.yaml
    simulation:
      dt_s: 0.05
    thermal:
      water_temperature_C: 12.0
    sensors:
      ImagingSonar:
        initial_state: "OFF"
    logging:
      enabled: true
      format: csv
      path: logs/mission.csv
    power_manager:
      apply_derating_to_actions: false

Log paths are relative to the working directory. Each logger starts a new file
at its configured path. Choose distinct paths to retain separate runs.

## Wrapper usage and timing

    import holoocean
    from holoenergy import EnergyAwareEnv

    base = holoocean.make("YOUR_INSTALLED_SCENARIO")
    base.reset()
    env = EnergyAwareEnv(base, config_path="configs/bluerov2_energy.yaml")
    state = env.step(action)  # eight main-BlueROV2 thruster forces
    print(state["Energy"]["soc"])
    env.close()

Verify native scenario control scheme and action units. Set simulation.dt_s to
exactly 1/ticks_per_sec; this is simulated time, independent of GUI frame rate.
No dt or electrical command mapping is guessed.

Action scaling defaults to false. Enabling it requires control_contract, or a
backend energy_action_contract, declaring:

    contract = {
        "agent_type": "BlueROV2", "control_scheme": 0,
        "action_units": "force_N", "thruster_count": 8, "dt_s": 0.05,
    }
    env = EnergyAwareEnv(base, config=config, control_contract=contract)

The contract is a caller assertion established from the actual scenario, not
automatic inspection of undocumented simulator internals. The examples verify
one BlueROV2 agent and scheme 0, then set the scenario tick rate and call reset.
The wrapper additionally checks the actual HoloOcean agent class and public
action-space shape, and respects get_low()/get_high() limits when selecting
the derated vector. This catches runtime switches away from direct control
without relying on private control-scheme fields.

step(action,ticks=N) advances and replans once per simulated tick. It returns
the final simulator state. Energy power, voltage and current are interval means;
SOC/temperature/sensor states are end states; cumulative Wh integrates all ticks.
Mean V times mean I need not equal mean P. Derating/service factors are the minimum
over the call, and applied_action is the last action.

reset() resets the simulator and battery/thermal/payload episode. Backend failures
fault the wrapper until reset, because the simulator clock may have advanced.
Completed ticks before a failure are logged with step_completed=false.
tick, act and set_ticks_per_sec through the wrapper are blocked to prevent bypass.
Direct use of env.env remains the caller's responsibility.

## Models and extension points

- EnergyBucketBattery: ideal L0 bucket.
- RintBattery: L1 OCV, Coulomb-counted reference SOC, effective DC resistance,
  sag and current/power/capacity limits. L2 RC polarization is deferred.
- ThermalModel: one pack-average node, exact held-input heat/cooling update,
  optional entropy curve and configured operational limits.
- ThrusterModel: voltage-dependent forward/reverse power versus command or force.
- PayloadComponent: OFF/IDLE/ACTIVE/STARTING/PINGING with temporal duty accounting.
- HotelLoad: constant plus named configurable components; change a known component
  with env.hotel.set_component_power(name,power_W).
- ConverterModel: configured rail efficiency.
- PowerManager: nonlinear action allocation and coupled electrical load solution.

Equations, coefficient provenance, assumptions and selection rationale are in
[scientific_sources.md](scientific_sources.md).

## Adding batteries and temperature data

Create a pack-level profile with model=rint, capacity_Ah, nominal_voltage_V,
initial_soc, internal_resistance_ohm, cutoff_voltage_V, max_current_A and
ocv_curve. The OCV curve must be monotone, include SOC 0 and 1, and contain
relaxed pack measurements. Add source URL/DOI, test protocol and calibration
domain in metadata. Demo pack knots are not measured OCV.

Temperature factor inputs are capacity_temperature_curve,
resistance_temperature_curve and max_current_temperature_curve, each containing
increasing-temperature [temperature_C,factor] pairs. OCV surfaces use
ocv_temperature_curves, a list of mappings with temperature_C and curve, where
curve contains [reference_soc,pack_voltage] pairs. Optional entropy_curve_V_per_K
contains [reference_soc,dU_oc/dT] spanning SOC 0–1.

The default factor tables are reference identities only. Replace them with
measurements before claiming cold-water accuracy. Keep SOC reference and
accessible capacity conventions consistent when importing data. Only mark
metadata.temperature_characterized=true only after characterization and remove
only measured placeholder fields. Held-out validation is a separate status.
Logs preserve unresolved limitations.

## Adding sensors and thrusters

Identify the exact hardware revision and official sheet first. Start with
profiles/sensors/custom_payload.yaml for unidentified DVL or other payloads.
Set power for used states; undocumented null values raise when selected.
OFF means a physically disconnected rail, not software standby.

env.set_payload_state("ImagingSonar","STARTING") applies startup for its configured
duration then ACTIVE. Selecting ACTIVE directly bypasses startup. PINGING without
frequency is one pulse then ACTIVE; frequency_Hz repeats pings with active_W
between them. ping_W is total instantaneous ping-state power, and
ping_duration_s*frequency_Hz must not exceed one.
These electrical states do not disable HoloOcean rendering or invalidate sensor data.

Add thruster voltage_tables with forward/reverse rows: command 0–1, force_N,
power_W, zero anchors and monotone force/power. Use propulsion.thruster for one
shared profile or propulsion.thrusters for heterogeneous individual profiles.
No T200 coefficients are hardcoded in the physical model.

Reproduce extraction from the unchanged official T200 workbook:

    .venv\Scripts\python.exe tools\import_t200.py
    git diff --exit-code -- holoenergy/profiles/thrusters/bluerobotics_t200.json

## Examples

Explicit energy-only synthetic backend, with derating enabled:

    .venv\Scripts\python.exe examples\bluerov2_energy_demo.py --backend synthetic
    .venv\Scripts\python.exe examples\bluerov2_sensor_payload_demo.py --backend synthetic

The synthetic backend has no ROV physics and cannot validate mission completion.
Actual HoloOcean runs require an installed native single-BlueROV2 scenario:

    <HoloOcean-Python> examples/bluerov2_energy_demo.py --backend holoocean
    <HoloOcean-Python> examples/bluerov2_sensor_payload_demo.py --backend holoocean

The default native scenario is configs/bluerov2_holoocean.json, using Ocean /
SimpleUnderwater with a BlueROV2 and a small camera, plus pose/velocity sensors.
The sonar energy component is an electrical proxy; no imaging sonar sensor is
rendered by this lightweight scenario. --scenario selects another native JSON.
Default backend is HoloOcean; startup requires it in the **selected interpreter**.
Missing simulator/world or invalid scenario fails explicitly, without a synthetic
fallback. Options include --steps, --config, --output-dir, --log-format csv and
--show-viewport (offscreen by default).

This machine's actual HoloOcean Python is
C:/Users/Andrea/miniconda3/envs/holoocean_joystick/python.exe, version 3.10.20.
HoloOcean 2.3.0 is installed there; the Python 3.13 energy-only .venv does not
contain it. HoloEnergy is also installed as an editable package in the Conda
environment without replacing HoloOcean or its dependencies.

The native opt-in check compares actual pose displacement with and without
action scaling under a deliberately imposed 8 A current limit:

    <HoloOcean-Python> examples/verify_holoocean_integration.py --backend holoocean --steps 60 --output-dir logs/holoocean

This test cap is an experimental simulation intervention, not a pack rating.
It checks clock increments, available current/power, actuator bounds, physical
motion differences and simulator-process cleanup. It is excluded from automatic
unit-test launching; run it explicitly when an installed world/GPU is available.

## Logs, limits and core hooks

One JSONL/CSV row per wrapper step; CSV dict/list cells are JSON. The sidecar
.metadata.json stores run UUID, version, fully resolved configuration, SHA256 and
warnings. Run/episode/step disambiguate resets. Preserve sidecars with mission logs.
dynamics_energy_consistent=false flags retained simulator thrust during a modeled
shortage in accounting-only mode.

No core hook is needed for direct action scaling. PID/custom dynamics would need
an authoritative public hook exposing each applied thruster command before
physics, agent identity and simulated dt, plus controller anti-windup feedback.
These hooks were not guessed. Propose a separate minimal patch only after
inspecting an installed core revision.

Rint parameters are held over each tick; perform dt refinement. Loaded cutoff
can be detected at a tick endpoint with slight intra-tick overshoot. Static
thruster curves omit inflow/interference. One thermal node cannot predict hottest
cells. Auxiliary fractional service is accounting, not a brownout/reboot model.
Temperature maps, DC resistance, hotel and thermal parameters remain uncalibrated.

See [verification.md](verification.md) for performed checks and
[validation_protocol_bluerov2.md](validation_protocol_bluerov2.md) for future
hardware calibration. Native HoloOcean integration and both demos now run on
this machine; these checks do not calibrate the battery/payload energy parameters.

## Consolidated v0.1 contracts

`fidelity_level` resolves from battery.model and must agree if declared. L0 keeps
a fixed temperature reference and omits thermal feedback; L1 uses the existing
one-node dynamics. `with_fidelity` makes the same-mission baseline explicit; its
nominal Ah×V conversion is uncalibrated usable energy. L2 RC/hysteresis/multi-node
models are future work. Optional static R(SOC,T) tables add no polarization state.

`resistance_soc_temperature_curves` is a list of temperature_C/curve mappings,
where each curve is a common increasing reference-SOC grid with absolute ohms.
SOC must span 0–1; values need not be monotone. Linear SOC then temperature
interpolation clamps and flags domain violations. When configured, the surface
supersedes internal_resistance_ohm and resistance_temperature_curve. Without it,
the previous R(T) calculation remains. OCV and capacity examples are unchanged.

Sensor `power_policy` defaults to manual. Sensor-linked mode is explicitly
unavailable: public HoloOcean 2.3 sensor data/capture APIs do not establish hardware
electrical states. The wrapper does not infer power from returned arrays or render
frequency. Use set_payload_state and a correctly identified hardware profile.

Payload `load_kind` defaults to continuous, retaining fractional service. For a
user-characterized discrete device, optional brownout fields are
minimum_bus_voltage_V, minimum_supplied_fraction, behavior (latch_off or
auto_restart) and explicit restart_delay_s for auto_restart. Thresholds have no
camera/sonar defaults. A tripped device is disconnected for the interval and
remaining loads are replanned; logical state is retained and timed state progress
pauses. Auto-restart retries at tick boundaries after the configured wait. Manual
set_state/reset clears the latch. This rail-off policy assumes off_W=0 and is not
exact reboot, regulated-rail transient or sensor-data validity modelling.
Computer and other discrete electronics can be named payloads, avoiding duplicate
hotel accounting. Above a minimum fraction below 1, fractional accounting may
remain approximate. Dynamics consistency flags concern propulsion commands.

Thruster metadata explicitly identifies static/bollard characterization. Inverse
force-power lookup requires support in both adjacent voltage tables; conservative
force limits cover the feasible voltage interval. Demand outside supported force
is capped for the request estimate and flagged requested_power_is_capped; this is
not extrapolated hardware consumption. Applied-action modelling stays in-domain.
No inflow correction is implemented.

Offline comparison, sensitivity/Monte Carlo, identified-map CSV import, manifest
checking and synchronized-log evaluation are in holoenergy.analysis. Formats,
CLI/API contracts, sampling limitations and calibration status are documented in
[experimental_tooling.md](experimental_tooling.md). The wrapper's logger metadata
is available even when file logging is disabled; enabled sidecars finalize output
hashes on close. Multi-tick rows retain voltage/current/temperature extrema in
addition to interval means. For event/duration studies, use one logged row per tick.
