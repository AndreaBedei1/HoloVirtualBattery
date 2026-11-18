# LOTUSim-Energy (Grosset et al., arXiv:2609.17124v1, 15 Sep 2026) - energy-modelling characterisation

Source: full text read via pdftotext (short paper, ~6 pp; page numbers not reliably recoverable from the text layer, so locations are given as section / figure / table).
Authors: CROSSING IRL 2010 (Naval Group / CNRS / IMT Atlantique).

## 1. Architecture and engine (Sec. III, Fig. 1, Table I)
- Distributed server-client; Gazebo (gz-sim) is the central orchestrator and deterministic barrier-synchronised step scheduler. Update requests are randomly permuted each tick with a reproducible seed. Real-time (RTF=1) and accelerated (RTF>1) modes.
- Three client classes: Physics (LOTUSim-Xdyn, gRPC/WebSocket), Agent Interaction (ROS 2/DDS, hardware-in-the-loop bridges), Rendering (Unity, optional; desktop/VR, Leap Motion, eye tracking, PUN2 multi-user).
- Marine physics: Xdyn 6-DoF (Fossen), added mass, damping, wave (Airy), current forces; fork "LOTUSim-Xdyn" adds Ekman-layer current (Sec. IV.C, Eqs. 1-7). Aerial: Gazebo rigid body + wind plugin (Sec. IV.B).
- Vehicles (Sec. V.C): tethered BlueROV(2), LRAUV (long-endurance), X500 UAV, WAM-V USV. Table II lists further task/agent classes (UAV/USV/ROV/AUV/CTV) but states those rows are supported by the stack and not benchmarked end-to-end.
- Table I positions it as Air+Surface+Underwater; Energy Model row for LOTUSim-Energy reads "Theoretical methods" (table text extraction is garbled; the column alignment of this cell is my reading, not certain).

## 2. Energy model (Sec. I contribution list, Sec. V.D, Sec. VI.E, Fig. 8)
The whole energy model is described in one paragraph (Sec. V.D) with no equations.
- Battery model type: "modular battery simulator plugin" coupling state-of-charge estimation to each vehicle's instantaneous propulsive effort "rather than assuming a constant power draw". Publishes real-time voltage and SOC. Battery chemistry/model class (ideal, linear, equivalent circuit, OCV-SOC curve): NOT STATED. Equations: NOT STATED. Parameters (capacity, voltage, resistance, efficiency) and their sources: NOT STATED.
- Propulsion power model: effort-dependent (per Sec. V.D and Sec. I bullet "based on propulsion effort"). Functional form (thrust->power map, speed dependence, motor/ESC efficiency, hover power for UAV): NOT STATED.
- Sensor/payload loads: not stated (camera, YOLO, sonar loads not mentioned in energy context).
- Compute load: not stated.
- Communication energy: not stated.
- Power states / modes: not stated.
- Mission phases: scenario has surface monitoring, underwater inspection, aerial inspection legs (Sec. VI.A, Fig. 5); Sec. V.B says scenes log "time/energy budgets and safety hold states". No phase-wise energy accounting described.
- Capacity/discharge display for LRAUV in Fig. 8 (Sec. VI.E.2), used by operators to "reserve for safe recovery"; no numbers readable in the text.
- Separate unrelated energy item: Fig. 9 right shows turbine electricity production vs wind strength (education mode); not robot energy.

## 3. Coupling / feedback
- Battery state is published for planners and operators (monitoring, HITL decisions, Sec. V.D, VI.E.2). Feedback of SOC/voltage into dynamics (derating, cutoff, thrust limit): NOT STATED. Environmental forcing (currents) does affect thruster compensation (Sec. VI.E.1) so energy draw is implicitly environment-dependent, but the paper does not report this linkage numerically.

## 4. Provenance, uncertainty, grading, evidence
- No parameter provenance, evidence grading, uncertainty/sensitivity analysis, or traceability for the energy model: NOT STATED. (Provenance discussion exists only for MetOcean data: Copernicus Marine, Sec. V.A, and a drag-coefficient citation Eq. 4.)

## 5. Validation
- No comparison of simulated energy with measured energy: NOT STATED. Only quantitative-ish validation is a real AIS track vs simulated USV path (Fig. 6, 10 points), explicitly framed as guidance illustration, not controller benchmark. Abstract claims evaluation "under real-time energy monitoring"; Conclusion lists "benchmarking of energy-aware planners ... under sim-to-real protocols" as future work, i.e. energy sim-to-real not yet done.

## 6. Code / data
- GitHub: https://github.com/IRL-Crossing-CNRS/LOTUSim-Energy (footnote 5, Sec. III); LOTUSim-Xdyn: https://github.com/naval-group/lxdyn (footnote 8); video: youtube NRd-LjRrrac (footnote 1). Parent: LOTUSim, arXiv:2607.03072 (ref [5]). Licence/battery code details not stated in paper.

## 7. Numeric results
- No energy or endurance numbers stated in text. Numeric items are only navigation: waypoint tolerance 0.5 m, accel limits 0.5 m/s2 / 0.01 rad/s2, velocity saturation 1-10 m/s / 0.05 rad/s (Sec. VI.B). Fig. 8 shows a battery capacity/discharge curve (values not recoverable from text).

## 8. Explicitly not modelled / future work (Sec. VII, Table II caption, Table I)
- Future: underwater image formation, biodiversity risk layer, benchmarking of energy-aware planners and fault detection with sim-to-real protocols. Wind turbine model marked "(On-Going)" in Table I. Abstract mentions "fault-detection pipelines" and "energy-aware battery modeling" as modular tools; fault detection is YOLO visual anomaly detection (Sec. VI.D), not electrical fault modelling. Many Table II tasks not benchmarked.

## Fairness notes for the comparator matrix
- It is a simulator-integration paper; energy is a secondary contribution described at plugin level. Absence of details is "not stated", not evidence of absence; the repository may hold more.
- Genuine strengths: effort-coupled (non-constant) battery drain, voltage+SOC outputs, multi-domain (air/surface/subsea) with metocean forcing, HITL use of SOC.
- Note: paper cites HoloOcean [2] only as having simplified currents and N/A energy in Table I.

## Capability rows
- thruster effort: yes (propulsive-effort-coupled; form not stated) - Sec. V.D, Sec. I contributions
- battery state: yes (voltage and SOC published; model type/equations not stated) - Sec. V.D, Fig. 8
- sensor loads: not stated
- compute: not stated
- communication: not stated
- power states: not stated
- provenance: not stated (energy parameters); MetOcean data sourced from Copernicus only - Sec. V.A
- uncertainty: not stated
- arbitrary robot layout: partial (plugin is "modular" and per-vehicle, vehicles: BlueROV2, LRAUV, X500, WAM-V; arbitrary thruster layouts not stated) - Sec. V.C-D
- physical feedback: not stated (monitoring/HITL only; no derating or cutoff described) - Sec. V.D, VI.E.2
- mission phase: partial (multi-leg scenario and "time/energy budgets" logging; no phase-wise energy model) - Sec. V.B, VI.A, Fig. 5
- evidence traceability: not stated
