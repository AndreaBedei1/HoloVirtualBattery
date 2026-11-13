# Evidence-traceable mission energy estimates for marine robots in HoloOcean: a provenance-aware energy layer and its verification

*Draft, not submitted. The statements and numbers are bound to `docs/paper/CLAIM_EVIDENCE_MATRIX.md`
(identifiers C1–C20 in brackets) and to the results in `experiments/results/final/`.*

## Abstract

Simulated mission energy for underwater robots depends on component powers, thruster maps, battery
parameters and hydrodynamic loads whose evidence ranges from exact manufacturer data to
placeholders. Simulators do not usually report which of these a number rests on. We present
HoloEnergy, an energy layer for the HoloOcean simulator. It couples actuator allocation, thruster
electrical models, component power states, a battery model and DESERT network activity, and links
every parameter to an evidence record with a source, a relation to the simulated device and a grade.
The goal is evidence-traceable mission-energy estimates within explicitly stated model assumptions and
evidence bounds, not a validated vehicle model.

Verification has three parts:
- an independent recomputation of every reported energy from the 100 Hz power traces, worst relative
  error 1.9e-13 over 36 runs;
- a backend check that tells a drag-patched HoloOcean 2.3.0 build (observed/expected drag 1.000000)
  from the unpatched build (0.0100);
- consistency between the bus and the modem accounting, within 1e-15 Wh.

Case studies on a simulated BlueROV2 Heavy cover thruster layout, current, payload scheduling, battery
fidelity and communication strategy. The results show which conclusions depend on unvalidated inputs:
- Replacing the simulator's surge resistance with published BlueROV2 measurements scales
  station-keeping propulsion power by 0.11 to 1.29.
- The acoustic-modem share of mission energy ranges from 0.96 % to 13.2 % over published device
  settings.

No result is validated against a physical vehicle.

## 1 Introduction

Energy limits the endurance and payload of small underwater vehicles, and simulation is the usual
way to compare designs and missions before field trials. A simulated mission energy is a sum of
products of modelled powers and durations. The powers come from very different evidence:
- thruster tables measured by a manufacturer under bollard conditions;
- datasheet maxima of sensors;
- receive powers stated as "less than" a value;
- battery parameters derived from a single cell;
- hydrodynamic coefficients of the simulator itself.

When a simulator reports one number, the reader cannot tell how much of it rests on each kind of
evidence, or which inputs would change the conclusion.

This paper addresses one question: can mission-level energy of HoloOcean robots be estimated with
traceable models, while making uncertainty and unsupported assumptions visible? We answer it with a
software layer, HoloEnergy, and with its verification. HoloEnergy does not add a validated vehicle
model. Its outputs are conditional on the simulator's dynamics, and the paper states each condition.

The contributions are:

1. **Run-time evidence grading.** Every parameter used in a run is linked to a registry record with
   its source, location, bound type and relation to the simulated device. The grade of the record is
   capped by that relation: exact A, representative B, proxy C, user D. Each run reports the energy
   share per grade, the proxy and upper-bound shares, unconfigured loads and structured warnings.
   The final experiments use 54 such records [C3, C4].
2. **A coupled energy accounting.** It joins wrench allocation, voltage-dependent thruster tables, a
   resistive battery model, a power manager and the timing of DESERT physical-layer events. The
   accounting closes to machine precision [C2].
3. **A verification procedure that is independent of the energy layer** for the simulator backend.
   It exposed a units defect in HoloOcean's drag force: the force is applied at 0.01 of its declared
   value in 2.3.0, and source reading shows the defect is still present in 2.4.0 [C1].
4. **Case studies with sensitivity to the unvalidated inputs.** They separate conclusions that
   survive published alternatives from conclusions that do not [C5–C20].

## 2 Related work

**Energy in robot simulators.**
- Gazebo Sim provides a linear battery model with internal resistance and attachable power loads,
  including a thruster load in watts [S1].
- UUV Simulator attaches constant on/off power consumers to a battery [S2].
- LOTUSim-Energy, a recent maritime simulator, mentions energy-aware battery modelling. Only its
  abstract was available to us [S3].
- Energy-aware control studies use a thruster power model inside simulation: deep reinforcement
  learning for 6-DOF position control [S4] and current-harnessing model predictive control on a
  BlueROV2 [S16].

None of these sources states the evidence behind individual parameters or how strongly a result
depends on it.

**Communication energy.**
- DESERT Underwater accumulates transmit and receive energy in its physical layer from configured
  powers [S6]; we confirmed the counters in its source.
- ns-3 provides an acoustic modem energy model with sleep, idle, receive and transmit states [S7].
- Danielis et al. couple AUV energy consumption with acoustic communication in OMNeT++ [S8] (read at
  abstract level).

HoloEnergy does not claim to be the first to count communication energy. Its additions are:
- listen and idle states taken from device documents;
- evidence grading of those powers;
- coupling of the modem load to the same battery bus that drives the thrusters.

**Credibility and provenance of simulations.** Credibility assessment scales rate the rigour of
models and simulations against requirements [S13]. Provenance models record how simulation models,
data and experiments were produced [S11]. Both work at the level of studies or models. In the sources
we verified (RELATED_WORK_VERIFICATION.md), we found no grading of individual parameters by their
relation to the simulated device, applied while the simulation runs.

## 3 Model

The full equations, with units, are in `docs/paper/MODEL_EQUATIONS.md`. This section summarises them.

### 3.1 Actuation

A requested body wrench $\tau \in \mathbb{R}^6$ is allocated to $n$ thrusters through the
configuration matrix $B$. The allocation uses weighted least squares with redistribution of
saturated actuators, within force bounds evaluated from the thruster tables at the voltage the pack
would have at its rated current. A pseudoinverse and a power-weighted iterative method are also
implemented. A layout that differs from the simulated body is evaluated as a virtual layout: its
wrench is re-allocated to the native thrusters, and the virtual forces are limited to what the native
body can apply, so energy is never charged for thrust the dynamics do not receive.

The electrical power of a thruster is interpolated in force and in voltage from the manufacturer's
T200 tables (10 to 20 V, separate forward and reverse branches). These are static (bollard) data.
They are applied with inflow, which makes the relation *representative* (grade B) rather than exact.

### 3.2 Components

Each sensor, computer, light or modem is a set of named power states (for example ACTIVE, IDLE,
OFF). Each state value is linked to a record and marked as exact, typical, or upper bound. Components
can be switched by mission phase. OFF is a gated rail at 0 W. A component without a defensible power
is declared unconfigured: it is excluded from the bus and reported as a gap, never given an assumed
value.

### 3.3 Battery and power manager

Two fidelity levels are provided:
- **L0** is an energy bucket at nominal voltage.
- **L1** is a resistive model.

For L1, with open-circuit voltage $U(\mathrm{SOC})$ and resistance $R$, the current that delivers
power $P$ is

$$I = \frac{2P}{U + \sqrt{U^2 - 4RP}}, \qquad V = U - IR.$$

The current is limited by the rated current and by $(U - V_\mathrm{cut})/R$, so the terminal voltage
never falls below the cutoff. The pack is latched off only when $U \le V_\mathrm{cut}$ or no charge is
left. When the request exceeds the available power, the power manager applies one uniform derating
factor to the actuator commands. It solves the operating current self-consistently.

### 3.4 Communication

DESERT runs as an external engine. Physical-layer start and end events of transmission and
reception set the state of each modem interface (TX, RX, LISTEN, SLEEP). The energy over a step is
$\sum_s P_s t_s$, and it is placed on the vehicle bus within the same simulation step. The layer
observes the network and does not change its behaviour.

### 3.5 Accounting identities

Terminal (bus) energy is the sum of the category energies: propulsion, sensors, compute,
communications, auxiliaries and converter losses. The work done against the open-circuit voltage
equals terminal energy plus battery loss.

## 4 Evidence method

A registry record holds:
- value and unit, or a range, or `null` when unknown;
- bound type: exact, nominal, typical, upper bound, range;
- the source, with page and table location;
- the conditions of the measurement;
- a grade for the record itself.

A link from a model parameter to a record carries a relation: exact, representative, proxy or user.
The effective grade is the record grade capped by the relation. When a user overrides a linked value,
or when the record does not contain what the model uses (for example a resistance map), the link is
marked stale and the value is graded D.

Each run reports:
- the energy share per effective grade;
- the shares computed from proxy evidence and from upper bounds (upper bounds bias the estimate
  upward);
- unconfigured loads;
- possible double counting of functions provided by two entries;
- a list of structured warnings, each with its kind, subject, energy and effect.

Published ranges are propagated to an interval on terminal energy. A side with no published bound
stays open instead of being filled with an assumed value.

The grades are a convention of this work. They describe traceability and relation to the modelled
device, not measured accuracy, and they have not been validated as an uncertainty metric [C4].

## 5 Verification

**Software tests.** 329 tests, including regression tests for each defect found by the internal
reviews. Examples:
- a voltage cutoff latched while the open-circuit voltage was above the limit;
- energy charged for thrust a virtual layout could not apply;
- a power-weighted allocator that raised an error at every step.

**Accounting.** An independent script recomputes every category, thruster and component energy,
battery loss and phase sum of the 36 final runs from the 100 Hz traces. The worst relative difference
from the reported values is 1.9e-13, against a tolerance of 1e-9 [C2]. In the cross-layer runs, the
communication energy on the bus differs from the modem adapter's own sum by at most 1e-15 Wh. This is
a check of the implementation against its own equations, not a validation.

**Backend.** HoloOcean computes drag as $\tfrac12\rho C_D A|v_r|v_r$ in SI units but applies it
without the conversion to engine units. A one-line patch fixes this. Our check drives a known thruster
force in a current and in still water and infers the applied drag:
- the patched build gives observed/expected 1.000000 and a physics-to-client step ratio of 1.000000
  at 100 Hz;
- the unpatched control build gives 0.0100 [C1].

The check tests the simulator independently of the energy layer. It does not validate the drag
coefficients themselves.

## 6 Experiments

The design was committed before the runs (`docs/paper/FINAL_EXPERIMENTS.md`). All native runs come
from one clean commit, on the patched HoloOcean 2.3.0 build at 100 Hz.

**Vehicle.** The simulated BlueROV2 Heavy body, with `Perfect` mass properties: neutral buoyancy,
and centre of mass in the horizontal-thruster plane. Isotropic quadratic drag acts at the centre of
mass. Unreal linear damping is applied as $v \leftarrow v(1 - c\,\Delta t)$ to the world-frame
velocity.

**Controller.** One wrench PID for all runs, using simulator state.

**Layouts.**
- L8-HV: the simulator's exact eight-thruster layout (geometry grade A).
- L6-STD: the six-thruster standard layout; lateral spacing of the verticals from the manufacturer
  drawing, fore-aft position a proxy (grade C).
- L4-H45: four vectored horizontals (grade C).
- Benchmark designs, grade D: L4-2H2V (two stern horizontals, two verticals); L8-VEC30 (three-axis
  vectored); and L8-HV with horizontals at 30° or 60°.

**Plans.**
- Station keeping for 90 s. The last 30 s are the steady window.
- A transit: out, stop, yaw, return and a 10 s hold, so every run ends settled.
- A heave transit.

**Currents.** Currents are head-on, so the horizontal thrusters stay on the forward T200 branch
(a stern current needs 1.38 to 1.42 times the power on the reverse branch). Further cases: oblique at
45°, sway, and 0, 0.2, 0.4, 0.5 and 0.8 m/s.

**Payloads.** Two suites, powered either for the whole mission or only in the stop, hold and yaw
phases:
- inspection: 4K camera, imaging sonar, DVL, two lights;
- AI vision: an embedded GPU computer.

**Battery.** L1 with a cell-derived resistance (proxy), and L0. One run starts at SOC 0.03.

**Communication.**
- Nine DESERT configurations with 20 seeds each.
- Eight cross-layer strategies on the transit: none, direct, MAC acknowledgements, multi-hop,
  flooding, optical, the vehicle as relay, and a fixed relay.
- Modems: an EvoLogics S2C M 18/34 profile and a Hydromea LUMA 250LP at 5 m.

**Sensitivity analyses (offline).**
- Surge resistance from HoloOcean, from a restrained standard BlueROV2 (Gabl et al.) and from damping
  identified on a free-running Heavy (von Benzon et al.).
- Every published acoustic transmit setting, the RS-232 and Ethernet interfaces, and the DESERT or
  device airtime.
- The three allocators.
- Isotropic versus anisotropic drag.

## 7 Results

### 7.1 Layout and orientation

Figure FF1 gives the steady propulsion power in a 0.5 m/s current. In head-on current L8-HV, L6-STD
and L4-H45 need the same energy (0.4897 Wh at 0.2 m/s and 6.5295 Wh at 0.5 m/s over 90 s; 245.9 W
steady). In the simulated body only the four vectored horizontals work, because drag acts at the
centre of mass and the horizontal thrust lines lie in its plane. The equality is therefore a
property of the simulated body, not a design result [C5].

L4-2H2V needs 14 % less energy in head-on current (5.5988 Wh) but cannot hold sway or oblique
current. Its final position error reaches 31.4 and 26.9 m [C6]. L8-VEC30 needs 23 % more (8.0398 Wh)
[C7]. All other layouts hold the oblique current in the steady window. During the start-up transient
they saturate for 21.6 % of the run [C9]. L8-HV cannot hold 0.8 m/s: the required 115 N exceeds the
81.3 N its clamped thrusters provide [C11]. The choice of allocator changes steady power by at most
0.13 % [C10].

Thruster angle trades head-on against sway cost. At 0.5 m/s over 90 s:
- 30°: 4.81 Wh head-on, 13.18 Wh sway;
- 45°: 6.53 Wh head-on, 7.78 Wh sway;
- 60°: 10.92 Wh head-on, 5.70 Wh sway.

The size of the trade-off depends on the drag law. With the anisotropic damping identified for the
Heavy, the sway-to-head-on cost ratio at 45° rises from 1.20 to 1.77. We therefore report the
direction of the trade-off and not its magnitude [C8].

### 7.2 Current and surge resistance

Station-keeping propulsion grows steeply with current: 13.4 W at 0.2 m/s, 245.9 W at 0.5 m/s and
608.9 W at 0.8 m/s, the last being infeasible. In still water only the hotel loads consume energy
(0.1438 Wh in 90 s) [C12].

These values follow HoloOcean's drag. Figure FF2 repeats the steady allocation with the two published
BlueROV2 resistance descriptions:
- the restrained-load measurements of Gabl et al. give 0.11 to 0.22 times the HoloOcean propulsion
  power;
- the identified damping of von Benzon et al., used only inside its identified speed range, gives
  0.87 to 1.29 times.

The two references differ from each other by a factor of 6 to 9 in propulsion power. The simulator
lies close to the identified damping and far from the restrained-load data. Absolute
station-keeping energies are therefore conditional on the simulated hydrodynamics.

### 7.3 Transit and ground-referenced damping

The same settled transit needs 0.647, 1.763 and 5.220 Wh at 0, 0.2 and 0.4 m/s (Figure FF3). The
final position errors are 0.025, 0.000 and 0.236 m. Part of the resistance is Unreal's linear
damping, which acts on the world-frame velocity and has no physical counterpart in a current. It is
21 % of the time-mean resistance in calm water, 12 % at 0.2 m/s and 5 % at 0.4 m/s, and up to 81 % in
single phases [C13].

### 7.4 Payload scheduling

Powering the payload only in the inspection phases reduces mission energy on the 0.2 m/s transit
(Figure FF4):
- inspection suite: by 33 %, from 3.146 to 2.116 Wh;
- AI-vision suite: by 10 %, from 2.036 to 1.823 Wh.

The imaging sonar needs a 19 to 74 V supply, while the bus is 12 to 16.8 V. Its step-up converter
has no published efficiency, so it is declared unconfigured. The inspection values are therefore
lower bounds with respect to conversion loss [C14].

### 7.5 Battery fidelity

Over the 0.2 m/s transit, L1 propulsion is 4.4 % above L0 (1.6396 against 1.5710 Wh). The difference
comes from the thruster tables evaluated at the higher L1 bus voltage near full charge. The L1
battery loss (0.0201 Wh) is a separate term. The comparison does not measure battery-model
accuracy, and the voltage effect changes sign during a discharge [C15].

From SOC 0.03, the L1 pack operates voltage-limited at the 12.0 V cutoff. It derates the thrusters to
0.313 and delivers 101.7 W instead of the requested 245.9 W, without latching off [C16]. The
open-circuit curve is a placeholder (grade D), so no endurance figure is given.

### 7.6 Communication

As simulated, the acoustic modem takes 1.45 % of the transit energy. That figure assumes:
- a direct link;
- the 2.8 W transmit setting for 1000 m;
- the RS-232 interface;
- the DESERT 4.8 kbit/s physical layer;
- one message every 2 s.

Recomputing the recorded state durations for every published transmit setting, both interfaces and
both airtime bases gives 0.96 % to 13.2 % (Figure FF5). The as-simulated value is a conditional point
estimate, not a bound [C17].

Relays move modem energy between nodes (Figure FF6). The vehicle spends:
- 0.0171 Wh with a fixed relay, when it only overhears;
- 0.0253 Wh when it forwards;
- 0.0260 Wh on the direct link.

Network-wide modem energy roughly doubles with relays (0.0860 and 0.0855 Wh against 0.0431 Wh), and
delivery drops from 39/39 to 37/39 and 34/39 [C18]. The optical link uses 0.0111 Wh, against
0.0260 Wh for the acoustic one [C20].

In the communication matrix, 8 of 9 configurations give the same delivery and energy for all
20 seeds, because nothing in those scenarios is stochastic. Multi-hop with MAC acknowledgements
delivers 61 of 200 messages (Wilson 95 % interval 0.245 to 0.372) [C19].

## 8 Threats to validity

- **No physical validation.** No measured BlueROV2 mission energy was available. Agreement with the
  simulator's own equations is verification only.
- **Simulator hydrodynamics.** Propulsion dominates every mission and follows HoloOcean's drag and
  Unreal's ground-referenced damping. The body is decoupled and neutrally buoyant. The layout
  equalities and the zero still-water propulsion follow from this.
- **Thruster data in inflow.** The T200 tables are bollard data. We grade them representative (B)
  because the device is the one simulated and only the inflow condition differs. A stricter reading
  would treat inflow as a different condition and grade them lower. One peer-reviewed source reports
  non-bollard T200 data, but we could not access it.
- **Battery.** The open-circuit curve is a placeholder. Its zero-SOC point is inconsistent with the
  rated cell capacity, and the resistance is a cell-derived lower bound. Thermal behaviour is not
  evaluated.
- **Communication.** Receive and listen are priced at the published upper bound. The 24 V modem
  supply conversion is not modelled. The DESERT physical layer is not the device's.
- **Experimental design.**
  - The native runs are deterministic, with one controller, and the cross-layer runs use one seed.
  - Phase schedules and layouts other than L8-HV are scenario choices.
- **Grading.** The grades are a convention; their usefulness for decisions has not been tested with
  users.

## 9 Conclusions

HoloEnergy produces mission-energy estimates for HoloOcean robots in which every parameter has a
traceable source and a grade, and in which the share of energy resting on proxies, upper bounds and
placeholders is reported with the result. The accounting and the backend were verified.

The case studies show how far conclusions depend on unvalidated inputs:
- Under the identified anisotropic damping, the direction of the orientation trade-off holds and
  the layout ranking within each current direction holds in five of eight cases. The magnitudes do
  not hold.
- Absolute propulsion energies change several-fold with the choice of published resistance data.
- The communication share depends on device settings that a simulation must state.

Physical validation of mission energy remains open.

## Data and code availability

Code, evidence registry, final results (per-run summaries, 0.1 s traces, verification), figures with
their plotted data, and the environment record are in the HoloEnergy repository
(branch `feature/provenance-aware-energy-framework`). The 100 Hz traces are regenerated from the
recorded commit and identified by SHA256.

## References

Verified at the source unless marked otherwise (see `docs/paper/RELATED_WORK_VERIFICATION.md`).

- [HO] E. Potokar, S. Ashford, M. Kaess, J. G. Mangelson. HoloOcean: An Underwater Robotics
  Simulator. ICRA 2022. doi:10.1109/ICRA46639.2022.9812353. *(registry record; full text not re-read
  in this phase)*
- [HO-SRC] BYU FRoSt Lab. HoloOcean v2.3.0 source code. https://github.com/byu-holoocean/HoloOcean
- [Gabl] R. Gabl, T. Davey, Y. Cao, Q. Li, B. Li, K. L. Walker, et al. Hydrodynamic loads on a
  restrained ROV under waves and current. Ocean Engineering 234 (2021) 109279.
  doi:10.1016/j.oceaneng.2021.109279
- [vB] M. von Benzon, F. F. Sørensen, E. Uth, et al. An Open-Source Benchmark Simulator: Control of a
  BlueROV2 Underwater Robot. J. Mar. Sci. Eng. 10 (2022) 1898. doi:10.3390/jmse10121898
- [T200] Blue Robotics. T200 Public Performance Data 10–20 V (September 2019).
- [S2C] EvoLogics GmbH. S2C M Series Product Information (December 2017).
- [LUMA] Hydromea. LUMA 250LP datasheet, V1.241007.
- [S1] Gazebo Sim API reference v8: Battery.
- [S2] UUV Simulator, `CustomBatteryConsumerROSPlugin` *(class page; authors not verified)*.
- [S3] Grosset, Dubromel, Lechene, Arzel, Buche. LOTUSim-Energy: A Maritime Simulator for
  Human-Drone Interaction in Autonomous Offshore Operation & Maintenance. arXiv:2609.17124, 2026
  *(abstract only)*.
- [S4] Bore, Sufan, Rodriguez-Martinez, Troni. Toward 6-DOF Autonomous Underwater Vehicle
  Energy-Aware Position Control based on Deep Reinforcement Learning: Preliminary Results.
  arXiv:2502.17742, 2025.
- [S6] G. Toso, F. Favaro. `uwphysical.cpp`, DESERT Underwater, SIGNET Lab, University of Padova.
- [S7] ns-3 project. UAN Framework, AcousticModemEnergyModel. ns-3 Model Library.
- [S8] Danielis, Parzyjegla, Mohamed Ali, Sill Torres. Simulation model for energy consumption and
  acoustic underwater communication of autonomous underwater vehicles. WMU J. Maritime Affairs
  (2021). doi:10.1007/s13437-021-00253-z *(abstract only)*.
- [S11] Ruscheinski, Uhrmacher. Provenance in Modeling and Simulation Studies: Bridging Gaps.
  WSC 2017, pp. 872–883 *(record to be checked)*.
- [S13] Blattnig, Green, Luckring, Morrison, Tripathi, Zang. Towards a Credibility Assessment of
  Models and Simulations. 10th AIAA Non-Deterministic Approaches Conference, 2008.
- [S16] Syntakas, Vlachos. Ocean Current-Harnessing Stage-Gated MPC: Monotone Cost Shaping and
  Speed-to-Fly for Energy-Efficient AUV Navigation. arXiv:2602.00823, 2026.
