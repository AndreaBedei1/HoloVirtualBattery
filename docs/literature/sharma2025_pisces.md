# Sharma et al. 2025 (Communications Engineering 4:93) - Pisces LED localisation, with measured subsystem power

Citation: S. Sharma, D. Van Passen, R. V. Prasad, K. Chowdhury, "Low power, non-intrusive 3D localization for underwater mobile robots", Communications Engineering (2025) 4:93. DOI 10.1038/s44172-025-00422-5 (p.1). Received 22 May 2024, accepted 23 April 2025. 12 PDF pages. Datasets available "upon reasonable request".

## 1. Scope
Blue-LED angle-of-arrival and received-signal-strength-ratio relative localisation for underwater robots (OpenFish robotic fish). Not a propulsion or battery paper; relevant to HoloEnergy only through its measured sensing and compute power numbers.

## 2. Measured vs simulated
- Measured (Sec. "Controlled experiments" and "Effect of multipath and noise", pp.4-5): circular pool of 3 m diameter, receiver at 0.25 m depth, distances 0.32 to 3.0 m, turbid water; MAE 0.031 m at 0.32 m and 0.16 m at 1 m (abstract). Transmitter driven by an Arduino Atmega 2560 on an independent battery.
- Measured power (Sec. "Power consumption", p.6; Table 2): current of the transmitter LED, receiver photodiode and Teensy MCU measured; a Raspberry Pi 4B camera system was also built for comparison. Supply voltage, instrument, averaging and operating state are not stated in the text read.
  - Transmitter LED circuit 18.8 mW x 2 devices = 37.6 mW; receiver photodiode circuit 0.6 mW x 3 = 1.8 mW; Teensy microcontroller 198 mW x 1; total Pisces 237.4 mW.
  - 5 MP embedded camera with fish-eye lens 760 mW; Raspberry Pi 4B processor 2960 mW; total camera-based solution 3720 mW.
  - Transmitter LED current 11 mA (abstract).
- Model/derived: received-power model and RSSR geometry; localisation latency 10 ms (abstract).

## 3. What this source can and cannot support in HoloEnergy
- V0, V4: no. V1: only as a weakly documented measured reference for small embedded compute and optical sensing power (Raspberry Pi 4B 2960 mW, camera 760 mW, Teensy 198 mW) if an order-of-magnitude hotel-load alternative is needed; operating state and voltage are unknown, so it cannot replace a BlueROV2 electronics-bay measurement.
- V2: marginal (component level, a single number per component, no uncertainty). V3: none.
- Not comparable to a BlueROV2 / T200 / 4S 18 Ah case: small robotic fish in a 3 m pool, no thrusters, no battery data. Mainly a negative entry for the evidence registry (no propulsion or battery information).
