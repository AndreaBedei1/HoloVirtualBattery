# De Carolis, Lane, Brown (OCEANS 2014 Taipei) - low-cost energy measurement and linear estimation model

Citation: V. De Carolis, D. M. Lane, K. E. Brown, "Low-cost Energy Measurement and Estimation for Autonomous Underwater Vehicles", OCEANS 2014 - TAIPEI. DOI 10.1109/OCEANS-TAIPEI.2014.6964490. The DOI is NOT printed on the pages; it is in the embedded PDF metadata (subject field). The page footer gives only "978-1-4799-3646-5/14/$31.00 (c)2014 IEEE". 5 PDF pages; page refs are PDF pages.

## 1. What is measured, what is simulated
- Measurement method (Sec. II, p.2): Hall-effect current sensor on the main electrical bus, "0A to 30A" range, read through an ADC by a microcontroller at fixed Fs; energy by trapezoidal integration, E[T] = sum Vbus * (a[n-1]+a[n])/2 * Ts (Eq. 2). Vbus is a symbol in the equation; how it is obtained is not described. Sensor model, accuracy, sampling rate Fs, temperature: not given. The claim in the abstract that the system measures energy "with a good confidence level" is not backed by any measured data in the paper.
- No real-vehicle measurement is reported anywhere. All results (Sec. IV, pp.3-5) come from the UWSim simulator with Nessie VII hydrodynamics and a thruster model "already known from previous experiments" (no parameters given). Table III labels 35.56 Wh as "Measured Energy Usage" but the text says it was calculated from the simulated navigation with the thruster model, i.e. it is a simulated reference, not a measurement.
- Linear model (Eq. 4, p.2): dE = k1*dx + k2*dy + k3*dd + k4*dpsi, calibrated by least squares on single-DOF trajectories (Sec. III-B, p.3). Whether the Table II coefficients came from the simulator or the vehicle is not stated.

## 2. Numbers (Tables I-III, p.4)
- Vehicle (Sec. I, p.1): Nessie VII, torpedo-shaped hover-capable AUV, four Li-Ion batteries "providing 2.2 kWh", six brushless DC thrusters "capable of developing up to 250 W" each.
- Table I (simulated inspection mission): duration 340.86 s; navigation distance 86.07 m; total energy 35.56 Wh; battery initial capacity 1800 Wh; battery usage 2.03 %. Our arithmetic: 35.56/1800 = 1.98 %, so 2.03 % does not follow from the printed numbers; 1800 Wh also differs from the 2.2 kWh in Sec. I.
- Table II: k1 = 557.24 J/m, k2 = 1174.21 J/m, k3 = 1118.13 J/m, k4 = 1607.14 J/rad.
- Table III: reference 35.56 Wh, predicted 34.18 Wh, error 3.89 %. Text: prediction "within 10%".
- Mean power implied (our arithmetic, not in paper): 35.56 Wh over 340.86 s = about 375.6 W average.

## 3. Test conditions
Simulated shallow-water pier inspection, ROS stack identical to the vehicle's, no currents ("shallow water without strong sea currents", Sec. V p.5). No temperature, voltage, or battery model.

## 4. What this source can and cannot support in HoloEnergy
- V0: no (no code, no reproducible inputs; thruster model parameters not given).
- V1: positioning only. It documents a coulomb-counting bus-current measurement approach and a waypoint-linear energy model; none of its coefficients applies to BlueROV2.
- V2: no. No component-level measured electrical data are published.
- V3: no. No measured vehicle power or energy is printed; the single comparison is model-vs-simulator-of-the-same-model.
- V4: no. The authors themselves say field validation was still to come ("further validate the model with real mission data").
- Comparability: Nessie VII (2.2 kWh, 6 x up-to-250 W thrusters, torpedo hull) is not comparable to a BlueROV2 / T200 / 4S 18 Ah case. Use only as related work for runtime energy models and as a methodological contrast: HoloEnergy compares against measured electrical data, whereas this paper's "measured" energy is simulated.
