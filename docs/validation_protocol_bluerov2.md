# BlueROV2 calibration and validation protocol

Planning document only. No hardware connection or real thruster action is executed.

## Hardware and measurement boundaries

Record Heavy vehicle/thruster ordering, T200/ESC revision, pack chemistry/serial/
cycle history, enclosure, wiring, converter boards and firmware. Identify camera,
sonar, DVL, controller and computer by exact model/revision. Preserve manufacturer
sheets and data hashes. Avoid counting camera/lights/ESC idle twice across loads.

Acquire synchronized terminal V(t), I(t), applied PWM/commands, vehicle states
and payload modes from ArduSub/BlueOS/QGroundControl/DataFlash or equivalent logs.
Calibrate onboard V/I scale and offset against a traceable meter first. Record
units, sign, timestamps, sample rates and measurement uncertainty. Telemetry SOC
is not independent ground truth without its own calibration.

Measure pack, water and enclosure temperature and sensor placement/lag.
The pack thermistor is a local proxy, not every cell's core temperature. Use
per-rail power measurement where possible. Resolve ping/startup separately from
steady loads. Anti-alias before resampling; integrate energy on original timestamps.

## Data separation

Preassign different cycles/missions to calibration and validation, stratified by
temperature, SOC, payload and maneuver. Do not randomly split adjacent samples
from one mission. Reserve independent temperatures and mission types. Define
acceptance thresholds from instrumentation uncertainty and mission reserve needs
before evaluating the validation set. Archive parameter domains, protocol,
software revision, raw/processed data hashes and uncertainty intervals.

## Battery and temperature characterization

1. Establish initial SOC with a documented full-charge/reference/rest protocol.
   Charging uses authorized personnel and suitable equipment; HoloEnergy is
   discharge-only.
2. Measure reference and usable capacity at controlled temperatures and specified
   rates/cutoff within manufacturer limits. Maintain a consistent reference SOC
   basis when reporting lower-temperature accessible capacity.
3. Measure relaxed OCV across reference SOC; rest duration must be justified by
   observed relaxation. S3 used one-hour rests and 5% SOC steps for its cell,
   not universally for every BlueROV2 pack.
4. Fit effective pack DC R(SOC,T) from controlled pulses and inspect relaxation
   residuals. Do not substitute 1 kHz cell AC impedance for pack DC resistance
   or cell current ratings for pack ratings.
5. Fit capacity accessibility and sag jointly to avoid counting loaded-cutoff
   capacity loss twice. Remap temperature-specific OCV to reference SOC.
6. Add an RC branch only when held-out transient error justifies more parameters.
   Entropy dU_oc/dT requires equilibrated temperature-controlled OCV measurements.

Thermal tests use the actual closed battery enclosure. Fit k and C_th using
independent heating/cooling records with identified I²R. Cooling alone identifies
k/C_th, not both parameters independently: use known heating or independent
heat-capacity data. Record enclosure material, air gaps, contact paths and flow.

Repeat at multiple water temperatures and durations. Inspect equilibrium,
transient and sensor-lag errors and uncertainty. Multiple time constants or
systematic surface/core lag justify a second enclosure node rather than an
arbitrary efficiency correction. Average-temperature accuracy does not establish
hot-cell safety. The demo's 40 C derating onset is a policy placeholder.

## Isolated component loads

- Electronics idle: computer, flight controller, Ethernet/switch and ESC idle.
- Camera: powered OFF, idle, streaming, startup, compression/frame rate and lighting.
- Sonar: idle, scans, startup and ping duty with recorded mode/range/rate.
- DVL: exact device states; leave profile unconfigured until identified.
- Lights/auxiliaries: isolate each state and repeat at representative voltages.
- Converters: compare input/output power versus load, input voltage and temperature.

Thruster sweeps are planned only for authorized personnel in a suitable underwater
facility, with the vehicle secured and manufacturer constraints followed.
Run real thrusters only in water. HoloEnergy does not control these tests.
Measure forward/reverse and mounted interactions; record inflow and actual PWM.

## Maneuvers and held-out missions

Measure electronics idle, hover, surge, yaw, vertical motion and complete
representative missions, with consistent initial charge/temperature. Include
current-limited segments and sonar OFF/ACTIVE comparisons. Record requested and
realized control. Repeat missions across SOC and the operational temperature range.
Preserve reserve policy separately from physical limits. Perform numerical dt
refinement on identical command histories before attributing errors to parameters.

## Metrics

- Power MAE=mean(abs(P_pred-P_meas)).
- Power RMSE=sqrt(mean((P_pred-P_meas)²)).
- Voltage/current/temperature MAE and maximum error; thermal peak/time error;
  cutoff and derating event-time errors.
- Total terminal E_meas=integral(V_meas*I_meas*dt)/3600. Report absolute Wh error
  and relative error (E_pred-E_meas)/E_meas for E_meas>0.
- Final reference SOC error against independently calibrated charge accounting,
  with reference-capacity convention and drift uncertainty.
- Mission completion, completion time, path error and unmet thrust under
  energy-aware dynamics. Synthetic energy-only demos cannot establish completion.
- Reserve violation events, duration and minimum margin against a predefined
  SOC/energy reserve. Also report voltage/current/temperature violations.

Report per maneuver, payload, SOC and temperature, with uncertainty across repeated
missions. Fit only on calibration data; evaluate acceptance on reserved validation.
Publish residual plots and parameter uncertainty in addition to aggregate Wh.

## Publication archive

Preserve calibrated profiles, equations, source DOI/URLs and simplifications,
instrumentation uncertainty, code/core versions, hashes, log sidecars and independent
validation metrics. Replace current pack-temperature, electrical, thermal and hotel
placeholders before claiming quantitative BlueROV2 endurance or thermal accuracy.
