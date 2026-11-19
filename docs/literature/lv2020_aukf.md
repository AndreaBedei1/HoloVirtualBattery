# Lv et al. 2020 (Electronics 9(9):1425) - adaptive UKF SOC estimation, Samsung 30Q cell tables

Citation: J. Lv, B. Jiang, X. Wang, Y. Liu, Y. Fu, "Estimation of the State of Charge of Lithium Batteries Based on Adaptive Unscented Kalman Filter Algorithm", Electronics 2020, 9, 1425. DOI 10.3390/electronics9091425 (printed p.1). Shandong University, Weihai. Published 2 Sept 2020. 22 PDF pages.

## 1. Measured vs simulated
- Measured (Sec. 2.2, pp.4-8): a battery "composed of 10 parallel lithium cobalt oxide cells", cell model "SAMSUNG 30Q INR18650" (Table 1, p.4: rated capacity 3000 mA h, rated voltage 3.6 V, discharge cut-off 2.5 V, weight 48.1 +- 1.5 g, 18.2 mm x 65.0 mm). Protocol: 1 C pulsed discharge for 3 min, 2 h rest, repeated to cut-off (p.4, Fig. 2). Parameter identification at 25 degC (p.7). The "1 C" current in amperes for the 10-parallel test object, the tester and the sampling rate are not stated.
- OCV(SOC) "obtained by the static method" (Table 2, p.5), fitted by an 8th-order polynomial (Eq. 3).
- Second-order RC model: Table 3 (p.8), averaged over SOC 20-100 %: Rsi 0.0037 ohm, Rtf 0.0019 ohm, Rts 0.0035 ohm, Ctf 23,340 F, Cts 501,270 F (as printed; verified on the rendered page). These are for the 10-parallel test object, not a single cell. Model error (Table 4): MAE 0.51 %, RMSE 0.8 % on pulse terminal voltage.
- Simulated: SOC-estimation experiments are MATLAB simulations under pulsed and UDDS discharge (Sec. 4, up to p.19). Table 5 terminal-voltage error: UKF 1.33 % / 1.95 %, AUKF 0.54 % / 0.9 % (MAE / RMSE); Table 6 SOC error: UKF 2.9 % / 3.3 %, AUKF 0.63 % / 0.7 % (p.19). Not a hardware validation.
- Caveat: the paper calls the chemistry "lithium cobalt oxide", which the INR designation does not indicate; do not reuse that chemistry statement.

## 2. Samsung 30Q OCV-SOC table (extracted verbatim)
Table 2, p.5 (20 points, SOC as fraction): see `data/lv2020_30q_ocv.csv`. Range 4.1617 V at SOC 1 to 3.0747 V at SOC 0.0563. The table is printed as two side-by-side column pairs; row order verified against the rendered page. Figure 3 (p.5) additionally shows points not in the table; those were not digitised.
Resistance: only Table 3 above (10-parallel block, SOC-averaged, 25 degC). Our arithmetic, assuming identical cells: 0.0037 ohm x 10 = 0.037 ohm per cell, which differs from the 0.0206-0.0233 ohm single-cell Ri in Song and Lee; unresolved, so no per-cell value is adopted from this paper.

## 3. Pack question
The paper does not mention Blue Robotics, BlueROV2 or a 14.8 V pack. A 10-parallel 30Q block is not a 4S pack; the OCV table is a cell-level proxy only.

## 4. What this source can and cannot support in HoloEnergy
- V0: no. V1: OCV(SOC) points for a 30Q-type cell at 25 degC from a pulse/rest protocol (measured, instrument not named); resistances only for a 10-parallel block with ambiguous per-cell scaling. Usable as a second, independent cell-level OCV source to compare against Song and Lee (differences of about 0.002 V at SOC 0.5 and 0.0065 V at full charge).
- V2: weak (model vs pulse-test terminal voltage, MAE 0.51 %), only for a 10-parallel block at 25 degC.
- V3, V4: none. Underwater/ROV context absent; UDDS is an automotive cycle and is simulated.
- Not comparable to BlueROV2 4S 18 Ah as a pack.
