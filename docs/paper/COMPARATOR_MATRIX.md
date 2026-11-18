# Comparator matrix (brief sections 19–21)

The comparison covers energy-modelling capability only. Each cell states what the cited material
shows. A capability that the material does not show is marked "not stated" rather than
"unsupported". Sources are listed at the end: [D] is Danielis et al. 2021 (read in full,
docs/literature/danielis2021.md), [L] LOTUSim-Energy (paper read in full, code partly,
lotusim_energy.md and lotusim_code.md), [G] the Gazebo Sim battery documentation and UUV Simulator
plugin [S1, S2], [DS] the DESERT `uwphysical` source [S6], [N] the ns-3 UAN energy model [S7].

| Capability | HoloEnergy | Danielis et al. 2021 [D] | LOTUSim-Energy [L] | Gazebo / UUV Simulator [G] | DESERT [DS] |
| --- | --- | --- | --- | --- | --- |
| Thruster effort → electrical power | Yes: per-tick allocation and voltage-dependent T200 tables | No: constant power per state, no propulsion law given | Partly: the paper states SOC/voltage follow propulsive effort; no equations in the paper, model not found in the readable code | No: a thruster `power_load` is constant while active (S1) | No (network simulator) |
| Battery state (SOC, voltage) | Yes: L0 bucket or L1 Rint with cutoff and derating | Yes: a battery module integrates power (no parameters given) | Yes (SOC published to operators) | Yes: linear battery with internal resistance (S1) | No |
| Sensor loads | Yes: evidence-linked power states | Yes: per-subsystem state machines (example 42 W sensor) | Not stated | Yes: constant on/off consumers (S2) | No |
| Compute loads | Yes | Not separate (subsystem state machines) | Not stated | As a generic consumer | No |
| Communication energy | Yes: DESERT PHY events → TX/RX/LISTEN/SLEEP on the vehicle bus | Yes: modem state machine (TX by range, "Active" below 1 W) | Not stated | No | Yes: TX/RX energy counters, no idle/listen [DS] |
| Power states / mission phases | Yes: states, phase marking, scheduled payload | Yes: state machines and mission profiles | Partly (mission scenarios) | On/off only | No |
| Physical feedback (energy → dynamics) | Yes: derating of actuator commands, voltage-limited operation | No (stated) | Not stated | Not stated in S1 | No |
| Arbitrary robot layout | Yes: N actuators, any position/direction, builder API | Generic AUV only | Several vehicles (BlueROV2, LRAUV, WAM-V, X500) | Yes (per-model plugins) | n/a |
| Parameter provenance | Yes: every parameter linked to a record with source, location, relation and grade | No: handbook values, no per-parameter citation [D] | Not stated | No | No |
| Uncertainty / bounds | Yes: interval propagation with open sides; sensitivity analysis | No | Not stated | No | No |
| Evidence traceability in results | Yes: per-run grade shares, dynamics evidence, structured warnings, requirement assessment | No | No | No | No |

## Same-mission model comparison (`experiments/run_tool_comparison.py`)

Neither competing tool could be executed here, so their published model structures were reproduced
on the final missions. This is a model comparison, not tool execution, and with no measured energy
it is not an accuracy ranking.

Both comparators were calibrated on the calm-water transit, which is their best case, and both
reproduce it exactly.

| Mission | HoloEnergy propulsion (Wh) | State-machine model [D] (Wh) | Gazebo-style constant load [G] (Wh) |
| --- | --- | --- | --- |
| Transit, calm (calibration) | 0.5239 | 0.5239 | 0.5239 |
| Transit, 0.2 m/s | 1.6396 | 0.5239 | 0.5452 |
| Transit, 0.4 m/s | 5.0967 | 0.5239 | 0.5452 |
| Station keeping, calm | 0.0000 | 0.0526 | 0.0000 |
| Station keeping, 0.2 m/s head-on | 0.3459 | 0.0526 | 0.6372 |
| Station keeping, 0.5 m/s head-on | 6.3858 | 0.0526 | 0.6372 |

- **State-machine model.** It cannot represent the effect of a current on propulsion: the hover and
  moving powers are fixed.
- **Gazebo-style constant load.** It is on/off only. It overestimates station keeping in a weak
  current and underestimates it in a strong one.
- **Communication.** The state-machine estimate is 0.0241 Wh and HoloEnergy's 0.0260 Wh, for the
  same direct acoustic link and the same transmit power. The difference comes from the airtime basis
  (13.9 kbit/s vs the DESERT 4.8 kbit/s PHY) and from the "Active" power (1 W vs the 0.8 W receive
  upper bound).
- **Caveat.** HoloEnergy's propulsion values follow HoloOcean's hydrodynamics, which are not
  validated (EXP10 part 1). The comparison shows what each model structure can represent, not which
  one is right.

## Sources

- [D] P. Danielis, H. Parzyjegla, M. A. Mohamed Ali, F. Sill Torres. Simulation model for energy
  consumption and acoustic underwater communication of autonomous underwater vehicles. WMU J.
  Maritime Affairs (2021), doi:10.1007/s13437-021-00253-z.
- [L] J. Grosset et al. LOTUSim-Energy. arXiv:2609.17124 (2026); code
  github.com/IRL-Crossing-CNRS/LOTUSim-Energy (EPL-2.0).
- [S1] Gazebo Sim API v8: Battery. [S2] UUV Simulator `CustomBatteryConsumerROSPlugin` (class page;
  authors not verified).
- [S6] DESERT Underwater `uwphysical.cpp` (G. Toso, F. Favaro). [S7] ns-3 UAN framework,
  AcousticModemEnergyModel.
