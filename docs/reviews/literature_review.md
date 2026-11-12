# Reviewer A: literature and provenance audit

**Scope.** I checked the scientific parameters of HoloEnergy against their cited sources. The review covers branch `feature/provenance-aware-energy-framework`, from tag v0.2.0 up to HEAD `69bd3d7`.

**Files read.**
- Registry: `holoenergy/evidence/data/{sources,literature}.yaml` and `parameters/*.yaml`.
- Profiles: the BlueROV2 vehicles, the T200 actuator and its JSON table, both 4S 18 Ah battery profiles, the 19 component profiles, the 13 modem profiles, the hydrodynamic datasets and the four proxy vehicles with their batteries.
- Usage code: `models/components.py`, `evidence/runtime.py`, `experiments/run_offline_campaign.py` (SUITES) and `run_comm_matrix.py`.
- Paper-facing text: `docs/paper_outline_smpat.md`, `docs/PROVENANCE_FRAMEWORK_FINAL_REPORT.md`, `README.md`, `docs/paper/tables/*`, `docs/paper/MODEL_EQUATIONS.md`, `data/evidence/final_parameter_audit.md`.

**Sources checked.**
- Primary sources, in their current online versions: Blue Robotics pages and datasheets, Water Linked, Tritech, Kongsberg, Cerulean, Blueprint, VectorNav, u-blox, TE, Sonardyne, Sea-Bird, Turner, EdgeTech, Subnero, EvoLogics, WHOI, Teledyne Benthos, Hydromea, Semtech, WFS, Raspberry Pi and NVIDIA.
- Open-access papers: Renner 2020, Rey 2025, Ulmamei 2025, Baller 2021, von Benzon 2022 (AAU repository copy), the Gabl 2021 accepted manuscript (PolyU IRA) and the Wu 2018 thesis.
- Local read-only PDFs: P017, P018, P022, P023, P024, P025, P029, P032, P041, P047.
- The unchanged T200 workbook S6, including its "READ ME FIRST" text box and its cell formulas.

**Method.** Each value was recomputed from the source figure and the stated derivation. For PDFs I used `pdftotext`, and I rendered pages to images where a table's layout was ambiguous.

**Not re-verified.**
- HoloOcean C++ literals (`HO-SRC-2.3.0`): the v2.3.0 source paths were not reachable in this session.
- Gabl et al. 2020 (Data; MDPI blocked automated download): the vehicle description in `bluerov2_standard.restrained_inline_load_head_on.conditions` was therefore not checked.
- Lam et al. 2023 (P001): paywalled.
- Tethys bollard Table I values (P032 Table I is an image).

Severity is defined as follows:
- **critical:** invalidates a result or claim.
- **major:** a used number, grade or claim is wrong or materially overstated.
- **minor:** everything else.

**No critical finding.** Every numeric value used by the BlueROV2 profiles, the S0-S6 suites, the modem profiles and the proxy vehicles matches its source within the stated derivation. The problems are in how evidence is labelled and claimed, plus two condition mismatches.

## Findings

| ID | Sev. | Record / profile, file:line | What the repo says | What the source actually says | How checked | Suggested fix |
| --- | --- | --- | --- | --- | --- | --- |
| A-01 | major | `docs/paper_outline_smpat.md:106`; `docs/PROVENANCE_FRAMEWORK_FINAL_REPORT.md:167`; `profiles/actuators/bluerobotics_t200.yaml:10` (`status: MEASURED`) | The validation hierarchy lists "component (manufacturer tables)". The final report lists "Component level: by construction from manufacturer tables" under "External validation". RQ6 (outline l.22) says component data are "reproduced by construction". | Manufacturer tables are the model *input*. Reproducing an input is not validation: there is no independent measurement at component level. The T200 workbook is one thruster (made Aug 2019) with one ESC (Basic ESC R3, BLHeli_S 16.6) in a manufacturer tank (S6, "READ ME FIRST" sheet). | Read the outline, the report and the S6 text box; traced the T200 profile to the workbook. | Remove "component" from the validation levels, or rename it "input traceability (not validation)". State that no component was independently tested. Use `status: MANUFACTURER_DATA` for S6 rather than `MEASURED`. |
| A-02 | major | `evidence/data/parameters/actuators.yaml:37-46` (`bluerobotics_t200.inflow_model`); `README.md:438-439`; `docs/EVIDENCE_GAPS.md:5` | The record says no published non-zero-advance-speed T200 data "were identified". The README says "no published data cover thrust/power at advance speed". | The repo's own registry lists P001 (Lam et al. 2023, doi:10.1109/oceanslimerick52467.2023.10244513), whose workbook entry says it reports non-bollard propeller performance and input power. EVIDENCE_GAPS records it as read at abstract level only. The gap is one of *access*, not of *existence*. | Compared `literature.yaml` P001 with the record, the README and EVIDENCE_GAPS. A web search found no open copy. | Change the wording to "one peer-reviewed source (P001) reports non-bollard T200 data; it was not accessed". Obtain P001 before claiming that no data exist. |
| A-03 | major | `profiles/vehicles/bluerov2_heavy_holoocean.yaml:69`; `bluerov2_standard_6t.yaml:41`; `data/evidence/final_parameter_audit.md:12,26-29` | `battery_losses` is linked to `bluerobotics_4s_18ah.dc_resistance_cell_derived` with `relation: exact`. The paper audit table prints "Applied relation: exact" for the cell-derived resistance (record: proxy), von Benzon damping (representative), both Gabl records (representative) and Wu 2018 damping (proxy). | The source chain is: Samsung 30Q cell DC-IR (typical value, fresh cell), times 4/6, with the cell identity only *implied* by a linked PDF. This is a proxy by the record's own definition (`batteries.yaml:85-104`). Gabl's vehicle is a modified 6-thruster standard frame. Wu's coefficients come from the original BlueROV. | `cap_grade` keeps the grade at C/B/D, so the grades are right. The printed relation is wrong, and it appears in a paper table. | Set `relation: proxy` in both vehicle profiles. Make `build_parameter_audit.py` print the record's relation, or the stricter of record and link, instead of the link default. |
| A-04 | major | `parameters/sensors.yaml:201-219` (`tritech_gemini_720is.power_range`); suite `S5-inspection` (`experiments/run_offline_campaign.py:378`) | Gemini 720is: 16-27 W, relation exact, grade A. In S5 it is powered from the BlueROV2 14.8 V pack (12-16.8 V), with `payload_efficiency: 1.0`. | Datasheet 0703-SOM-00001 Issue 15, p.2: supply voltage 19-74 Vdc, power 16-27 W "range dependent". Footnote: the figure is for a standalone unit and excludes cable losses. The device cannot run from the BlueROV2 bus without a boost converter, whose losses are neither modelled nor declared. | Read the datasheet text (agent extraction re-checked by me); compared it with the pack OCV range in `bluerobotics_4s18ah_v2.yaml`. | Record `supply_V: 19-74` in `conditions`. In S5, declare the required step-up converter as an unconfigured gap (grade D), or use a sonar whose supply range covers the bus. Mention this in the RQ3 text. Also check every added device against the bus range: the others (DVL A50 10-30 V, Ping360 11-25 V, Lumen 10-48 V full brightness, 4K cam 5-55 V) are compatible. |
| A-05 | major | `docs/paper_outline_smpat.md:20` (RQ4); `profiles/communications/evologics_s2cm_18_34_1000m.yaml`; `parameters/comms_compute.yaml:123-136` | RQ4 says the acoustic modem "adds at most 1.37 %", with RX/listen priced at the published 0.8 W maximum. | EvoLogics S2C M product information (Dec 2017), p.1, power consumption, footnote 2: figures are for the RS-232 interface option. Ethernet adds 500 mW and a wake-up module adds 300 mW. TX is a range-setting value (2.8 W at 1000 m, 8 W at 2000 m, 55 W max), not a bound. The DESERT PHY used for airtime (4.8 kbit/s, 25 kHz centre, 5 kHz band; `run_comm_matrix.py:52-57`) is not the S2C M 18/34 PHY (18-34 kHz, up to 13.9 kbit/s). "At most" therefore holds only for RS-232, the 1000 m setting and DESERT's airtime. With Ethernet, the listen power is 1.3 W (+62 %). | Read the EvoLogics PDF (agent extraction) and the profile and record conditions; read the DESERT PHY settings. | Replace "at most" with "for the RS-232 variant at the 1000 m setting". State the interface assumption in the profile. Report the PHY/device mismatch as a representative-relation caveat. Optionally add the Ethernet variant as a sensitivity case. |
| A-06 | minor | `sensors.yaml:164-180` (`bluerobotics_lumen.power_full`); suite S5 `lights_on` | 15 W, `bound: nominal`; not flagged as an upper bound in the paper tables. | Lumen page (BR-100857, R4): the spec table gives "Peak Current (15/Vin) A". The 15 W figure appears in the description at full brightness. Full brightness is specified for 10-48 V only. Dimmed power is not published. | Agent page fetch; compared it with `component_sources.md`. | Use `bound: upper_bound` (peak, full brightness). Declare S5 "two lights at full brightness for the whole mission" as a scenario assumption: this one choice is about 30 W of the S5 suite. |
| A-07 | minor | `batteries.yaml:60-70`; `bluerov2_heavy_holoocean.yaml:23,27` | `max_temperature` of 50 °C, used as `cutoff_temperature_C` for discharge. | Blue Robotics (Guides tab) gives 50 °C as an exposure limit for the batteries ("do not expose…"), not a rated discharge cutoff. The pack page gives no operating range. | Agent page fetch. | Keep the value but describe it as "exposure limit used as cutoff (interpretation)". |
| A-08 | minor | `batteries.yaml:71-104`; `evidence/runtime.py:309` | Pack R of 13.29 mΩ is declared a lower bound. Battery-loss energy is graded C. Capacity is 18 Ah at all currents. | Samsung "Introduction of INR18650-30Q" (Aug 2014; marked "Spec. (Tentative)"), p.3: DC-IR 19.94 ± 2 mΩ *initial*, AC-IR 13.13 mΩ. Capacity is 3.0 Ah at 0.2C but 2.7 Ah at 10 A, and 60 A pack current is 10 A per cell. The runtime reports an *upper*-bound energy share but no *lower*-bound share. Battery losses computed from a lower-bound R are therefore not flagged as under-estimates. | Recomputed 4 × 19.94/6 = 13.29 mΩ; read the runtime bound accounting. | Report the lower-bound energy share (battery losses) next to the upper-bound share. Note in the record that the source is a tentative presentation. Note in the profile that rate-dependent capacity (−10 % at 10 A per cell) is not modelled. |
| A-09 | minor | `comms_compute.yaml:732-746` (`rpi4b.video`); `profiles/components/raspberry_pi_4b.yaml:9`; suites S2/S3/S5/S6 | The record is relation exact, grade A, `measured_mean`, 3.9 W, workload "H.264 video playback". The profile caps it to B. | Raspberry Pi documentation, power-supply section, per-workload table (Pi 4B, "June 2019", measured with HDMI, keyboard, mouse and Ethernet attached). Video *playback* decodes to HDMI. BlueOS *forwards* an already encoded camera stream, so this is a different workload and different peripherals. | Agent fetch of the RPi documentation source (`power-supplies.adoc`). | Keep the record exact for its stated condition, but change the BlueROV2 mapping to `relation: proxy` (C), or justify B in text. Note the 2019 firmware date. |
| A-10 | minor | `comms_compute.yaml:834-849` (`jetson_orin_nx_16gb.yolov8s_fp16`); suite S6 | 12.815 W mean power, grade B; nvpmodel "not stated". | Rey et al. 2025, Table 4 (arXiv 2502.15737 p.15): the column header is W·s. The value is mean power, which is consistent with the J/inference column (12.815 × 60/2760 = 0.279). Other conditions: power read with tegrastats (module VDD_IN, not the carrier board); throughput-maximising run (48.24 FPS); power mode not stated. The text contradicts Table 4 for the Orin Nano (7.4 → 8.7 W "FP32 → INT8" versus the table's 8.790 FP32 and 7.257 INT8). | Agent page render plus my arithmetic. | Add these conditions to the record. State that S6 assumes inference at maximum rate. Carrier-board and DC-DC losses are excluded. |
| A-11 | minor | `actuators.yaml:3-24`; `profiles/thrusters/bluerobotics_t200.json` | Basic ESC; static/bollard; zero power below about \|u\| = 0.08-0.11. | S6 "READ ME FIRST": Basic ESC **R3** with BLHeli_S **16.6**; a single T200 from Aug 2019 with a 1 m 18 AWG cable. All values below 300 RPM were dropped to zero by the manufacturer, so the deadband is a processing artefact, not a measured zero. Current is reported in 0.05 A steps at low load. The current product page lists a 16 AWG cable and propeller material changes in 2024 and 2026. | Unzipped the workbook text box; read the cells and formulas (14 V / 1548 µs: current 0.01 A, power hard-coded 1.4 W). | Record ESC R3/BLHeli_S 16.6, the 300 RPM zeroing and the hardware revision in `conditions`. State that low-thrust (station-keeping) power below about 0.4 N is a linear interpolation to zero. |
| A-12 | minor | `docs/bluerov2_hydrodynamic_external_comparison.md:131` | Gabl's active-thrust cases (−92 N forward, 86 N backward, 64 N lateral) are dismissed as "not drag". | Gabl et al. 2021 (accepted manuscript, Sect. 3.2, Fig. 5) report still-water sums of restrained forces with the thrusters active. This is the static (zero-inflow) condition of the T200 tables, measured on an installed 6-thruster vehicle. My estimate from the S6 tables, assuming full throttle and ignoring interaction, is about 112-129 N surge at 14-16 V. Bus voltage and ArduSub gain are not reported by Gabl 2021. | Read the manuscript; computed 0.7071 × 2 × (F_fwd + F_rev) from the workbook. | Use it as the only installed-vehicle check of the propulsion force domain, after extracting voltage and gain from Gabl 2020 or DataShare. If no conditions are available, cite it as a qualitative check. |
| A-13 | minor | `sensors.yaml:52-65` (`waterlinked_dvl_a50.startup_duration`) | Record says "Not published by the manufacturer". | Water Linked docs (electrical/LED section): the DVL can take about 30-60 s to power on, depending on configuration. Power during boot and the duration of the 35 W surge are not published. | Agent fetch of docs.waterlinked.com/dvl/electrical/. | Record the 30-60 s boot time as published. Keep power during boot unconfigured. |
| A-14 | minor | `comms_compute.yaml:404-425` (`ahoi.idle_rx`, `ahoi.sleep`); `ahoi_bridge_max.yaml` | LISTEN/RX 0.3 W for the bridge-amplifier profile; sleep 1 mW, `upper_bound`. | Renner et al. 2020, §4.3 (pp.18:18-18:19): the 300 mW idle/receive total assumes the transmitter is asleep. The bridge transmitter idles at 791 mW. In sleep the whole modem draws "a few milliwatts", whereas <1 mW is the transmitter board alone. | Agent extraction of the open copy. | State the transmitter-asleep assumption for LISTEN. Use "a few mW" (unconfigured or range) for whole-modem SLEEP, or call 1 mW a transmitter-only bound. |
| A-15 | minor | `comms_compute.yaml:559-578` (`semtech_sx1276.tx_*`) | TX at 29 mA (+13 dBm) and 87 mA (+17 dBm) from Table 6. The profile RX uses the LoRa Table 10. | SX1276 Rev 7: Table 6 is FSK mode. The LoRa Table 10 (p.19) gives 28 mA (+13 dBm RFO) and 90 mA (+17 dBm PA_BOOST). | Agent page render. | Use Table 10 values for a LoRa profile, or label the TX bracket as FSK. The profile is unused in experiments. |
| A-16 | minor | Several records | Source conflicts not recorded. | VectorNav VN-100 Rugged: 40 mA @ 5 V = 200 mW, but the page states 220 mW and also "200 mW" elsewhere (only the SMD conflict is noted, `sensors.yaml:318`). WHOI MM2 hibernate: 0.96 mW at 12 V (2018 table) versus 455 µW at 12 V (Gallimore 2010, Table I, already in `sources.yaml`). Rey 2025: the text contradicts Table 4 (A-10). | Agent extractions. | Add `notes` with both values, as already done for the ATM-900 and the Ping360. |
| A-17 | minor | `sensors.yaml:546-578` (`bluerov2.runtime_*`) | ~2 h / ~4 h runtime, relation exact, grade A, battery 15.6 Ah. | The BlueROV2 page ties the hours to the discontinued 15.6 Ah pack. The 2025 BlueROV2 datasheet ties the same hours to the 18 Ah pack. The 18 Ah page says "up to 4 hours of continuous moderate use". "Normal" and "light" use are undefined. | Agent fetch of the page and datasheet. | Grade it at most B (undefined operating condition). Record the battery conflict. Keep it out of any validation claim (currently unused). |
| A-18 | minor | `proxy_vehicles.yaml:248-261` (`remus100.hotel_power_nominal`); `torpedo_remus_like.yaml:33,37` | "Nominal hotel power of the REMUS 100 power model (vehicle with INS, DVL and ADCP)". | P023 (doi:10.1109/auv53081.2022.9965807) p.3: the 60 W, J = 0.53, Cp = 0.12 and d = 0.14 m are assumptions for "a small AUV" in the model example. INS/DVL/ADCP is the equipment of the REMUS 100 *field test* (p.5), not a stated composition of the 60 W. | Local PDF text (P023 pp.3, 5). | Describe it as an "assumed hotel power of the source's model example". Drop the "do not add INS/DVL/ADCP" inference, or mark it as an interpretation. |
| A-19 | minor | `proxy_vehicles.yaml:262-289` (`remus100.scripps_lap*`) | Lap 1: 2051 m, 46.6 Wh, 1105 s, 1381 rpm. | P023 Table I (p.5): the row labels are offset by one row in the source (e.g. "Energy Consumed (W.hr)" sits on the 2051/1973/1976 row). The repo's realignment agrees with the text (6.43 Wh saved, 13.7 %). However, 46.6 Wh over 2.051 km is 22.7 Wh/km, which conflicts with the realigned dE/dR value of 21.6. | Local PDF text. | Note the source misalignment and the dE/dR inconsistency in the record. These are cross-check-only values. |
| A-20 | minor | `profiles/batteries/proxy_alr6000_38kwh.yaml:9` | L0 bucket at the installed 38 kWh; the 40 % overstatement is declared in a note. | P024 (doi:10.1109/joe.2021.3058416) p.5, §IV-A: about 27 kWh recoverable at 25 W total and below 22 kWh at 50 W. The proxy's own hotel load (15 W) plus propulsion lies in that range. | Local PDF text. | Default to the source's recoverable 27 kWh for the proxy, or report endurance with both values. |
| A-21 | minor | `proxy_vehicles.yaml:172-195, 323-341, 435-451` | Proxy force→power tables pair measured or quoted power with thrust = drag. | REMUS (P022 Table 5, p.4): 3.60 lbf is a lifting-line *design prediction* at 4.5 kn, scaled by v². Tethys (P032 p.6): the 7 N is a drag estimate while flying nose-down against positive buoyancy. ALR6000 (P024 Fig. 12 caption, p.8): Eq. 12 was measured at about 25 N net buoyancy, so actual thrust exceeds the zero-lift drag of Eq. 7. The derivations are declared, but these thrust-side conditions are not all stated. | Local PDF text. | Add "thrust side: design/estimate, buoyancy-affected" to `conditions`. Grade C stays appropriate. |
| A-22 | minor | `proxy_vehicles.yaml:27-52` (`mares.thruster_force_power_linear`) | kT ≈ 5 W/N. | P017 p.5, Eq. 13: kT is said to be estimated from experiments, about 5, with no unit stated. W/N is implied by P = kT F but not printed. Table I values (2.16e6 J, 15 W, η = 0.15, Kdu = 4 kg/m) and the about 2 m/s surge limit (p.6) all match. | Local PDF text. | Note "unit inferred from Eq. 13". |
| A-23 | minor | `hydrodynamics.yaml:158,163`; `paper_outline_smpat.md:22` | The record gives the identified range as up to 0.72 m/s and the HoloOcean/von Benzon ratio as 0.86-1.16 (0.2-1.0 m/s). RQ6 says 1.13-1.21 within "0.2-0.6 m/s". | von Benzon 2022 Table 4 (p.8): x_max 0.72 m/s at 85 N; Sect. 4.2: steps of 20-100 % input. The two ratios differ because RQ6 includes UE linear damping (11.5 v). My recomputation confirms both. | Recomputed from Table A1 (13.7 u + 141 u\|u\|). | Use one stated speed range, and say in both places whether linear damping is included. |
| A-24 | minor | `sensors.yaml:423-441` (`te_ms5837_30ba.power_1sps_osr8192`); `docs/paper/tables/sensor_table.md` | 60 µW (20.09 µA × 3.0 V) mapped to the HoloOcean DepthSensor, grade A. | TE datasheet REV C6, p.2: 20.09 µA at 1 sample/s, OSR 8192; no VDD is given in that row. ArduSub samples the Bar30 much faster, and current scales with rate, so 1 sample/s is not the operating condition. | Agent extraction. | Grade B, or state "1 sample/s only". Negligible energy. |
| A-25 | minor | `docs/paper/tables/component_sources.md:22`; `final_parameter_audit.md:26` | "Benzon et al. 2022". | The first author is Malte **von** Benzon (JMSE 10(12):1898). | PDF title page. | Cite as "von Benzon et al. 2022". |

## Records verified as correct (value, unit, location and bound match the source)

**Battery, Blue Robotics 18 Ah R3 page and Samsung document**
- `bluerobotics_4s_18ah.capacity` / `energy_nominal` / `nominal_voltage`: 18.0 Ah, 266.4 Wh, 14.8 V.
- `bluerobotics_4s_18ah.minimum_voltage`: 12 V (3.0 V/cell).
- `bluerobotics_4s_18ah.max_continuous_current`: 60 A; the 132 A for 10 s burst is correctly not enabled.
- `samsung_inr18650_30q.dc_resistance`: 19.94 ± 2 mΩ DC (10 A-1 A), p.3 and p.5.
- `bluerobotics_4s_18ah.dc_resistance_cell_derived`: arithmetic and proxy grade correct; only its link relation is wrong (A-03).
- `bluerobotics_4s_15_6ah.*`: 15.6 Ah / 230 Wh, Molicel P26A cells, 4S6P, 12 V, 60 A; discontinued.
- `battery.hydrostatic_pressure_effect`:
  - P041: NCM811 soft-package cell, discharge capacity +9.2 % at 60 MPa (J. Energy Storage 73:108979).
  - P047: LiFePO4 cell, 2.80 → 2.60 Ah (−7.1 %) at 100 MPa (Table 2).

**T200 (S6 workbook)**
- `bluerobotics_t200.static_force_power_curve`:
  - SHA-256 matches; 6 voltage sheets.
  - u = (PWM − 1500)/400; kgf × 9.80665.
  - Power = I × V formula; the 14 V / 1548 µs anomaly is handled correctly.
  - Bollard and zero-inflow conditions match the README.
  - Full-throttle powers match the product page (205/390/645 W at 12/16/20 V).
- `bluerobotics_t200.voltage_domain`: 10-20 V data domain.

**Blue Robotics devices**
- `bluerobotics_navigator.power_idle` / `power_typical` / `power_max`: 5 mA, 150 mA and 200 mA; supply 5-5.35 V; derivations declared.
- `bluerobotics_lowlight_usb_camera.power_max`: 220 mA × 5 V, upper bound.
- `bluerobotics_4k_camera.power_max`: 5 W, upper bound (BR-103829).
- `bluerobotics_ping360.supply_voltage` / `power_max`: 11-25 V (the 11-18 V conflict is noted); 5 W maximum.
- `bluerobotics_ping_sonar.power_typical` / `power_peak`: 100 mA typical, 900 mA peak, 4.5-5.5 V.

**Third-party sensors**
- `waterlinked_dvl_a50.supply_voltage` / `power_average` / `power_on_surge`: 10-30 V, 4 W average (no ping-rate condition in the source), 35 W maximum.
- `blueprint_oculus_m750d.power_range`: 10-35 W family range, grade B appropriate.
- `cerulean_surveyor_240_16.*`: 5 W idle, 15 W "typical max" while pinging.
- `kongsberg_m3_500m.*`: 22 W average, peak below 60 W.
- `tritech_micron.power_average`: 4 VA average.
- `edgetech_2205.power`: no number published; unconfigured is correct.
- `vectornav_vn100_smd.power`: conflict recorded.
- `ublox_zed_f9p.*`: Table 13 (68/85 mA tracking, 75/90 mA acquisition, measured at 25 °C, indicative); VCC 3.0 V typical (Table 12); I_BCKP 45 µA at 3 V; UBX-17051259 R09, 24-Mar-2023.
- `sonardyne_sprint_nav_mini.power_nominal`: 24 V, 10 W nominal; integrated DVL, INS and pressure sensor.
- `seabird_sbe49.power_sampling`: 285 mA at 12 V, 180 mA at 19 V, 350 mA at 9 V, pump included.
- `turner_cyclops7f_chlorophyll.power`: 240 mW at 12 V.

**Communications**
- `subnero_wnc_m25mso4.*`: TX below 45 W average, RX below 4 W, deep sleep below 1 mW, up to 15 kbit/s, 24 V.
- `evologics_s2cm_18_34.*`: 2.8/8/35/55 W TX by range setting, RX below 0.8 W, listen 5-285 mW with wake-up module, 2.5 mW standby, 13.9 kbit/s.
- `evologics_s2cr_18_34.*`: up to 65 W (2024 guide; the web-page conflict is noted), RX 0.8 W.
- `whoi_micromodem2.*`: about 60/35 W TX, 0.82 W FSK RX and idle, 2.74 W PSK RX at 12 V.
- `benthos_atm900.*`: 20/10/5/2.5 W at levels 8/6/4/2 at 21 V; RX 650 mW typical / 720 mW max; lowpower 10.2/12.0 mW; the §3 conflict is noted.
- `ahoi.tx_bridge`: 1.1-2.1 W.
- `sonardyne_bluecomm200.*`: receiver 10 W, emitter 15 W (6 W radiated light is correctly *not* used); the 25 W node value is declared and graded B.
- `hydromea_luma250lp.*` / `hydromea_lumax.*`: 2-5 W / 2-20 W TX typical; RX 0.5 W / 2 W; sleep below 10 mW.
- `semtech_sx1276.rx_lora_125khz` / `standby` / `sleep`: 10.3 mA, 1.6 mA and 0.2 µA at 3.3 V.
- `wfs_seatooth_s100.*`: 1-7 W TX, 86 mW RX, 5 mW sleep, 2.4 (4.8) kbit/s.

**Compute**
- `rpi4b.idle` / `stress` / `halt`: 0.6 A, 1.2 A (1.25 A max) and 0.023 A from the official Pi 4B table.
- `rpi4b.idle_baller2021`: 2.643 W with LAN, 2.100 W without (Table III).
- `rpi5.bare_board`: 800 mA.
- `jetson_orin_nx_16gb.budget_10w/15w/25w`: nvpmodel budgets (the Super variant also has 40 W); correctly treated as caps, not consumption.
- `jetson_orin_nx_16gb.yolov8s_int8`, `jetson_orin_nano.yolov8s_fp16`, `rpi5.yolov8s_ncnn`: 11.002, 7.836 and 5.422 W, as read from Table 4 (see A-10).
- `jetson_agx_orin.idle_15w` / `inference_15w`: 6.39 W and 9.91 W (Ulmamei 2025).

**Hydrodynamics**
- `bluerov2_standard.restrained_inline_load_head_on`: Table 1, p.9, d = ∞; −0.6/1.0/6.4/16.4/28.8/45.2/46.9 N.
- `bluerov2_standard.restrained_equivalent_drag_area`: 0.090-0.094 m², recomputed.
- `bluerov2_heavy.translational_damping_identified`: Table A1 (13.7/141, 0/217, 33/190, origin "Experimental"); m = 13.5 kg; Table 4 gives 0.72 m/s at 85 N; Table 5 gives A_u = 0.0877 m².
- `bluerov2_heavy.translational_damping_wu2018`: Table 5.3, PDF p.56 (−4.03/−18.18, −6.22/−21.66, −5.18/−36.99); grade D is appropriate.

**Proxy vehicles**
- MARES:
  - `mares.hotel_load` / `battery_energy` / `propulsion_efficiency_surge_model`: P017 Table I.
  - `mares.thruster_force_domain`: derivation 4 × 2²/2 = 8 N.
  - `mares.vertical_hold_power` / `vertical_descent_power`: P018 p.6 (19.8 W, 38 W, 700 cm³, 0.2 m/s, 7.5 N).
- REMUS:
  - `remus.propulsion_power_3kn` / `5p6kn` / `battery_energy_2000`: P022 p.5 (15 W, 110 W, 1000 Wh; previously 65 W at 3.2 kn).
  - `remus.propeller_design_thrust_4p5kn`: Table 5 (3.60 lbf, 1525 rpm, 45.7 W, QPC 0.811).
  - `remus.hotel_load_1997` / `bus_voltage_1997`: P029 pp.2 and 6 (19.4 W itemised, 24 V, 48 × 2 V 5 Ah cells, 480 Wh).
- Tethys:
  - `tethys.propulsion_power_level_flight` / `propulsive_efficiency_measured`: P032 p.6 (12 W, 0.96 m/s, 300 RPM, 7 N, 0.87; 0.49 recomputed).
  - `tethys.low_speed_design_thrust`: P032 p.5 (2 N, 0.07 Nm).
  - `tethys.hotel_load` / `battery_energy_primary`: P025 pp.2-3 (5-8 W, 7 W, 13 kWh, 1800 km at 1 m/s).
- ALR6000:
  - `alr6000.*`: P024 (38 kWh, 7s8p × 10, 560 SL2780 cells, 25.2 V, 27 kWh at 25 W and below 22 kWh at 50 W, 15-240 mW/cell at 5 °C, 10 W computer, C_DV 0.049 at 1025 kg/m³, Eq. 12 P = 70.145 U^2.4333, 26-38 %, 15-20 W, 1.2 W, about 25 N buoyancy).
- AMOUR V, Silver Frog and the dual-electric USV: the unsupported (D) records match the reasons given.
