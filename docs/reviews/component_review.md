# Component review (Reviewer D: sensors, compute, communications)

Independent review of HoloEnergy at tag `v0.2.0` (bd11c98), branch
`feature/provenance-aware-energy-framework`. Later commits were checked only where they touch
this scope: 89b78ff adds relay strategies to `run_crosslayer.py`, 5713394 adds a scheduled-payload
runner and 69bd3d7 adds voltage-dependence reporting. None of these commits has committed results.
The aim of the review was to find flaws.

## Scope and method

**Files reviewed**
- All 19 `holoenergy/profiles/components/*.yaml`, all 13 `profiles/communications/*.yaml`, and their
  records in `evidence/data/parameters/{sensors,comms_compute,vehicle_electronics}.yaml` and `sources.yaml`.
- `sensor_policy.py`, `integrations/{communications,desert}.py` and `models/components.py`
  (including the legacy `PayloadComponent` path).
- `tools/check_desert_noninterference.py`, `experiments/run_comm_matrix.py`, `run_crosslayer.py`,
  the committed `results/native/desert/*.json` and `results/native/crosslayer.json` (with `logs/crosslayer*.log`).
- `docs/double_counting_policy.md`, and the claims made in `README.md`, `docs/RESEARCH_STATUS.md` and `docs/paper_outline_smpat.md`.

**Primary sources.** All 47 source documents were re-read online (manufacturer pages, datasheets
and papers; URLs as listed in `sources.yaml`). The quotes below come from those documents.

**Runs.** All runs used the DESERT engine at 127.0.0.1:5571 with `manage_engine=False`. No Docker
and no HoloOcean were used. Outputs are in the reviewer scratch folder
`C:\Users\ANDREA~2.BED\AppData\Local\Temp\claude\945244cbcba3dc8b\50891df7-d4df-47f1-ad45-e3fefca5e7b6\scratchpad\reviews\D\`.
- Native non-interference check, e01_chat (`nonint_e01.json`): PASS.
- Full communication matrix re-run (`comm_matrix_rerun.json`, `comm_matrix_rerun_EF.json`): all 9
  configurations reproduce the committed Wh, deliveries and frame counts exactly.
  - E and F first failed because another session was holding the single-session engine; the retry passed.
- Independent sampled-time integration (0.1 ms grid) of raw PHY events (`scripts/indep_check.py`,
  `indep_check_B2_whoi.json`):
  - Configuration B2 (multi-hop + ACK) with the WHOI profile (RX differs from LISTEN), including
    `receiver_busy_overlap` and `transmitter_busy` outcomes.
  - Agrees with the adapter to within 3e-5 relative.
- Library probes, run in memory with nothing written: the legacy sensor path, modem-profile quantity validation, and the HoloOcean 2.3.0 sensor registry.

## Per-device table

Bound labels:
- **UB**: the profile uses a published maximum or the top of a published range.
- **typ**: a typical, average or nominal figure.
- **meas**: a measured mean.

### Component profiles

| Profile | Device | States | Power used | Source value / location | Bound | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| bluerobotics_lowlight_usb_camera | Low-Light HD USB Camera R1 | ACTIVE | 1.1 W | "Supply Voltage 5 V", "Max Power Draw 220 mA" (product page) | UB, flagged | Correct. The camera compresses H.264 on board, so the companion computer does not encode. |
| bluerobotics_4k_camera | 4K Cam Low-Light (BR-103829, Ethernet, 5–55 V) | ACTIVE | 5 W | "Max Power 5 W" | UB, flagged | Correct. It is an Ethernet camera, not USB. |
| bluerobotics_lumen | Lumen (page shows R4, URL says r2) | OFF/ACTIVE | 15 W | "over 1500 lumens at 15 Watts"; "Peak Current: (15/Vin) A"; Vin 7–48 V | labelled `nominal` | **Bound wrong**: the page gives 15 W as a peak, so it should be UB. Dimming is not modelled (D-05). |
| bluerobotics_navigator | Navigator (IMU ICM-20602, MMC5983 + AK09915, BMP280/390, ADC, PWM) | IDLE/ACTIVE | 0.025 / 0.75 W | "5 mA (Idle)", "150 mA (Typical)", "200 mA (Max)"; 5–5.35 V | typ | Values correct. "Idle" is undefined on the page. |
| bluerobotics_ping360 | Ping360 (page R2, URL R1) | ACTIVE | 5 W | "Maximum Power Consumption 5 W"; "11–25 V" and "11–18 VDC" on the same page | UB, flagged | Value correct. Profile `relation: exact` contradicts its own "electrical proxy only" comment (D-14). |
| bluerobotics_ping_sonar | Ping (page BR-101684 RevB) | ACTIVE | 0.5 W | "100 mA (typical) / 900 mA (peak)", 4.5–5.5 V | typ | Correct. The peak is not modelled (D-16). |
| cerulean_surveyor_240_16 | Surveyor 240-16 | IDLE/PINGING_MAX | 5 / 15 W | "5W typical at idle, 15W typical max while pinging", 10–30 V | typ / UB | Correct. |
| edgetech_2205 | EdgeTech 2205 | (unconfigured) | – | "Power consumption varies depending on the configuration" | – | Correct: excluded from the bus. |
| jetson_orin_nx_16gb | Jetson Orin NX 16GB | AI_INFERENCE | 12.815 W | Rey 2025 Table 4 p.15; column headed "Energy Consumption (W·s)"; measured with tegrastats; no power mode stated | meas (record grade A) | Number matches, but the unit is ambiguous and the figure is module-only; profile capped at B (D-10). |
| kongsberg_m3_500m | M3 500 m | ACTIVE | 22 W | p.2 "Input power: 22 W (avg.), peak power < 60 W, mode dependant", 12–36 V | typ | Correct. |
| raspberry_pi_4b | Raspberry Pi 4B | IDLE/VIDEO/HIGH_LOAD | 3.0 / 3.9 / 6.0 W | RPi docs workload table, in amps only: 0.6 / 0.78 / 1.2 A, measured with an HDMI monitor, USB keyboard, mouse and Ethernet attached | meas | Values match. The 5 V supply is assumed. VIDEO is H.264 *playback*, not BlueOS streaming (D-15). |
| seabird_sbe49 | SBE 49 FastCAT | ACTIVE | 3.42 W | p.2 "285 mA at 12 V" (pump included); "Turn-on transient: 750 mA" | typ | Correct. The transient is not modelled. |
| sonardyne_sprint_nav_mini | SPRINT-Nav Mini | ACTIVE | 10 W | p.2 "24 V dc, 10 W nominal"; inertial sensors + Syrinx Mini DVL + pressure sensor | typ | Value correct. `includes` declares a magnetometer the datasheet does not mention. 24 V on a 14.8 V bus (D-06, D-09). |
| te_ms5837_30ba | MS5837-30BA (served Rev C6, record says B1) | ACTIVE | 60 µW | "20.09 µA" at 1 sample/s, OSR 8192; VDD typ 3.0 V; conversion peak 1.25 mA | typ | Correct, but only valid at 1 sample/s; negligible either way. |
| tritech_gemini_720is | Gemini 720is | ACTIVE | 27 W | p.2 "16 - 27 W (range dependent)", standalone unit, "ignores cable losses"; 19–74 Vdc | UB (value_max), flagged | Value correct. The supply is outside the BlueROV2 4S range (D-09). |
| tritech_micron | Micron (0650-SOM-00004 Iss. 08) | ACTIVE | 4 W | "12 - 48V DC at 4VA (average)" | typ | Correct (VA on DC). Sensor mapping is inconsistent (D-14). |
| ublox_zed_f9p | ZED-F9P-01B | STARTING/ACTIVE/SLEEP | 0.27 / 0.204 / 1.35e-4 W | Table 13 p.14: acquisition 90/75 mA, tracking 85/68 mA; p.13: I_BCKP 45 µA at V_BCKP 3 V | typ | Values match. ACTIVE uses the GPS-only current, not the multi-GNSS default; antenna supply excluded; 45 µA cited on the wrong page (D-15). |
| vectornav_vn100_rugged | VN-100 Rugged (accel., gyro, magnetometer, barometer) | ACTIVE | 0.22 W | "Power 220 mW", but also "40mA @ 5 V" (= 200 mW) | typ | Value matches. The page's own inconsistency is not flagged; `includes` omits the barometer (D-15). |
| waterlinked_dvl_a50 | DVL A50 | ACTIVE | 4 W | "Power consumption, average 4 W"; "Power-on current surge 35 W"; ping rate 4–15 Hz adaptive | typ | Correct. Surge correctly unconfigured, but missing from the peak-current analysis (D-16). |

### Communication profiles

Every TX figure below is worded as electrical consumption in its source. No acoustic source level
or optical output figure was taken as electrical power.

| Profile | Device | States | Power used | Source value / location | Bound | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| evologics_s2cm_18_34_{1000m,2000m,3500m,max} | S2C M 18/34 (2017 PI, p.1) | TX / RX=LISTEN / SLEEP | TX 2.8 / 8 / 35 / 55 W; RX 0.8 W; SLEEP 2.5 mW | "2.8W, 1000m range / 8 W, 2000 m / 35 W, 3500m / 55 W, max. available"; "Receive Mode less than 0.8 W" for RS-232 ("Add 500 mW for the Ethernet interface"); listen 5–285 mW only with a Wake-Up module; 24 VDC; 13.9 kbit/s | TX typ (UB for max); RX/LISTEN UB, flagged | Correct. LISTEN = RX is right without a wake-up module. The RS-232 assumption is not stated in the profile. |
| whoi_micromodem2_25khz | Micro-Modem 2 (table 403005) | TX / RX / LISTEN / SLEEP | ~60 / 2.74 / 0.82 / 0.00096 W | "Standard (Micromodem 2 Firmware 27046 or newer)", 12 VDC: TX(25kHz) ~60, RX S-PSK 2.74, Idle 0.82, Hibernate 0.00096 | typ (approximate) | Values match. The firmware condition is missing; legacy firmware idles at 1.43 W (D-15). |
| benthos_atm900_level8 | ATM-900 (manual Rev D, p.2-2) | TX / RX=LISTEN / SLEEP | 20 / 0.65 / 0.0102 W | "Average transmit power @ 21 VDC: 20 watts at power level 8"; "650 mw typ / 720 mw max"; lowpower "10.2 mw typ"; "Peak transmit current: 3 A, 50 ms" | typ | Correct. The manual's own conflicts (16.8 mW, 768 mW) are recorded. The 3 A peak is not modelled. |
| ahoi_bridge_max | ahoi (Renner 2020, p.18:19) | TX / RX=LISTEN / SLEEP | 2.1 / 0.3 / 0.001 W | "1.1 W (lowest output level) to 2.1 W (highest output level)", whole-modem total; "idle and receive mode is 300 mW"; whole modem "a few milliwatts in sleep mode" | TX at highest level; SLEEP UB | TX and RX correct. SLEEP is the transmitter board only and underestimates the whole modem (D-15). |
| subnero_wnc_m25mso4 | WNC-M25MSO4 | TX / RX=LISTEN / SLEEP | 45 / 4 / 0.001 W | "< 45 W (transmit mode, avg.)", "< 4 W (receive mode, nominal)", "< 1 mW (deep sleep)"; 22–28 VDC | UB, flagged | Correct. The FAQ's "<150 mW" sleep mode with acoustic wake-up is not offered. |
| sonardyne_bluecomm200 | BlueComm 200 | TX / RX=LISTEN | 25 / 10 W | Receiver "10 W"; Emitter "Power Consumption 15 W (bandwidth allocation dependant)"; "Optical Transmit Power 6 W (radiated light)"; 24–36 V | TX derived (B), UB | Correct derivation. The 6 W optical output correctly kept apart. |
| hydromea_luma250lp_max | LUMA 250LP (datasheet marked PRELIMINARY) | TX / RX=LISTEN / SLEEP | 5 / 0.5 / 0.01 W | "Transmitting 2 - 5 W (typ.)", "Active, Receiving 0.5 W", "Sleep Mode < 10 mW"; "250 Kbit/sec, up to 600 Kbps at reduced range"; range 7 m | TX UB, flagged | Values correct, but the DESERT optical PHY used with it is not this device (D-03). |
| hydromea_lumax_max | LUMA X | TX / RX=LISTEN | 20 / 2 W | "Transmitting 2 - 20 W (typ.)", "Active, Receiving 2 W", 10 Mbit/s | TX UB | Correct. "LED banks" wording not in the source. |
| semtech_sx1276_14dbm_upper | SX1276 (chip only) | TX / RX=LISTEN / SLEEP | 0.287 / 0.034 / 6.6e-7 W | Table 6: +17 dBm PA_BOOST 87 mA, +13 dBm RFO 29 mA, sleep 0.2 µA; Table 10: LoRa RX band 1, 125 kHz, 10.3 mA; +14 dBm not tabulated | UB of bracket (C) | Values correct. The default `modem_signal_processing` contradicts "excludes MCU" (D-17). |
| wfs_seatooth_s100_max | Seatooth S100 | TX / RX=LISTEN / SLEEP | 7 / 0.086 / 0.005 W | "Transmit: 1-7W / Receive: 86mW / Sleep: 5mW"; "Standard: 2.4 kbps / Optional: 4.8 kbps" | TX UB | Values correct. Bitrate records "typical/max" where the datasheet says "standard/optional". |

**Records with no component profile**
- `blueprint_oculus_m750d.power_range` (10–35 W) is verified, but its datasheet cell spans the M/MT and MD columns, not only M/MT.
- `turner_cyclops7f_chlorophyll.power` was not mapped to any profile.

**Grade-D gaps, correctly left unconfigured:** Fathom-X, the 5 V BEC efficiency, and the power-sense module.

## Findings

| ID | Severity | Location | Issue | Evidence | Fix |
| --- | --- | --- | --- | --- | --- |
| D-01 | major | README.md:75; paper_outline RQ4; RESEARCH_STATUS.md:82 | "An acoustic modem adds **at most** 1.37 %" is not an upper bound. It is an upper bound only for RX/LISTEN (0.8 W maximum). TX uses the *lowest* published S2C M setting (2.8 W at 1000 m). The airtime comes from DESERT's 4.8 kbit/s PHY rather than the device's 13.9 kbit/s, and converter losses are omitted (D-09). | Crosslayer `direct`: TX 13.93 s, LISTEN 53.07 s. Recomputed shares: 8 W → 2.6 %, 35 W → 8.3 %, 55 W → 12.1 %. At 2.8 W with 13.9 kbit/s airtime → 1.07 %. So 1.37 % is neither an upper nor a lower bound. | Report 1.37 % as a conditional point estimate (setting, PHY rate, RX/LISTEN maximum, 2 s period) with a sensitivity band over the published TX settings. Drop "at most". |
| D-02 | major | run_crosslayer.py; RQ4 | The cross-layer design cannot show a strategy → vehicle battery effect. The vehicle never relays. RX = LISTEN power, so ACK and overhearing are free. The vehicle moves about 5 m (0.25 m/s, final x = −0.96 m) against links of 8–1000 m, so mobility does not change the network. There is no feedback from battery to network and no derating. "Identical trajectory" holds by construction. The `none` baseline compares modem present against modem absent: 52 % of the increment is LISTEN, independent of activity. | Vehicle comm energy: direct 0.02262870 Wh = ack 0.02262870 Wh (difference 1e-15). Multi-hop is 0.08 mWh *below* direct because of horizon truncation (64 TX starts, 63 TX ends). The TX-attributable share is 39.0 J = 0.66 % of terminal energy. Terminal energy differs between direct and ack by 1.2e-6 Wh while comm energy is identical, so that difference is not caused by communication. HEAD's `relay-fixed` case (vehicle only overhears) will be energy-neutral by construction. | Reframe RQ4. Vary the vehicle's own load: relay-vehicle (HEAD), traffic period, TX setting, sleep/wake policy. Use an RX ≠ LISTEN profile (WHOI) for overhearing. Use geometry where motion changes link outcomes. Report the TX-attributable share separately from idle listening. |
| D-03 | major | run_comm_matrix.py E/F; crosslayer `optical`; holo_desert default PHY | The PHY operating point does not match the device whose energy is charged. **Optical:** the DESERT default `tx_power_w: 50.0` W of *radiated* power and 1 Mbit/s are paired with LUMA 250LP at 2–5 W *electrical*, 250 kbit/s and 7 m range, on an 8 m link. The radiated power exceeds the electrical input, and TX airtime is about 4× too short. **Acoustic:** source level 135 dB re 1 µPa and 4.8 kbit/s are paired with the S2C M "1000 m" setting with no published relation. 1966 PHY bits per frame are sent for a 50-byte payload (holo_desert JSON envelope). | `comm_matrix.json` scenario `network.optical`; crosslayer optical TX 0.0669 s / 34 frames = 1.97 ms; `tx_bits` 19664 / 10 frames; LUMA 250LP datasheet. | Take PHY bitrate and range from the profiled datasheet. Add a consistency check (radiated ≤ electrical). State the frame size in per-byte metrics. Treat the optical results as illustrative only. |
| D-04 | major | run_offline_campaign.py SUITES; RQ3; README.md:74; RESEARCH_STATUS "Suites" | Payload suites assume continuous full-power operation for all 67 s, including holds and the yaw, and the docs do not say so. In S5, 2 Lumens at 15 W, Gemini at its 27 W maximum, the 4K camera at its 5 W maximum, the DVL and the RPi in VIDEO are all ACTIVE throughout. | S5 hotel load is 70.65 W. The summary's upper-bound energy is 0.596 Wh (32 W, 45 % of the added load) and the Lumens are another 42 % (D-05). "+86 %" is quoted with no caveat. | State the continuous-operation assumption. Report the upper-bound share next to +86 %/+23 %. Add the scheduled-payload variant (HEAD runner 5713394; no results yet). |
| D-05 | major | sensors.yaml `bluerobotics_lumen.power_full` | The 15 W figure is labelled `nominal`, but the page gives it as a peak ("Peak Current: (15/Vin) A"), so it should be an upper bound. The URL points to R2 while the page describes R4. | Lumen product page. With the correct label, S5's upper-bound energy would rise from 0.596 to about 1.15 Wh, roughly 41 % of terminal energy. | Use `bound: upper_bound`, add a dimming lookup only if measured, and cite the revision. |
| D-06 | major | docs/double_counting_policy.md; vectornav_vn100_rugged.yaml comment; tests/test_double_counting.py | The double-counting check flags *physically distinct* devices (Navigator + VN-100, Navigator + SPRINT-Nav, SPRINT-Nav + A50). This contradicts the policy's own rule that distinct devices are not a double count. The VN-100 profile tells users "Do not combine with a Navigator", which would drop a real device's power. Every BlueROV2 has a Navigator, so any external AHRS or INS triggers the flag, and `double_counting: error` rejects valid builds. SPRINT-Nav's `magnetometer` capability is not on its datasheet; VN-100's `includes` omits its barometer. | `test_navigator_plus_separate_imu_magnetometer_is_flagged`; SPRINT-Nav datasheet p.1; VN-100 page. | Flag only a load that declares it *represents* a function inside another device (e.g. `represents: navigator.imu`). Make other overlaps informational. Remove the "do not combine" advice. |
| D-07 | major | models/payload.py `PayloadComponent`; legacy `sensors:` config | The 0 W rule for ground-truth sensors and the refusal of derived sensors can both be bypassed. The legacy schema accepted 4 W on `VelocitySensor` and 12 W on `SemanticSegmentationCamera` (verified in memory), yet the policy doc says these "are refused ... can never double count". | `ComponentModel({'nav': {'simulation_sensor': 'VelocitySensor', ... 'active_W': 4.0}, 'seg': {... 'SemanticSegmentationCamera' ... 12.0}})` builds without error. | Call `check_component_mapping` in `PayloadComponent`, or reject the legacy `sensors:` schema. |
| D-08 | major | run_native_campaign.py WrenchController; bluerov2_heavy_holoocean.yaml components | The closed-loop runs navigate on 0 W ground truth (`PoseSensor`, `VelocitySensor`, `DynamicsSensor`), but the default Heavy budget has no sensor that could supply that feedback (no DVL/USBL; only the Navigator IMU). Sensing the controller relies on is therefore uncharged. This biases the hotel load low in RQ3 (station keeping "0.048 Wh / 30 s") and in transits in current. | Controller lines 160–182; profile components list. | State the assumption. For runs with position/velocity feedback, add a navigation-equivalent load (e.g. A50 4 W + Bar30) or report its size. |
| D-09 | major | whole component/comm layer | No supply-voltage domain check exists (no code reads `supply_V`), and converters run at efficiency 1. On the 14.8 V 4S bus the model powers the Gemini 720is (19–74 V), S2C M (24 V), SPRINT-Nav (24 V), Subnero (22–28 V) and BlueComm (24–36 V). 5 V loads (5.75 W in the default suite) have no BEC loss. The resulting bias is *downward*, which contradicts the "upper bounds bias upward" reading. | `grep supply_V holoenergy/*.py` finds nothing; `vehicle_electronics.yaml` lists the BEC as a gap; `bluerobotics_4s18ah_v2.yaml` nominal 14.8 V. | Check each device's supply range against the bus. Require an explicit converter (efficiency or a flagged gap) per rail, and show its direction in the evidence summary. |
| D-10 | major | comms_compute.yaml `jetson_orin_nx_16gb.yolov8s_fp16` | 12.815 W is graded A / exact / measured_mean. The source column is headed "Energy Consumption (W·s)" and the paper uses W and W·s interchangeably. It was measured with tegrastats (on-module sensors, rail unspecified) with no nvpmodel stated, and it excludes the carrier board, fan and DC-DC conversion. "AI vision +23 %" rests on it. No measured Orin NX segmentation or idle figure was found, so "semantic segmentation" falls back to YOLOv8s detection (representative). | Rey 2025 p.10 (method) and p.15 (Table 4). | Grade the record B. Label it module-level. Add carrier overhead as a gap. Name the workload in every RQ3 sentence. |
| D-11 | major | experiments/results/native/crosslayer.json; desert/comm_matrix.json; run_crosslayer.py:229–230 | Committed results come from dirty trees with *untracked* runners. `crosslayer.json` merges two invocations under one `git` / `created_utc` stamp: run 1 produced `none` and `optical` and failed every acoustic case with "negative energy from load source"; run 2 re-ran them. It records `holoenergy_version` 0.1.0, and its evidence summary misses the modem upper bound (0.0205 Wh = camera only). The runner merges old results by design. | `logs/crosslayer.log`, `logs/crosslayer2.log`; crosslayer.json `git.working_tree_status` "?? experiments/run_crosslayer.py". | Re-run all strategies in one clean-tree invocation. Remove the merge, or stamp provenance per result. Regenerate F10/F11. |
| D-12 | minor | integrations/{communications,desert}.py; all 13 profiles | RX power equals LISTEN power in 12 of 13 profiles (WHOI is the exception), so the receive machinery (half-duplex priority, overlap merge, outcome filter) has no energy effect. The WHOI RX state uses S-PSK for every reception, FSK included. | Profile tables above; comm_matrix shows every receiver at 56.0 J. | State this wherever receive, ACK or overhearing energy is discussed. Allow RX power per modulation. |
| D-13 | minor | communications.py `ModemPowerProfile.from_mapping` | No `quantity == electrical_power` check, unlike `ElectricalComponent`. A bitrate record is accepted as TX = 15000 W at grade A (verified). | Probe with `subnero_wnc_m25mso4.bitrate`. | Reject non-electrical records. |
| D-14 | minor | sensor_policy.py PHYSICAL; ping360 / micron / navigator profiles | Mapping inconsistencies: <br>• Ping360 (and Micron) are mechanical scanning sonars mapped to the multibeam `ImagingSonar` with `relation: exact`, whereas SBE49 is capped at `representative` for a weaker mismatch. <br>• The policy lists Micron under `ProfilingSonar`, but its profile maps it to `ImagingSonar`. <br>• The policy lists Navigator for `IMUSensor`, but the Navigator profile has no `simulation_sensor`. <br>• `audit_agent_sensors` ignores `includes` and is never called; the CLI only calls `classify`. | Files as listed. | Cap the scanning-sonar mappings at representative. Align PHYSICAL with the profiles. Make the audit honour `includes`. |
| D-15 | minor | sensors.yaml, comms_compute.yaml | Missing conditions and wording slips: <br>• VN-100 says 220 mW vs 40 mA × 5 V = 200 mW. <br>• ZED-F9P ACTIVE uses GPS-only 68 mA instead of the multi-GNSS default 85 mA; antenna/LNA current is not included; 45 µA is on p.13, not p.14. <br>• RPi table: amps only, with HDMI, keyboard, mouse and Ethernet attached; VIDEO means playback. <br>• WHOI: firmware ≥ 27046 condition missing; "coprocessor" is not in the source. <br>• ahoi SLEEP is the transmitter board only. <br>• Subnero's sleep mode with wake-up is missing. <br>• Seatooth says "standard/optional". <br>• Page or document revisions differ from the URLs: Ping360 R2, Ping RevB, Lumen R4, MS5837 Rev C6. | Primary sources above. | Correct the records and conditions. |
| D-16 | minor | profiles; payload model | Peaks and transients are not modelled anywhere, so the peak-current and brownout analysis omits them: A50 35 W surge, SBE49 750 mA, Benthos 3 A for 50 ms, Ping 900 mA, ZED-F9P 130 mA, MS5837 1.25 mA. No sonar uses the existing ping-rate mechanism; the A50's 4 W average is not tied to its 4–15 Hz ping rate. | Sources above. | Add peak records to the peak-current check, or list them as unmodelled. |
| D-17 | minor | semtech_sx1276_14dbm_upper.yaml | The default `includes: modem_signal_processing` contradicts "excludes MCU". The MCU that actually runs the stack would be flagged as a double count. | Profile comment; communications.py default. | Use `includes: []` for chip-level proxies. |
| D-18 | minor | run_comm_matrix.py F; all experiments | The hybrid configuration F never switches to optical: optical TX = RX = 0 at both nodes, with the switch threshold at 1e13. It measures only the idle cost (35 J per node) of an always-listening, unused optical modem. No experiment uses a SLEEP idle policy, so continuous listening is an unstated assumption. | Matrix rows F, E. | Label F as idle cost only. Add a sleep or duty-cycled variant. |
| D-19 | minor | run_comm_matrix.py `recompute`; paper_outline §6 | The "independent" recomputation reuses the adapter's assumptions (outcome filter, TX priority, clipping), so it checks a re-implementation. My sampled-time integration agrees to within 3e-5, so the implementation is sound, but the wording overstates independence. | `indep_check_B2_whoi.json`. | Call it a re-implementation check, or cite a sampled-time check. |
| D-20 | minor | check_desert_noninterference.py | The docstring says holo_desert manages Docker in native mode, but the code uses `manage_engine=False`. Native mode does not compare backend command logs. The cross-layer stepping path (`session.step(1)` plus a hand-split `HoloOceanLink.sync`) is not covered by any non-interference check. | Lines 12–14, 144, 183–186; run_crosslayer.py 140–150. | Fix the docstring. Add a non-interference run of the cross-layer stepping path. |
| D-21 | minor | jetson budget records; profiles/compute/README.md; provenance_framework.md | The budgets omit MAXN and the Super modes (MAXN_SUPER, 40 W) listed in the r36.4.4 docs. The compute README says no compute profile is bundled, yet two are. The documented `bound` list omits typical, budget and lower_bound. | Sources and files. | Update the records and docs. |
| D-22 | minor | run_comm_matrix.py metrics; desert.py `network_metrics` | Energy per delivered message or byte is dominated by LISTEN over an arbitrary horizon (messages × interval + drain). For A, 1.15 J of the 12.0 J per message is TX. Non-interference energy metrics report 0 deliveries because host events are absent. | comm_matrix A; nonint outputs. | Report TX-only energy per message and state the horizon. |

**Counts:** 0 critical, 11 major (D-01 to D-11), 11 minor (D-12 to D-22).

## Verified correct

- **Sensor registry.** The policy matches HoloOcean 2.3.0 `SensorDefinition._sensor_keys_` exactly (39/39).
  - In the current (non-legacy) component schema, state sensors are refused any load above 0 W and derived semantic sensors are refused outright.
  - The semantic-segmentation decomposition into camera + compute is enforced in that schema (the legacy schema bypasses it, D-07).
- **Source levels.** No acoustic source level or dBm figure is ever turned into electrical power.
  - `desert.py` reads only time, duration, bits, outcome, medium and interface.
  - `units.py` refuses conversions from dB re 1 µPa or dBm to W.
- **Numeric values.** All values in the per-device table match their primary sources. Every TX figure is worded as electrical consumption in its source.
- **Maximum-only values.** These are flagged as upper bounds and kept in the reports: Ping360, both cameras, Gemini (value_max), Surveyor PINGING_MAX, Subnero, S2C M RX/LISTEN, LUMA TX, Seatooth, SX1276 and AHOI TX.
  - The S5 summary carries 0.596 Wh of upper-bound energy.
  - `comm_matrix.json` lists the upper-bound states, and the 72–95 % share quoted in RESEARCH_STATUS matches.
- **Unknowns stay unknown:** EdgeTech, Jetson idle, A50 startup duration, BlueComm standby, Fathom-X, the BEC and the power-sense module.
- **Communication energy agrees with the native events.**
  - The comm matrix reproduces 9/9 configurations exactly.
  - The native non-interference check (e01) passes again.
  - The sampled-time check (B2, WHOI) agrees to within 3e-5.
  - Bus minus adapter is ≤ 2e-15 Wh in `crosslayer.json`.
  - TX takes priority and overlapping receptions are merged correctly.
- **Declared overlaps are detected** (Navigator/IMU, SPRINT-Nav/A50, modem DSP/compute), and policy `error` rolls back cleanly. The logic is wrong for distinct devices (D-06).
- **LISTEN = RX** is the correct reading for S2C M without a Wake-Up module and for ATM-900, and both profiles say so.
- **SPRINT-Nav Mini** does integrate the DVL, inertial sensors and pressure sensor, as its datasheet states.
- **Acknowledged limits.** RESEARCH_STATUS correctly states that vehicle modem energy is invariant across strategies, the 4.8 vs 13.9 kbit/s mismatch, RX/LISTEN priced at the maximum, and the dirty-tree provenance. D-01, D-02, D-03 and D-11 concern what these statements leave out, or claims worded more strongly than they support.
