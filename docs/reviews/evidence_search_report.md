# Evidence search report (2026-11-12)

Scope: five focused searches requested for HoloEnergy (T200 at advance speed, BlueROV2 Standard
vertical-thruster geometry, BlueROV2 battery, modem electrical power, external validation data).
Method: web search and fetch of primary sources, and text extraction of the local PDFs indexed in
`holoenergy/evidence/data/literature.yaml` into a scratch directory outside the repo. No PDF content is
copied here beyond individual numbers and very short labels. No repository file other than this report
was modified. Nothing was committed and no simulator was run.

Grades follow the registry convention (A: manufacturer/peer-reviewed exact value; B: representative;
C: proxy/derived; D: unsupported). "Typical" and "maximum" are reported as the source states them.

Downloads that were **not** performed because they need the user's approval are listed in section 6.

---

## 0. Summary of usable findings

| # | Finding | Source (location) | Grade | Record ids affected |
|---|---|---|---|---|
| F1 | Vertical thrusters of the BlueROV2 (6T) are **221.0 mm apart** centre-to-centre, so y = ±0.1105 m | Blue Robotics 2D drawing `2d-drawing-brov2-2018.png`, top view, dimension "221.0 MM [8.70 IN]" (linked from the current product page) | A (y only) | `profiles/vehicles/bluerov2_standard_6t.yaml` V1/V2 `position_m[1]`; `evidence.geometry` (currently `record: null, relation: proxy`); EVIDENCE_GAPS row "BlueROV2 Standard vertical thruster positions" |
| F2 | The cells of the 18 Ah pack are confirmed as **INR18650-30Q, 24 cells** (4S6P implied) | Blue Robotics-hosted UN38.3 test report TCT231027B027 V3.0 (issued 2023-11-15), p. 2 "Sample Description", model BATTERY-LI-4S-18AH-R1 | A (cell identity) | `bluerobotics_4s_18ah.dc_resistance_cell_derived` (removes the stated assumption; the value stays a lower-bound proxy, C) |
| F3 | LUMA 250LP data rate **250 kbit/s**, "up to 600 Kpbs at reduced range", max range 7 m | Hydromea LUMA 250LP datasheet V1.241007 (preliminary), p. 1 System Specifications (= `DS-HM-LUMA250LP`) | A | new `hydromea_luma250lp.bitrate`; closes gap row "Hydromea LUMA 250LP bitrate" |
| F4 | Teledyne Benthos ATM-900: TxPower levels 1–8 = −21 dB … 0 dB in 3 dB steps; maximum source level 185 / 183 / 178 dB re 1 µPa @ 1 m (LF / MF / band C omni), 190 dB (directional); average TX electrical power per level already recorded | ATM-900 User's Manual P/N M-270-26 Rev. D (= `DS-TB-ATM900`), pp. 2-2 to 2-3 and p. 8-53 | A (per-level attenuation and max SL); per-level SL is an inference (see 4.3) | `benthos_atm900.tx_level{2,4,6,8}` (add SL); new `benthos_atm900.source_level_max`; gap row "electrical TX power vs source level" (Benthos only) |
| F5 | EvoLogics: power figures are for RS-232; **+300 mW with the Wake-Up module, +500 mW with Ethernet**; "User-configurable Listen Mode is only available with a Wake-Up module installed" | EvoLogics Product Information Guide 2024 (`DS-EL-GUIDE-2024`), p. 4 footnote 2; S2C M sheet Dec 2017 (`DS-EL-S2CM-2017`) p. 1 footnotes | A | `evologics_s2cm_18_34.rx`, `.listen_wakeup`, `evologics_s2cr_18_34.rx` (notes/conditions); supports the current RX = LISTEN choice for a modem without Wake-Up module |
| F6 | Open 30Q dataset with relaxed OCV (45 min) at 5 SOC points and EIS, 8 cells, every 25 cycles | Leonardi et al. 2026, Mendeley Data, doi:10.17632/g7ncmhrcrz.2 (CC BY 4.0) | B/C for the pack once downloaded | `bluerobotics_4s_18ah.ocv_curve` (D placeholder) could become a 5-point cell-derived curve; not yet extracted (download needs approval) |

Nothing usable was found for: T200 thrust/power at non-zero advance speed (`bluerobotics_t200.inflow_model`
stays D), the longitudinal (x) position of the vertical thrusters from a dimension, pack-level OCV or
resistance of the Blue Robotics pack, peer-reviewed BlueROV2 hotel-load or current/voltage logs,
peer-reviewed measurements of EvoLogics/Subnero/LUMA power, and any BlueROV2 mission-level energy data.

---

## 1. Blue Robotics T200 at non-zero advance speed

### 1.1 Sources found

1. **Lam, J., Chen, A., Bennett, A., Triantafyllou, M. (2023).** Propeller Characterization Testing of a
   Blue Robotics T200 Thruster. OCEANS 2023 – Limerick. doi:10.1109/OCEANSLimerick52467.2023.10244513
   (registry P001).
   - Access: closed (Semantic Scholar `openAccessPdf` = none; IEEE page returned no content to the
     fetcher; ResearchGate 403). Only the abstract was read.
   - What the abstract states: (i) bollard tests on a 6-DoF load cell compared with Blue Robotics data;
     (ii) tow-tank tests at advance ratios J = 0.19 to 0.97 at 11.6 rev/s, which did not show the expected
     behaviour; (iii) a retest at 34.5 rev/s (≈2070 rpm) that did, but only a **partial** curve because of
     the tank/carriage limits; the authors call for a larger tank with a faster carriage.
   - A search-engine snippet of the full text mentions a ~1 m/s carriage limit; not verified.
   - The abstract does not mention supply voltage, ESC current or electrical power at advance speed.
2. **Blue Robotics forum, "T200 performance with relative speed"** (thread 11373). Not a primary data
   source, but it records the manufacturer's position: the published data are bollard thrust with zero
   inlet velocity; moving-water testing "isn't something we've yet had the capacity for"
   (Blue Robotics staff, 2022-12-12). A. Bennett (MIT) wrote on 2025-04-15 that the propeller tunnel was
   offline and that T200/T500 characterisation was planned. No result has been published that I could find.
3. **Blue Robotics T200 product page** (checked 2026-11-12): performance data file is still
   `T200-Public-Performance-Data-10-20V-September-2019.xlsx` (bollard). No moving-water data, no ESC idle current.
4. Papers citing Lam 2023 (10 listed by Semantic Scholar) were screened by title. None is a T200
   open-water dataset. "Characterizing Mathematically Parameterized Toroidal Propellers for AUV
   Applications" (OCEANS 2025, doi:10.23919/OCEANS59106.2025.11245016) may contain a stock-propeller
   baseline; not retrieved, unverified lead.
5. arXiv 2602.00823 (Syntakas & Vlachos, BlueROV2 current-harnessing MPC) fits T = a·P^b to the
   manufacturer 16 V data only (Sec. V-B, Eqs. 25–26; coefficients not reported). Not inflow data.

No towing-tank, cavitation-tunnel or flume dataset, thesis or open dataset reporting T200 thrust **and**
electrical power versus inflow speed was found.

### 1.2 Sufficiency for an inflow-aware force→power model

An inflow-aware model needs, for several supply voltages (the registry domain is 10–20 V) and commands:
thrust, electrical power (V·I at the ESC input) or shaft torque × rpm plus motor/ESC efficiency, inflow
speed (advance ratio), ideally J from 0 to the zero-thrust point and the reverse direction.

Lam 2023, as far as the abstract shows, gives at most a partial K_T(J) (possibly K_Q(J)) curve at one
rotational speed, with no voltage or current. **It is not sufficient.** If the full text has K_T/K_Q
tables, it could support only a shape check of thrust loss with J at fixed rpm (grade B/C), not
electrical power versus inflow.

**Records:** `bluerobotics_t200.inflow_model` stays `unsupported` (D). Gap row "T200 thrust/power at
non-zero advance speed" stays open. The local IEEE PDFs carry a University of Bologna licence stamp, so
the user can probably obtain the Lam 2023 full text through institutional IEEE access to confirm.

---

## 2. BlueROV2 Standard (6T) vertical-thruster geometry

### 2.1 Sources found

1. **Blue Robotics 2D drawing, `2d-drawing-brov2-2018.png`** (manufacturer). Linked from the current
   product page (Technical Details) as `https://docs.bluerobotics.com/brov2/cad/2d-drawing-brov2-2018.png`;
   the same file is in `bluerobotics/bluerobotics.github.io/brov2/cad/`.
   - Top view dimension between the two vertical-thruster centre marks: **221.0 mm [8.70 in]**.
     Overall 457.1 mm × 338.1 mm × 253.9 mm.
   - Lateral position: **y = ±110.5 mm** (half the dimension). Exact for the drawn 2018 design.
   - Longitudinal position: **not dimensioned**. Scaling the image (my measurement, grade C): centre marks
     at x-pixels 113.5 and 465.5 (352 px = 221.0 mm, 1.593 px/mm; the 338.1 mm width gives 1.594 px/mm and
     the 457.1 mm length 1.593 px/mm). The centre marks lie ≈14.5 px ≈ **9 mm forward of the mid-length of
     the 457.1 mm side panels** (the front, dome side, is at the bottom of the top view). The mid-length is
     not the CG or the body-frame origin, so this is only a bound on the order of magnitude of x.
   - Vertical (z) position: not dimensioned. It does not change the vertical-thruster wrench.
2. **ArduSub `AP_Motors6DOF.cpp`, `SUB_FRAME_VECTORED`** (ArduPilot master). Motors 5 and 6:
   roll factor +1 / −1, pitch factor 0, throttle −1, forward/lateral 0. Normalised factors, not lengths:
   they confirm a symmetric left/right pair with no pitch arm in the controller's frame, consistent with
   x ≈ 0. Argument order: (motor, roll, pitch, yaw, throttle, forward, lateral, testing_order).
3. **2017 developer Gazebo model** (`patrickelectric/bluerov_ros_playground/model/BlueRov2.urdf.xacro`,
   last commits 2017-11/12). Thruster map for thr5/thr6: `0 0 -1 0 ∓0.111 0` (roll arm 0.111 m, pitch arm 0);
   horizontal yaw arm 0.167 m. The file cites the GrabCAD BlueROV2 model as its CAD basis. This is the
   source of the repo proxy (0, ±0.11 m); the actual arm in the file is 0.111 m.
4. **Community Gazebo model, `clydemcqueen/bluerov2_gz`** (`models/bluerov2/configs.yaml`, last change
   2026-10): vertical thrusters at (0.0, ±0.109, 0.077) m; horizontal at (±0.14, ±0.092, 0) m; meshes from
   Blue Robotics GrabCAD. Heavy model: verticals at (±0.118, ±0.215, 0.064) m. Not primary (C).
5. **AquaChat++ (arXiv 2508.06554)**, Eq. 10: allocation-matrix entries include 0.111 and 0.167, the same
   numbers as the 2017 model; no lengths or source given. Not independent.
6. Not read (PDF > 10 MB, needs a download): P. Ng, MS thesis 2024 (hosted by Blue Robotics,
   `bluerobotics.com/wp-content/uploads/2025/01/ng_patrick_ms_thesis_2024.pdf`; Heavy, has a thruster
   allocation section) and a Politecnico di Torino thesis (`webthesis.biblio.polito.it/31918/1/tesi.pdf`;
   TOC lists TCM and roll identification). Unverified leads.
7. **Blue Robotics CAD**: `https://cad.bluerobotics.com/BLUEROV2-R4.zip` (375,730,995 bytes, Last-Modified
   2022-06-07) and `BLUEROV2-R3.zip` (258,262,015 bytes). Not downloaded. Measuring the vertical-thruster
   axes in this CAD is the only route to a manufacturer x position.

### 2.2 Comparison with the repo proxy

| Source | x (m) | y (m) | Type |
|---|---|---|---|
| Repo proxy (`bluerov2_standard_6t.yaml`) | 0.0 | ±0.11 | proxy (C) |
| Blue Robotics 2D drawing 2018 | not dimensioned (≈ +0.009 from panel mid-length, image-scaled) | **±0.1105** | A for y; C for x |
| 2017 dev Gazebo model | 0 (pitch arm 0) | ±0.111 | C |
| McQueen bluerov2_gz | 0.0 | ±0.109 | C |
| ArduSub vectored factors | pitch factor 0 | roll ±1 (normalised) | design intent |

The y proxy agrees with the manufacturer dimension to within 0.5 mm (0.5 %). **Usability:** y can be
re-sourced to the manufacturer drawing (exact, A) through a new record, e.g.
`bluerov2_standard.vertical_thruster_lateral_spacing` = 221.0 mm. x stays a proxy (C) unless the CAD is
measured; all sources agree on x ≈ 0 within about a centimetre.

---

## 3. Battery: Blue Robotics 14.8 V 18 Ah pack, INR18650-30Q, BlueROV2 hotel load

### 3.1 Pack identity and ratings (manufacturer)

- **UN38.3 Test Report TCT231027B027, V3.0, issued 2023-11-15** (Shenzhen TCT Testing Technology),
  hosted by Blue Robotics at `bluerobotics.com/wp-content/uploads/2019/07/14.8V-4S-18Ah-UN38.3-PUBLIC-2024.pdf`
  (scanned, 18 pages), p. 2 "Sample Description", model **BATTERY-LI-4S-18AH-R1**:
  cell model **INR18650-30Q**, **24 cells**, cell nominal 3.6 V, cell rated 3000 mAh; pack 14.8 V,
  18000 mAh / 266.4 Wh, limited charge voltage 16.8 V, standard charge 3.6 A, max continuous charge 9 A,
  end-of-charge current 180 mA, cut-off 12 V, standard discharge 18 A, maximum discharge 60 A;
  sample received 2017-04-07.
  - This removes the assumption in `bluerobotics_4s_18ah.dc_resistance_cell_derived` ("implied by the
    linked datasheet, not stated"). The value remains a lower-bound proxy (C): interconnects, wiring and
    connector are still excluded.
  - Version caveat: the report covers R1. The current R3 product page states 4S6P and links the 30Q
    datasheet but names no cell; it lists max charge current 20 A versus 9 A max continuous charge in the
    R1 report. Treat the cell identity as exact for R1 and representative for R3.
- **Product page R3** (checked 2026-11-12): no discharge curves, no OCV table, no resistance. Thermistor
  NTC β = 3435 K, R25 = 10 kΩ ±1 %; 60 A continuous, 132 A 10 s burst; 12 V minimum.
- **Blue Robotics "Lithium-ion Battery Guide"** (`bluerobotics.com/learn/battery-info/`): one generic
  discharge curve, with no stated load, temperature or rest, and text levels of about 3.75 V and 3.2 V per
  cell. Not usable for OCV–SOC.

### 3.2 INR18650-30Q cell OCV and resistance

1. **Leonardi, S. G., Lucà Trombetta, G., Musicò, G., Aloisio, D., Brunaccini, G., Sergi, F. (2026).**
   Lithium-ion cells EIS dataset with fitting and degradation modes (Version 2). Mendeley Data.
   doi:10.17632/g7ncmhrcrz.2, CC BY 4.0. Associated article: J. Energy Storage 154A (2026) 121144,
   doi:10.1016/j.est.2026.121144 (not read).
   - Dataset page: 8 Samsung INR18650-30Q cells (nominal 2.95 Ah as stated), aged to 80 % capacity; OCV read
     **after 45 min relaxation**; R_int reported as a **% increase**, computed as ΔV/I with ΔV between the
     OCV and the voltage 5 s after a constant-current step; EIS fitted with L, R_ohm, 2×(CPE, R_ct), W.
   - Protocol from Battaglia et al., MetroGREENST 2025, doi:10.1109/MetroGREENST67435.2025.11429011
     (accepted version, Univ. Messina repository), Sec. III and Table I: EIS every 25 cycles at
     **SOC 100, 75, 50, 25, 0 %**, 0.1 Hz–10 kHz, 10 mV excitation, Arbin LBT21044 with climatic chambers;
     ageing profiles at **25 °C** (cells 1–4, 7–8) and **45 °C** (cells 5–6), discharge 5C (15 A).
   - Usability: the cycle-0 OCV points of the 25 °C cells would give a **measured 5-point relaxed cell
     OCV–SOC curve** (×4 for the pack), better than the current illustrative placeholder. Limits: 5 points,
     45 min is not full equilibrium, check-up temperature not stated on the dataset page, absolute DC
     resistance may not be given (only % change), and EIS R_ohm underestimates DC pulse resistance.
     Candidate grade for the pack: C (cell-derived). Record: `bluerobotics_4s_18ah.ocv_curve`.
     **Requires downloading the dataset (not done).**
2. **Bussios, M., Goldar, A., Garone, E., Kinnaert, M. (2024).** Fast Determination of OCV Curve for
   Lithium-ion Batteries. ECC 2024, pp. 206–211, doi:10.23919/ECC64448.2024.10591299. According to the
   search index it tests the 30Q (and Sony VTC6) with C/50–C/100 charge/discharge averaging. Full text not
   retrieved (404); data availability unknown. Unverified lead.
3. Batemo cell explorer (Samsung INR18650-30Q): commercial model/data, resistances behind a paywall.
   Not usable under the project rules.

No pack-level OCV, pulse resistance or discharge curve of the Blue Robotics pack was found.

### 3.3 BlueROV2 hotel load and current/voltage logs

- No peer-reviewed paper or open dataset with BlueROV2 battery current/voltage logs or measured hotel
  load was found (searched for Ocean Engineering/JMSE/Sensors/arXiv papers, GitHub/Zenodo/figshare logs).
  P008 (Huang & Preece 2026) is simulation only. AquaChat++ has no battery model (only a "25 % per cage"
  planning rule).
- Non-primary indications, **not** recommended for records: Blue Robotics staff on the forum
  (thread 16018, 2024-02-15): "0.62 amps is a typical current consumption for the system at idle (hotel
  load)", with voltage and configuration not stated. Battery-life statements: legacy docs "~3 hours (normal
  use)" / "~5 hours (light use)" with the 18 Ah battery; current product page "~2 hours" / "~4 hours" with
  the 15.6 Ah battery. Use profiles are undefined.
- Record status: `bluerobotics_t200.esc_idle_power`, `bluerobotics_fathom_x.power`, `bluerov2.bec_5v_efficiency`
  stay D.

---

## 4. Acoustic and optical modem electrical power

### 4.1 EvoLogics S2C

- `DS-EL-GUIDE-2024`, p. 4, Technical specifications. Stand-by 2.5 mW (M HS: 0.5 mW); Listen Mode
  5–285 mW; Receive Mode 0.8 W in the 2024 table (the 2017 S2C M sheet says "less than 0.8 W").
  **Footnote 2:** values are for the RS-232 interface; add 500 mW with Ethernet; add 300 mW if the
  Wake-Up Module is installed; user-configurable Listen Mode is only available with a Wake-Up Module;
  Listen Mode power depends on the settings. Footnote 5: the Wake-Up Module is RS-232 only.
- `DS-EL-S2CM-2017`, p. 1: TX 2.8 W (1000 m) / 8 W (2000 m) / 35 W (3500 m) / 55 W max for the 18/34 column,
  with the same footnotes. No source level (dB re 1 µPa) is given per range setting, and no
  setting→power mapping for Listen Mode.
- Usability: the footnotes justify RX = LISTEN (0.8 W upper bound) for a modem **without** a Wake-Up
  Module. With the module, RX and TX each rise by 300 mW and LISTEN falls within 5–285 mW, but which value
  applies depends on unpublished settings. Records: add these conditions to `evologics_s2cm_18_34.rx`,
  `evologics_s2cm_18_34.listen_wakeup`, `evologics_s2cr_18_34.rx`.
- **Nothing usable found** for peer-reviewed measurements of S2C receive/listen/transmit power or energy
  per packet. The S2C/SUN/DESERT field-experiment papers found (e.g. ResearchGate 261507445) report energy
  derived from datasheet values; full texts were not accessible. The Computers 2021 comparison table
  (`https://www.mdpi.com/2073-431X/10/10/119`) quotes datasheet values (secondary).

### 4.2 Subnero WNC-M25MSO4

Product page and brochure (`subnero.com/brochures/Subnero-MF-Modems.pdf`): < 4 W receive (nominal),
< 45 W transmit (avg.), < 1 mW deep sleep, 22–28 V DC, up to 15 kbps. No per-level TX power, no source
level, no light-sleep/listen-with-wake-up figure. **Nothing new**; records unchanged.

### 4.3 Teledyne Benthos ATM-900 (manual already registered as `DS-TB-ATM900`)

User's Manual P/N M-270-26 Rev. D:
- p. 2-2: average transmit power @ 21 V DC: 20 W (level 8), 14 W (7), 10 W (6), 7 W (5), 5 W (4),
  3.5 W (3), 2.5 W (2), ">2 W" (1, transducer dependent); peak TX current 3 A, 50 ms @ 21 V DC; receive
  active 720 mW max / 650 mW typ @ 24 V DC; low-power state 12.0 mW max / 10.2 mW typ @ 24 V DC.
- pp. 2-2 to 2-3, typical source levels: LF omni (9–14 kHz) 185 dB re 1 µPa @ 1 m; MF omni (16–21 kHz) 183 dB;
  band C omni (22–27 kHz) 178 dB; LF and MF directional 190 dB.
- p. 8-53, `TxPower`: settings 1–8 = 0 dB to −21 dB attenuation in −3 dB steps, 8 = maximum (default).
- Usability: this is the first manufacturer mapping between **electrical TX power and acoustic level**
  among the registered modems. Electrical power per level is exact (A). The per-level source level
  (SL_max − 3·(8 − level) dB) is an inference (B): the manual defines the setting as transmit power
  attenuation and does not tabulate SL per level. The electrical values fall by roughly half per two
  levels (6 dB), which is consistent with that inference. Records: `benthos_atm900.tx_level{2,4,6,8}`
  (add attenuation and SL), new `benthos_atm900.source_level_max` (transducer-specific).

### 4.4 WHOI Micro-Modem 2, Sonardyne BlueComm 200

No new primary data beyond the registered `DS-WHOI-MM2-TABLE`, `GALLIMORE2010` and `DS-SD-BLUECOMM200`.
BlueComm standby remains unpublished (`sonardyne_bluecomm200.standby` stays D).

### 4.5 Hydromea LUMA 250LP

`DS-HM-LUMA250LP` (V1.241007, "preliminary specifications may change without notice"), p. 1:
data rate **250 Kbit/sec**, "Up to 600 Kpbs at Reduced Range"; maximum range **7 m**; 120° cone; supply
12–36 V; TX 2–5 W (typ., four levels); active receiving 0.5 W; sleep < 10 mW. New record
`hydromea_luma250lp.bitrate` = 250 kbit/s (A, nominal at maximum range; 600 kbit/s as `value_max` with the
reduced-range condition). This replaces the DESERT optical PHY bitrate as the airtime basis.

No peer-reviewed measurement of LUMA power was found.

---

## 5. External validation data

Classification: **P** = parameterization only; **S** = subsystem validation; **M** = mission validation;
**I** = insufficient. "Held-out" means parameterize from source A and validate on independent source B.

| Vehicle | Source (location) | Reported data | Environment | Class | Held-out? |
|---|---|---|---|---|---|
| BlueROV2 | none peer-reviewed; manufacturer battery-life claims (3.3) | ~2–3 h normal, ~4–5 h light (pack-dependent) | undefined | I | No |
| BlueROV2 | Gabl 2021, von Benzon 2022 (registered) | restrained/identified hydrodynamics | tank | S (drag only) | No energy |
| Nessie VII | P028 De Carolis et al. 2018, IEEE JOE, doi:10.1109/JOE.2017.2707261, p. 8 and p. 9 Fig. 5 | 2.2 kWh LiPo, 6–8 h at 2 kn, six Seabotix HPDC1502 (max 250 W each); energy per distance ≈ 220 J/m downstream and ≈ 325 J/m upstream | Fort William, "strong tidal currents", current not measured | P / I | No |
| Nessie VII | P020 De Carolis et al. 2014 (OCEANS Taipei) | not assessed: open-access server refused the connection | – | – | – |
| IVER3 | P028 p. 8 and p. 9 Fig. 6 | 560 Wh LiPo, 8–14 h at 2.5 kn; radial pattern ≈ 80 J/m downstream, ≈ 100 J/m upstream | Trapani/Tallinn trials, current not measured | P / I | No |
| IVER3 | manufacturer sheets (OceanServer; L3Harris) | 800 Wh and 8–14 h at 2.5 kn vs 784 Wh and 5–6 h at 2.5 kn | – | I (conflicting with each other and with P028's 560 Wh) | No |
| REMUS 100 | P023, doi:10.1109/AUV53081.2022.9965807, p. 5 Table I (Scripps Pier, July 2022) | 3 laps of an 800 × 100 m box: distance 2051 / 1973 / 1976 m; energy 46.6 / 41.2 / 40.2 Wh; time 18:25 / 25:27 / 25:50; mean rpm 1381 / 967 / 962; 10 m altitude | currents described as "relatively weak", not quantified | M (weak) | Partly: see below |
| REMUS 100 | P023 Sec. IV-B, Fig. 8 (Mission Bay, Aug 2021) | 10 km, 15 legs, 1400 rpm fixed, ~2 m depth; ADCP along-track current; ≈ 250 Wh at fixed rpm (text) | ebb tide, ADCP measured | M (energy and currents only in a figure) | Model and hotel (J = 0.53, Cp = 0.12, d = 0.14 m, Ph = 60 W, p. 3) come from the same paper |
| REMUS 600 | P026 (2019), p. 4 and p. 5 | hotel 33 W (base tail + nav module) vs 56 W legacy; longest mission 9 h 45 min, > 31 nmi at 3.2 kn; > 15 kWh installed | not reported | P (hotel) / I | No (energy used not reported) |
| REMUS 600 | P033 Edwards & Smith 2017, p. 3 | mission logs (Vineyard Sound etc.) plotted: battery power vs speed through water, cluster ≈ 20 W at 1.5 m/s, spikes to 60 W | ADCP logged | S (plotted only; logs not public) | No |
| Tethys | P025 Hobson et al. 2012, p. 2, p. 3 Fig. 2–3, p. 4, p. 5 Fig. 5 | 23-day mission, > 1800 km (1850 km in Fig. 5 caption) at 1 m/s, sensors ≈ 5 W; 13 kWh primary; hotel 5–8 W steady, 7 W average; sea-trial power breakdown at 1.0 / 0.75 / 0.6 m/s (Fig. 3, plotted) | offshore California, currents not reported | S (Fig. 3, needs digitizing); M as a feasibility bound only (energy used not reported) | **Yes (subsystem):** propulsion from P032 (2010) → P025 Fig. 3 |
| ALR6000 | P024 Roper et al. 2021, IEEE JOE 46(4), p. 8 Eq. 12 / Fig. 12, p. 9 | fit from Portland Harbour 2015 trials; DynOPO: 0.7 m/s over ground, 90 m altitude, ≈ 10 W non-propulsion, longest mission ≈ 195 km over > 3 days, ≈ 3700 m depth; ETI CCS: 5 days, sensors ≈ 60 W, mean propeller 40 W (peaks 80 W against the tide), 272 km of sidescan | Southern Ocean / North Sea, currents not quantified | S (ETI mean propeller power, but speed not reported) / I for mission energy | Weak, same paper (Portland → DynOPO/ETI) |
| Autosub LR | P030 Furlong et al. 2012 | design values and early trials, no measured power | – | P / I | No |
| MARES | P017 Cruz 2019 | kT ≈ 5 W/N from experiments, hotel, 600 Wh (already registered) | – | P | No mission logs found |

Held-out assessment:
- **Tethys** is the only clean held-out case: parameterize propulsion from P032 (Bellingham et al. 2010,
  propulsion tests, already in `proxy_vehicles.yaml`) and hotel from P025, then compare with the sea-trial
  power breakdown in P025 Fig. 3 at three speeds. This is subsystem validation and needs figure digitizing
  (grade B at best). The 23-day mission can only check that the predicted energy stays within 13 kWh.
- **REMUS 100**: propulsion from P022 (2000; 15 W at 3 kn, 110 W at 5.6 kn) and hotel from P029 (1997,
  19.4 W) against P023 Table I is formally held-out, but the vehicles are two decades apart (P023 itself
  uses Ph = 60 W). It is a weak mission-level test; currents are not quantified for the Scripps laps.
- **BlueROV2**: no held-out mission test is possible with the evidence found.
- Nessie VII and IVER3 give upstream/downstream energy-per-distance ratios without measured currents.
  They are useful only as qualitative checks.

---

## 6. Not done here (needs the user's decision or access)

| Item | Where | Size | Why |
|---|---|---|---|
| BlueROV2 R4 CAD | `https://cad.bluerobotics.com/BLUEROV2-R4.zip` | 375,730,995 bytes | measure vertical-thruster x (and z) |
| 30Q EIS/OCV dataset | Mendeley doi:10.17632/g7ncmhrcrz.2 (CC BY 4.0) | not shown | extract cycle-0 OCV at 5 SOC points |
| Lam et al. 2023 full text | IEEE Xplore (institutional access) | – | confirm whether any V/I or K_Q data exist |
| Ng 2024 MS thesis; Polito thesis 31918 | URLs in 2.1 | > 10 MB each | possible geometry tables (unverified) |
| P020 De Carolis 2014 | `osl.eps.hw.ac.uk` (connection refused) or IEEE | – | Nessie VII measured power |

## 7. Proposed registry actions (not applied)

1. New record `bluerov2_standard.vertical_thruster_lateral_spacing` (221.0 mm, A, Blue Robotics 2D drawing
   2018); set V1/V2 y = ∓0.1105 m; x stays proxy (C).
2. `bluerobotics_4s_18ah.dc_resistance_cell_derived`: cite the UN38.3 report (p. 2) for cell identity and
   count. Keep C and the lower-bound status.
3. New `hydromea_luma250lp.bitrate` (250 kbit/s; 600 kbit/s at reduced range; 7 m maximum range).
4. Benthos: add attenuation per level and `source_level_max` per transducer; mark per-level SL as B.
5. EvoLogics: add the RS-232/Ethernet/Wake-Up conditions to the RX/LISTEN records.
6. After approval and download, consider replacing the `bluerobotics_4s_18ah.ocv_curve` placeholder with a
   5-point 30Q relaxed-OCV curve (C).
7. Leave `bluerobotics_t200.inflow_model`, `bluerobotics_t200.esc_idle_power`, the electronics D records and
   the BlueROV2 validation status unchanged.
