# Leonardi et al. 2026 (J. Energy Storage 154:121144) - automated EIS fitting, aged Samsung INR18650-30Q cells

Citation: S. G. Leonardi, G. Musò, G. Lucà Trombetta, D. Aloisio, G. Brunaccini, F. Sergi (CNR-ITAE, Messina), "Automated electrochemical impedance spectroscopy fitting for quantitative analysis of degradation modes in lithium-ion batteries", Journal of Energy Storage 154 (2026) 121144. DOI 10.1016/j.est.2026.121144 (p.1). Received 18 June 2025, accepted 15 February 2026, online 23 February 2026. Open access, CC BY. Dataset DOI 10.17632/g7ncmhrcrz.1 (Mendeley Data, cited under "Data availability", p.16; not downloaded). 18 PDF pages.

## 1. Measured vs derived
- Measured (Sec. 3.1.1, p.7; Table 1, p.8): Dataset 1, 500 EIS spectra from eight INR18650-30Q cells (nominal "2.95 Ah" per the paper) aged to 80 % of initial capacity under four profiles. AP1: 23 degC, CC 4 A to 4.2 V then CV with 150 mA cut-off, discharge 15 A to 2.5 V, 10 min rest after charge and 30 min after discharge. AP2: as AP1 with 5 A charge. AP3: as AP1 at 45 degC. AP4: as AP1 without the CV phase. Check-ups for fresh cells and every 25 cycles at 23 degC: capacity and EIS at SOC 100-75-50-25-0 %, 10 kHz to 100 mHz, 10 points per decade. Equipment: Arbin LBT 21044, Gamry 5000E potentiostat, Arbin MZTC climate chamber.
- Derived: equivalent-circuit fits (Circuits A and B, Fig. 1), RMSE of order 1e-4 (Table 5), degradation modes LLI/LAM/CL (Fig. 15). Dataset 2 (Sec. 3.1.2, pp.7-8) comprises other chemistries/formats (LFP 80 Ah, Kokam 200 Ah pouch, Samsung 35E, BAK pouch, coin cell).

## 2. 30Q data availability
- No OCV-SOC table and no printed ohmic or charge-transfer resistance values in the main text. Impedance is shown only as Nyquist plots (e.g. Fig. 11 and the figures of Sec. 4.2); more in the supplement (Figs S3-S8), not available locally. Capacity fade is in Fig. S2 (supplement).
- Therefore NO CSV was produced from this paper. The Mendeley dataset (spectra and fitted parameters) may hold per-SOC resistances at 23 degC; it was not downloaded or inspected (a download needs the user's permission).

## 3. Pack question
Not addressed. No Blue Robotics, ROV or pack-level data. The paper establishes only that INR18650-30Q is a Samsung SDI 18650 cell used here as a laboratory cell.

## 4. What this source can and cannot support in HoloEnergy
- V0: no. V1: indirect only. It shows that 30Q impedance vs SOC, temperature (23 and 45 degC ageing) and age exists in a public dataset that could be queried later for a cell-level resistance with stated 23 degC conditions. Until then it supplies no numeric parameter.
- V2: no (no terminal voltage vs load comparison). V3, V4: no.
- Not comparable to BlueROV2: laboratory cells, no pack or vehicle. Useful to justify an ageing and temperature caveat on cell resistance and OCV, and to name the 30Q as a well-characterised cell for sensitivity studies.
