# De Carolis, Brown, Lane (IEEE JOE 2018) - runtime energy estimation and route optimisation

Citation: V. De Carolis, K. E. Brown, D. M. Lane, "Runtime Energy Estimation and Route Optimization for Autonomous Underwater Vehicles", IEEE Journal of Oceanic Engineering 43(3):608-619, 2018. DOI 10.1109/JOE.2017.2707261 (printed on PDF p.1 and p.2). Local file IEEEjoeRuntimeEneryFullText.pdf is the Heriot-Watt accepted manuscript ("peer reviewed version", 13 PDF pages; manuscript page numbers 1-12 appear on PDF pp.2-13). Not one of the 2026-11-19 files; read for positioning.

## Measured vs simulated
- Field data: IVER3 (560 Wh LiPo, 1 Hz, "more accurate battery management system, capable also of measuring the platform's energy consumption") and Nessie VII (2.2 kWh LiPo, six HPDC1502 brushless thrusters, 250 W max each, 10 Hz, low-cost energy monitor, i.e. the 2014 paper). Sec. IV, manuscript pp.7-9, PDF pp.8-10.
- Reported only as plots: instantaneous energy-per-distance eps_nav(psi) in J/m (Fig. 4 IVER3 lawn-mower survey with an east-bound current; Fig. 5 Nessie two-leg run in tidal currents), regression model with 95 % intervals (Fig. 2, simulator data), velocity profile (Fig. 3). No tabulated Wh, no voltage/current logs, no energy-prediction error against measured mission energy.
- Tables I-II (p.11) are route-optimisation simulation results (1000 runs, 5x10 grid): inspected points EA-OP vs OVRP, gain 5.14 % at 0.00 m/s to 24.49 % at 1.00 m/s current bound (Table I); solver times (Table II). Not electrical.
- Method: LWPR nonlinear regression of eps_nav(heading) and v_cruise(heading) from on-board data; probability of mission completion from normal distributions of time and energy (Eqs. 2-16).

## Supports in HoloEnergy
- V0/V1: no parameters usable for BlueROV2.
- V2-V3: no (no numeric measured power/energy). V4: no, although it is the closest published field evidence of mission-level energy tracking and uncertainty-aware completion probability; useful related work for the "mission-energy with uncertainty" framing.
- Comparability: torpedo AUVs with large LiPo packs; not BlueROV2/T200/4S 18 Ah.
