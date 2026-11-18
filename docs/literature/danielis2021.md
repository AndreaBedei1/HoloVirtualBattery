# Danielis et al. 2021 - energy + acoustic comms simulation model for AUVs

Citation: Danielis, Parzyjegla, Mohamed Ali, Sill Torres, WMU J Maritime Affairs 21:89-107 (2022; online 2021), doi 10.1007/s13437-021-00253-z. Page numbers are journal pages (p.89 = PDF p.1). Table 2 and Fig. 2 were checked on rendered page images, not only text.

## 1. Characterisation

- Type: simulation-model paper, proof of concept (Sec. 5, p.105). The energy model is a minor part (Sec. 3.1, 4.1); most of the paper is the acoustic channel / packet-reception model (Sec. 3.2, 4.2).
- Tool chain (Abstract p.89; Sec. 3 p.93-94): OMNeT++ with INET. Extended INET modules: WirelessHost, ApskScalarRadio/Transmitter/Receiver, ApskErrorModel, ApskScalarRadioMedium, ConstantSpeedPropagation, ScalarAnalogModel, InterpolatingAntenna. The abstract AUV module extends SimpleModule with energy, comms, sensor and movement submodules (p.94). No hydrodynamics engine, no Gazebo/HoloOcean/ROS.
- Vehicle: generic "advanced AUV" with a survey head; Table 1 (p.98) lists sensors (DVL, camera, multibeam, side-scan, sub-bottom profiler, surround sonar). SeaCat (Atlas Elektronik) is cited only as context (p.90). No vehicle mass, dimensions, drag, thruster type or battery capacity/voltage is given anywhere.
- Motivating application: UXO detection with cooperative AUVs, Baltic/North Sea (p.90).
- Parameter provenance: only "theoretical values from handbooks" (p.105); EvoLogics 2020 for modem "above 60 W" (p.90); frequency bands from Shin and Park 2008 (p.101). No per-parameter citation.

## 2. Energy model (Sec. 3.1, p.94-95)

Structure: one power state machine (PSM) per subsystem. Subsystem code fires transition events; the PSM sets that subsystem's instantaneous power; the BatteryModule "integrates the subsystem's power signal over time and sums up" all subsystems (p.94). Remaining charge and remaining mission time can be predicted (p.95). Fig. 1 (p.94): MissionModule -> commands -> instrumented subsystems / PSMs -> BatteryModule. A "base load" covers anything not instrumented (p.94); its value is NOT given.

No equations are printed. Implicitly E = sum_k integral P_k(state_k(t)) dt with piecewise-constant P.

### Propulsion
- Thrusters are mentioned (bow and vertical, p.98; "thrusters or imaging sensors", p.95) and used in the usage profiles (p.99), but NO thruster power, speed-power law, drag or thrust model is given. Slow/fast/full-power levels are not quantified.
- Movement model (Sec. 3.4, p.98): INET built-in mobility "without considering physical laws"; physical model is future work.

### Hotel / sensor loads
- Simple consumer PSM (Fig. 2 left, p.95): Off = 0 W; On = 42 W ("e.g., 42W", p.95), an example for one generic device, not tied to a named sensor. All Table 1 sensors are "active" in light/heavy profiles (p.99); per-sensor powers are not listed.
- Sensor model (Sec. 3.3, p.98): "under construction"; sensor effects on energy and movement are future work.

### Payload / compute
- No compute or payload PSM; only the implied base load.

### Communication (modem PSM, Fig. 2 right, p.95)
- States: Off (0 W), Active (P < 1 W; "standby, listen, and receive modes that all consume less than 1W", p.95), Transmitting (nested). Transitions: activate/deactivate, transmit, done.
- Transmit power by distance d (km): d <= 1.0 -> T1 = 2.8 W; 1.0 < d <= 2.0 -> T2 = 8 W; 2.0 < d <= 3.5 -> T3 = 35 W; d > 3.5 -> T4 = 80 W (Fig. 2 right; "recommended transmission power setting", p.95).
- Duration: transmission time grows proportionally with message size and inversely with data rate (p.100); no equation. Defaults: bitrate 13.9 kbps, preamble 10 microseconds, message 2 B, UDP header 8 B (Table 2, p.101). Whether header and preamble count toward t_tx is not stated.
- RX is not separated from idle: all RX/listen/standby is "Active, < 1 W" (exact value not given). No wake-up, startup or sleep power.
- Link between energy and channel parameters: Table 2 / Fig. 8 use Tx power 80 W and options 2.8/8/35/80 W (p.101, p.103) as radio transmit power parameters; the paper does not explain how these electrical watts relate to radiated acoustic power.

### Battery model
- BatteryModule integrates power and tracks remaining charge (p.94-95). Initial capacity, voltage, efficiency, usable fraction, Peukert/temperature effects: NOT given. The simulation was run "until the battery was completely depleted" (p.99).
- Capacity cannot be back-calculated: constant powers of the light/heavy profiles are not given.

### Energy states and mission phases
- States: as Fig. 2 above. Mission: MissionModule follows a plan of waypoints, speeds and sensor schedules (p.94). Three usage profiles (p.99): light (continuous slow movement, periodic short-range position updates, all sensors on), heavy (thrusters and modem at full power throughout, all sensors on), mixed (slow/fast intervals, comms at different distances, a short period with most sensors off; repeated every 60 min). Interval lengths and power levels of the mixed profile are NOT given.

### Feedback
- Energy -> dynamics: no. Energy -> communication behaviour: no (modem power chosen by distance only). Reception success does not alter energy. Sensor -> movement feedback: future work (p.98). Battery depletion ends the simulation (p.99); no behavioural change stated.

## 3. Validation
None. "In our ongoing work, we will conduct experiments to verify our findings" (p.106). The claim that energy "can already be determined very well with theoretical values from handbooks" (p.105) is unsupported by measurement. For constant-power profiles the authors note results can be computed by hand (p.99).

## 4. Results reported
- Fig. 4 (p.99): instantaneous power (first 3 h) and battery level for three profiles; maximum mission time: heavy about 8 h 45 min, light about 12 h 30 min, mixed about 11 h 10 min. Power levels only readable from plots (not extracted here).
- Fig. 5 (p.100): modem power vs distance (steps 2.8/8/35/80 W) and vs message size/data rate; one message sent 5 min into the simulation. No communication share of total mission energy is reported.
- Comms scenario (Sec. 4.2.1, p.100): two AUVs, one UDP packet every 2 s, 120 s, 60 packets. Ranges: 100-900 Hz up to ~8500 m; 1-5 kHz 4100 m; 5-20 kHz 1900 m; 20-50 kHz 700 m; 100-130 kHz 230 m (p.102). Tx 2.8 W -> ~200 m; 8 W -> 300 m; 35 W -> 700 m; 80 W -> 1000 m last reception (p.103). Fading, sensitivity, SNIR threshold, antenna blind spot beneath the transmitter (p.103-105).
- The 2 s message cadence matches our scenario, but the paper computes no energy for it.

## 5. Code availability
Not stated (no repository, DOI or supplement; Open Access, funding Projekt DEAL, p.106). Earlier version at MARESEC 2021.

## 6. Table 2 as printed (p.101; read from image)
Background noise power 1 dBm; Transmitting power 80 W; Rayleigh fading system loss 2 dB; Receiver sensitivity 2 dBm; Receiver SNIR threshold 2 dB; Receiver energy detection 1 dBm; Frequency band 18-34 kHz; Bitrate 13.9 kbps; Default message length 2 B; Preamble duration 10 microseconds; UDP header 8 B. Also: propagation speed 1500 m/s, noise bandwidth 16 kHz (p.97), Rician K = 4 with 2 dB system loss (p.103). The dBm values (also 5, 10, 15, 20 dBm in the text, p.102-104) look like dropped minus signs; true signs are not recoverable.

## 7. Reproduction recipe

Goal: mission energy from speed profile v(t), duration T, N_tx sent and N_rx received messages of S bytes.

Equations (reconstructed from the PSM description; the paper prints none):
1. E_total = integral_0^T [ P_base + P_prop(v(t)) + sum_s P_sensor,s(on/off) + P_modem(t) ] dt  (Sec. 3.1, p.94)
2. P_modem(t) = P_active (< 1 W) outside transmissions, 0 if Off; = P_Tx(d) during transmission with P_Tx = 2.8 W (d <= 1 km), 8 W (1-2 km), 35 W (2-3.5 km), 80 W (> 3.5 km). (Fig. 2 right, p.95)
3. t_tx = 8 (S + L_hdr [+ preamble]) / R, R = 13.9 kbps, UDP header 8 B, preamble 10 microseconds (Table 2, p.101). Header inclusion is an assumption; p.100 states only size and rate dependence.
4. E_comm = N_tx * P_Tx(d) * t_tx + (T - N_tx * t_tx) * P_active. Reception is billed at P_active; no separate RX energy (p.95). N_rx does not change the energy.
5. Battery: SOC(t) = 1 - E_total(t) / E_batt; end when E_total = E_batt (p.94-95, 99). E_batt must come from us.
6. P_sensor: 0 W off / 42 W on for a generic consumer (Fig. 2 left, p.95), an example only. P_prop: not defined by the paper.

Worked example (my calculation with the paper's constants): message every 2 s, S = 2 B, d <= 1 km. t_tx = 8*(2+8)/13900 = 5.8 ms (with header) or 1.2 ms (without); duty about 0.3 percent. Transmit energy per hour = 1800 * 2.8 W * 5.8 ms = about 29 J; the modem budget is dominated by the unspecified listening power P_active (< 1 W, i.e. under 3.6 kJ per hour). The 80 W level applies only beyond 3.5 km.

Parameters NOT given by the paper (must be supplied by us and flagged as assumptions): base-load power; thruster/propulsion power or any v -> P law; drag/thrust coefficients; vehicle mass; battery capacity, voltage, efficiency, usable fraction; per-sensor powers (42 W is an example only); exact Active/listen/RX power (only "< 1 W"); idle vs sleep distinction; modem startup/wake cost; whether preamble/headers enter t_tx; power levels and interval lengths of the profiles; relation of PSM Tx watts to radiated acoustic power; per-constant sources.

## 8. Capability rows

- thruster effort | no | thrusters named (p.95, p.98) but no effort or speed-power model; movement ignores physics (Sec. 3.4, p.98)
- battery state | partial | BatteryModule integrates power, tracks remaining charge, predicts mission time (p.94-95; Fig. 4 right, p.99); capacity, voltage, efficiency not stated
- sensor loads | partial | On/Off PSM 0/42 W (Fig. 2 left, p.95); Table 1 sensors (p.98) without individual powers; sensor model under construction (p.98)
- compute | no | only an unquantified base load (p.94)
- communication | yes for power state and message-level energy, partial overall | distance-dependent Tx 2.8-80 W, duration from size/rate (Fig. 2 right p.95; p.100); full INET channel/reception model (Sec. 3.2, 4.2); RX/idle lumped into < 1 W
- power states | yes | per-subsystem PSMs (Sec. 3.1, Fig. 1-2, p.94-95)
- provenance | partial | "theoretical values from handbooks" (p.105); EvoLogics 2020 (p.90); Shin and Park 2008 for bands (p.101); no per-parameter sources
- uncertainty | no | none in the energy model; only packet reception is stochastic via fading (p.103)
- arbitrary robot layout | partial | modular per-subsystem PSM, any subsystem can be instrumented (p.94); no geometry or vehicle description
- physical feedback | no | movement without physical laws (p.98); no energy-to-dynamics or energy-to-comms feedback; sensor feedback is future work (p.98)
- mission phase | partial | MissionModule with waypoints, speeds, sensor schedules (p.94); light/heavy/mixed profiles (p.99); no explicit phase state machine
- evidence traceability | no | no validation, no code, no energy parameter table (p.106); only Table 2 for comms defaults
