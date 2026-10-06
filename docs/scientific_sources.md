# Scientific sources and model decisions

Research date: 2026-10-06. Raw search records are in `sources/research*.json`.
Search backend: web.run; parallel-cli was unavailable. Publisher HTML sometimes
returned 403/429; accessible publisher PDFs and institutional author copies were
used. No numerical parameters were transferred between different cell chemistries.

## Bibliography

| ID | Reference and access | Used for |
| --- | --- | --- |
| S1 | Bernardi, D., Pawlikowski, E., Newman, J. (1985). A General Energy Balance for Battery Systems. *J. Electrochem. Soc.* 132(1), 5–12. [DOI 10.1149/1.2113792](https://doi.org/10.1149/1.2113792), [author technical-report record](https://escholarship.org/uc/item/9fx5f0h8). The record is a 1984 precursor; the publication is 1985. | Heat-balance framework. The original publisher full text was not accessible; simplified equation corroborated by S2. |
| S2 | Alhanouti, M., Gießler, M., Blank, T., Gauterin, F. (2016). New Electro-Thermal Battery Pack Model of an Electric Vehicle. *Energies* 9, 563. [DOI 10.3390/en9070563](https://doi.org/10.3390/en9070563), [full text, KIT](https://publikationen.bibliothek.kit.edu/1000059427/3890227). | ECM tradeoffs, thermal balance §4 Eq. 7a–b, temperature-dependent resistance and OCV. |
| S3 | Zhang, R. et al. (2018). A Study on the Open Circuit Voltage and State of Charge Characterization of High Capacity Lithium-Ion Battery Under Different Temperature. *Energies* 11, 2408. [DOI 10.3390/en11092408](https://doi.org/10.3390/en11092408), [publisher PDF](https://mdpi-res.com/d_attachment/energies/energies-11-02408/article_deploy/energies-11-02408.pdf). | Temperature-specific OCV characterization and SOC definitions. |
| S4 | Pózna, A. I., Hangos, K. M., Magyar, A. (2019). Temperature Dependent Parameter Estimation of Electrical Vehicle Batteries. *Energies* 12, 3755. [DOI 10.3390/en12193755](https://doi.org/10.3390/en12193755). | Temperature-dependent capacity and electrical parameters; parameter identification §3.4. Simulation verification, not BlueROV2 validation. |
| S5 | [Blue Robotics 18 Ah 4S battery product](https://bluerobotics.com/store/comm-control-power/powersupplies-batteries/battery-li-4s-18ah-r3/), [battery guide](https://bluerobotics.com/learn/battery-info/), [Samsung INR18650-30Q datasheet hosted by Blue Robotics](https://bluerobotics.com/wp-content/uploads/2018/10/INR18650-30Q-Data-Sheet.pdf). | Pack ratings and operational bounds. Cell ratings do not replace pack ratings. |
| S6 | [Blue Robotics T200 product and test data](https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/), [official September 2019 workbook](https://cad.bluerobotics.com/T200-Public-Performance-Data-10-20V-September-2019.xlsx). | Measured electrical input power and thrust vs PWM and voltage. |
| S7 | [Blue Robotics Low-Light HD USB Camera](https://bluerobotics.com/store/sensors-cameras/cameras/cam-usb-low-light-r1/). | 5 V supply, maximum 220 mA, hence upper bound 1.1 W. |
| S8 | [Blue Robotics Ping360](https://bluerobotics.com/store/sonars/imaging-sonars/ping360-sonar-r1-rp/). | Maximum input power 5 W; supply 11–25 V. |
| S9 | Raj, A., Texas Instruments (2010, revised 2020). [Calculating Efficiency, SLVA390A](https://www.ti.com/lit/an/slva390/slva390.pdf), Eq. 13. | Converter efficiency and power-loss definition. |
| S10 | [HoloOcean BlueROV2 2.2](https://byu-holoocean.github.io/holoocean-docs/v2.2.0/agents/agents/blue-rov-agent.html), [agent API 2.2](https://byu-holoocean.github.io/holoocean-docs/v2.2.0/holoocean/agents.html), [environment API 2.3](https://byu-holoocean.github.io/holoocean-docs/v2.3.0/holoocean/environments.html). | Eight thruster forces, control scheme 0; simulated tick timing. These are inspected API versions, not a claim of runtime compatibility with every version. |

## Selection

L0 is an ideal energy bucket for accounting baselines. L1 uses an OCV source and
series effective DC resistance. It captures sag and resistive loss with two dynamic
states (reference SOC and average pack temperature). RC polarization, diffusion,
hysteresis, aging and charging are excluded. S2 compares richer ECMs: their
parameters need pulse/relaxation measurements unavailable for this particular pack.
L1 is a first calibratable approximation, not experimentally validated here.

One lumped thermal node is implemented. S2 Eq. 7b reduces to
`C_th dT/dt = I² R - k (T-T_water)` for this Rint circuit. Optional reversible
heat is `-I T_K dU_oc/dT` (positive discharge current). The entropy coefficient
must be measured; its omission is explicit, not a statement that it is zero in
all Li-ion cells. Enclosure conduction, internal air and water exchange are
combined into an effective `k`; radiation and internal temperature gradients
are omitted. A second enclosure node is deferred until validation shows a need.

Temperature dependence uses measured tables rather than universal correction
coefficients. S3 supports OCV characterization at temperature; S4 motivates
identifying capacity and electrical parameters at multiple temperatures. Table
interpolation is an engineering representation of these measurements, not an
equation or dataset copied from either article. No Arrhenius activation energy
or Peukert exponent is assigned without pack-specific data.

## Implementation traceability

Voltages and resistance are pack-level. Current is positive during discharge;
SOC is a fraction and time is in seconds. Source IDs resolve to the bibliography
above. Each entry distinguishes source values, calibration and simplifications.

### L0 energy bucket — battery.py

- Origin: conservation of energy and the Wh definition; S5 for pack ratings.
- Equations: E_used += P_terminal*dt/3600; SOC=SOC_initial-E_used/E_capacity;
  I=P/V_nominal.
- Source values: 18 Ah * 14.8 V = 266.4 Wh if using the S5 nominal pack baseline.
- Calibrate: actually usable Wh, initial charge and application limits.
- Simplification: ideal constant voltage, no sag, internal loss or cold-capacity
  correction. The wrapper can still apply thermal operational limits.
- Rationale: accounting baseline and independent integration verification.

### Rint discharge, SOC and voltage — battery.py

- Origin: equivalent electrical circuit discussed by S2; charge balance.
- Equations: V=U_oc(SOC_ref,T)-I*R(T); P_terminal=I*V;
  SOC_ref_next=SOC_ref-I*dt/(3600*Q_ref).
  For constant power, I=2P/(U+sqrt(U²-4RP)), the stable high-voltage root;
  at R=0 use I=P/U. This quadratic solution is our algebraic derivation.
- S5 source values: Q=18 Ah, nominal 14.8 V, cutoff 12 V, continuous 60 A.
  The 132 A/10 s burst rating is not enabled. No pack BMS is assumed.
- Calibrate: pack DC pulse resistance, relaxed OCV-SOC and actual usable capacity.
  Demo R=0.04 ohm and OCV interior knots are placeholders. The 12/16.8 V
  illustrative endpoints follow operating bounds, not measured relaxed OCV.
- Simplifications: no RC polarization, diffusion, hysteresis, aging, regeneration,
  charging or slow self-discharge. R varies with T, but currently not SOC.
  Discharge Coulomb counting is ideal; electrical loss is modeled separately.
- Rationale: identifiable DC parameters for a first ROV mission-energy model.
  Add RC dynamics only if pulse and held-out mission errors justify them.

### Temperature dependence — battery.py

- Origin: S3 motivates OCV characterization at different temperatures; S4
  motivates fitting capacity/electrical parameters across temperature.
- Equations: piecewise linear interpolation in SOC then T for U_oc(SOC_ref,T);
  R(T)=R_ref*f_R(T); I_rating(T)=I_ref*f_I(T).
  These interpolations represent measured maps, not copied article coefficients.
- Source coefficients: none; these articles did not characterize this BlueROV2 pack.
- Calibrate: OCV-temperature curves, DC resistance factors, capacity and continuous
  current factors. Default tables contain only [25 C,1], a reference identity.
  **Empirical cold-temperature effects are not characterized by the default profile.**
  Logs explicitly flag this. No invented Arrhenius activation energy or Peukert
  exponent is supplied.
- Simplifications: average pack temperature, reference SOC basis, no aging or
  current-dependent map. Table endpoints clamp and out-of-calibration is logged.
- Rationale: transparent chemistry-specific calibration without transferring
  coefficients from unrelated cells.

Capacity accessibility uses an explicitly selected engineering convention:
Q_eff(T)=Q_ref*f_Q(T), with 0<f_Q<=1;
Q_available=Q_ref*max(0,SOC_ref-(1-f_Q));
SOC_available=Q_available/Q_eff.

Cold inaccessible capacity occupies a tail of the reference charge interval.
Reference SOC does not change solely when temperature changes. Warming can
restore access before an operational cutoff latches. This convention is a
calibratable approximation, not a universally validated law from S3/S4. Reference
capacity must use the highest characterized usable-capacity condition. Import
temperature-specific OCV on the same reference SOC axis. Fit accessibility and
sag jointly: otherwise loaded-cutoff capacity measurements can double-count sag.

### Deliverable current and power — battery.py, power_manager.py

- Origin: our algebra from the Rint circuit, constrained by S5 pack ratings.
- Equations: I_lim=min(I_rating(T)*g_thermal, U/(2R), (U-V_cut)/R,
  3600*Q_available/dt, I_heat_limit);
  P_available=I_lim*(U-I_lim*R), additionally bounded by optional max_power_W.
  Omit R denominators at R=0. OCV at/below cutoff yields zero power.
- Source parameters: continuous current and voltage limits from S5.
- Calibrate: installed wiring/connector limits and voltage margin, current map
  versus temperature and actual enclosure cooling.
- Simplifications: no burst budget, BMS hysteresis or recovery policy. Cutoff
  latches until reset. Loaded voltage is checked at the end of each tick,
  including changed SOC and temperature. Event timing resolution is dt.
- Rationale: enforce charge, stable voltage branch and operational limits.

### Thermal dynamics and battery efficiency — thermal.py, battery.py

- Origin: simplified S1 heat balance and S2 Eq.7b.
- Equations: C_th*dT/dt=Q_heat-k*(T-T_water); Q_heat=I²R.
  With a measured entropy curve s(SOC_ref)=dU_oc/dT, use
  Q_heat=I²R-I*T_K*s. The sign assumes positive discharge current.
- S5 limit: current pack guide 50 C maximum operational temperature, distinct
  from the thermistor measurement range.
- Calibrate: C_th, effective pack/enclosure-to-water k and entropy. Demo C_th=1200
  J/K, k=2 W/K and derating onset 40 C are placeholders. Water 15 C and initial
  pack 20 C are scenario inputs. Entropy is omitted unless provided, and must
  agree with the OCV-temperature surface when supplied.
- Simplifications: one uniform node, no hot-cell gradients or separate enclosure
  state. k combines internal air, enclosure conduction and external exchange;
  it is not a bare-cell convection coefficient. Radiation is omitted. Electronics
  and converter heat are not deposited into the battery node.
- Rationale: dynamic thermal feedback is computationally light; a second node
  needs sensor-lag/enclosure data and should be justified by validation.

For heat held constant over dt, the exact thermal solution is:
T_next=T_water+(T-T_water)*exp(-k*dt/C_th)
+(Q_heat/k)*(1-exp(-k*dt/C_th)).
At k=0: T_next=T+Q_heat*dt/C_th. This is our analytic ODE solution, avoiding
Euler cooling instability. A predictive quadratic current bound prevents
held-interval heat from exceeding cutoff.

Electrical resistive efficiency follows eta_battery=P_terminal/(U_oc*I)=V/U_oc
for I>0. Temperature affects it through R and OCV; no additional arbitrary
temperature-efficiency multiplier exists. The chemical_energy_used_Wh field
integrates ideal OCV electrical work U_oc*I. It is a free-energy/work estimate,
not complete chemical enthalpy when reversible heat is included.

### Thruster consumption — propulsion.py, tools/import_t200.py

- Origin: S6 official September 2019 workbook, tested at 10,12,14,16,18,20 V.
- Equations: u=(PWM_us-1500)/400; F_N=F_kgf*9.80665 (standard gravity).
  Interpolate electrical power along u or force, then voltage, with separate
  forward/reverse tables; sum all eight drive inputs.
- Source values: PWM, force, power and tested supply voltage. Unchanged source
  bytes, SHA256, processing and row anomalies are retained.
- Calibrate: installed inflow, interference, mounting, ESC revision and PWM mapping.
- Simplifications: static bollard curves, no spin-up or incoming-flow dynamics.
  Conservative cumulative-max envelopes remove nine monotonicity inversions.
  Nonzero actions outside the measured voltage range fail instead of extrapolating.
  Test power is already electrical drive input; do not double-count ESC losses.
- Rationale: measured bidirectional lookup avoids an uncalibrated cubic law.

Source anomaly: sheet 14 V, PWM 1548 us has current 0.01 A and published power
1.4 W, while VI=0.14 W. Published Power is retained and flagged; manufacturer
clarification remains pending. Neither conflicting column is silently corrected.

### Sensors, payload and hotel load — payload.py, hotel_load.py

- Origin: S7/S8 electrical limits. The time/state accounting is our engineering model.
- Equations: E_component=sum(P_state*time_in_state)/3600. Startup and ping
  durations are integrated exactly across interval boundaries. ping_W is total
  ping-state power; active_W applies between periodic pings.
- S7/S8 values: camera maximum 5 V*0.220 A=1.1 W; Ping360 maximum 5 W.
- Calibrate: active mean, idle, startup/ping watts and durations, frequency.
  Unknown-state fields remain null and raise when selected. DVL/custom profiles
  remain unconfigured until exact hardware is identified. Hotel 15 W is an
  aggregate placeholder, not a verified computer/flight-controller measurement.
- Simplifications: ACTIVE demo values are upper bounds, not observed means.
  OFF=0 assumes a physical power gate. Electrical states do not disable simulator
  rendering or control sensor data validity.
- Rationale: reuse measured component profiles without generalizing watts from
  a simulated sensor class.

Ping360 is a mechanical scanning sonar. Mapping its electrical profile to a
HoloOcean ImagingSonar is an explicit electrical proxy, not equivalent imaging
physics. GPUImagingSonar and unidentified DVL need their own hardware profile.

### Conversion losses — converters.py

- Origin: S9 Eq.13 efficiency definition.
- Equations: P_in=P_out/eta; P_loss=P_in-P_out for each rail.
- Source coefficients: none; converter hardware is unidentified.
- Calibrate: actual board efficiency versus voltage, load and temperature.
  Demo eta=0.9 for payload/hotel rails is a placeholder.
- Simplifications: constant rail efficiencies. Propulsion distribution eta=1
  assumes no extra cable loss beyond the test electrical boundary.
- Rationale: an identifiable rail-efficiency model before board-specific modeling.

### Allocation and derating — power_manager.py, env_wrapper.py

Origin: our engineering policy constrained by the equations above; S10 supplies
the API semantics. Auxiliaries take priority over propulsion. Bisection finds
the action factor from measured nonlinear consumption, then solves the coupled
terminal-voltage/load point. Force capability at the minimum permitted voltage
provides a conservative action ceiling. Action factor is not a watt ratio.

The linear current ramp between thermal onset and cutoff is a configurable
control policy, not a literature-derived current rating. It compounds the
temperature current map. LOW_SOC=20% is also a user policy, not a chemistry constant.

When auxiliaries exceed supply, their logged service is fractionally reduced
and propulsion is zero. This is an accounting approximation, not a reboot or
sensor-validity model. Inspect auxiliary_service_factor and unmet_power_W.
Default action scaling is false; uncurtailed simulator actions during shortage
are flagged as inconsistent with the simulated energy supply.
