# Song and Lee 2023 (Electronics 12(12):2587) - variable-threshold passive balancing, with Samsung INR 18650-30Q ECM tables

Citation: H. Song, S. Lee, "Study on the Systematic Design of a Passive Balancing Algorithm Applying Variable Voltage Deviation", Electronics 2023, 12, 2587. DOI 10.3390/electronics12122587 (printed p.1). Chosun University. MDPI open access, CC BY. 19 PDF pages; page refs are PDF pages (= journal "n of 19").

## 1. Scope
BMS passive-balancing design for 4-series reduced modules of INR 18650-30Q, INR 18650-29E and INR 21700-50E cells. It is not an underwater, robot or mission-energy paper.

## 2. Measured vs simulated
- Tabulated cell data (Appendix A, Tables A1-A3, pp.16-17): OCV, Ri, Rdiff, Cdiff vs SOC at 25 degC and 0.5 C-rate (Appendix A text). The text says an experiment measured cell-to-cell deviation (0.3 % capacity, 0.3 % OCV, 5 % resistance; Conclusions p.16) but does NOT describe how the OCV/ECM tables were obtained (pulse test, HPPC, datasheet). Treat as "reported, extraction method not stated".
- Single-cell model check (Fig. 6, p.7): MATLAB/Simulink ECM against experimental voltage; maximum error 0.18 V at low SOC, RMSE 0.0121 V over the operating range (Sec. 2.2, p.6). Experiment details for this comparison (current profile, instrument) are only in the figure.
- Experiment (Sec. 4, p.14, Figs 16-17): 4S reduced module, "30 V/10 A class" cycler, DC1651A monitoring/balancing board with an "LTC 6083" IC (as printed), Arduino. CC-CV charge; cell voltage deviation and balancing on/off only. No energy or Wh measurement of the battery under load.
- Simulated: balancing losses for 4S 30Q (Sec. 3.1, pp.7-8): 0.24 Wh (discharge), 0.53 Wh (rest), 0.22 Wh (charge) to reach the 10 mV target; the proposed method is about 2 % (12 mWh) better than a fixed threshold (Sec. 3.3, p.14).

## 3. Conditions
25 degC, 0.5 C, single 30Q cell tables; Cn = 3.0 Ah, CC 1.5 A, CV 4.2 V, cutoff 150 mA (Table A4, p.18). Balancing resistor 33 ohm in the text (Sec. 2.1, p.5) versus 30 ohm in Table A4 (inconsistent in the paper).

## 4. Samsung INR18650-30Q data (extracted verbatim)
Table A1 (pp.16-17), values as printed, also in `data/song2023_30q_ocv.csv` (soc, ocv_V) and `data/song2023_30q_ecm.csv` (adds Ri, Rdiff, Cdiff). SOC 100/90/80/70/60/50/40/30/20/10/0 %:
- OCV (V): 4.1682, 4.0765, 4.0157, 3.9168, 3.8204, 3.7336, 3.6322, 3.5200, 3.3513, 3.2019, 2.8277.
- Ri (ohm): 0.0219, 0.0219, 0.0213, 0.0212, 0.0206, 0.0213, 0.0214, 0.0208, 0.0215, 0.0219, 0.0233.
- Rdiff (ohm): 0.0331, 0.0331, 0.0247, 0.0430, 0.0305, 0.0291, 0.0337, 0.0339, 0.0392, 0.0613, 0.0613.
- Cdiff (F): 1058, 1058, 2476, 1507, 898, 2451, 2007, 1680, 2525, 610, 610.
- Fig. 2 (p.5): OCV-SOC curves (graph); Fig. 5 (p.6): ECM parameters (graph). Only the table is used. Table verified against the rendered pages 16-17.
- Cross-check with Lv et al. (`lv2020_aukf.md`): 100 % OCV 4.1682 V here vs 4.1617 V there; 50 % is 3.7336 V here vs 3.7317 V at SOC 0.5034 there.

## 5. Does it establish that a Blue Robotics 14.8 V 18 Ah pack uses 30Q cells?
No. The paper never mentions Blue Robotics, BlueROV2, or any underwater pack. The 4S 30Q module in it is a 4-cell bench module (4 series, 1 parallel). The data are a cell-level proxy only; applying them to the BlueROV2 pack needs an independent statement of the pack's cell type and parallel count.

## 6. What this source can and cannot support in HoloEnergy
- V0: nothing. V1: yes for traceability of a cell-level OCV(SOC) and series-resistance proxy table (cell = 30Q, 25 degC, 0.5 C) if the pack cell type is separately established; the extraction method is not stated, so grade as weak-to-moderate reported data.
- V2: weak. The only measured comparison is single-cell terminal voltage vs a model built from the same table (RMSE 0.0121 V), with a current profile shown only graphically. It cannot validate pack voltage under thruster load.
- V3, V4: no measured vehicle power or energy.
- Not comparable to a BlueROV2 4S 18 Ah pack (single 3 Ah cell data, 0.5 C, 25 degC only; no temperature or C-rate dependence). Ri of about 0.021 ohm per cell is a single-condition value; do not scale it to pack resistance without knowing the parallel count and interconnect resistance.
