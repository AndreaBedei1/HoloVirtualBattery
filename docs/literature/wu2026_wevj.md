# Wu, Wang, Xing 2026, WEVJ 17(5):236 (doi 10.3390/wevj17050236)

Verdict: methods reference only. No OCV-SOC data, no R0/R1/C1 values. It is a data-driven (TCN-Transformer, Hippo-optimised) SOC estimator; no equivalent-circuit model is built.

## Cells and datasets (Sec. 3.1, Table 3, pp. 10-11)
- Public data: CALCE (Univ. Maryland, Pecht 2017, ref [39]; data statement points to calce.umd.edu/battery-data#INR, no DOI). Table 3: NMC/graphite cylindrical, cutoffs 4.2/2.5 V; capacity cell is garbled in the text extraction, reads as 2 Ah (consistent with the CALCE INR 18650 data set, which is not the 30Q).
  - Profiles: DST, US06, FUDS (BJDST and 1C discharge used for training), at 0, 25, 45 C, discharged from 80% and 50% SOC to cutoff. Fig. 6 shows US06 current/voltage at 25 C.
- Own experiment: text states Samsung INR18650-30Q, 25 C only, Arbin tester + climate chamber. Tests: capacity calibration (1C CC-CV charge, 1C CC discharge), US06, FUDS. Table 3 lists 3.35 Ah, 4.2/2.75 V (3.35 Ah is odd for a 30Q nominal 3.0 Ah; unresolved, flag to author). Fig. 7 is the test-rig schematic. Own data are not published (data statement only cites CALCE).

## OCV-SOC
None. Text matches for OCV are only generic mentions in the Introduction (ref [9,10]) and the abbreviation list. No OCV test, no SOC-OCV table or figure, no HPPC or pulse test.

## Internal resistance / ECM parameters
None. No R0, R1, C1, no SOC/temperature dependence tables. Only qualitative statement that resistance rises at low temperature (Sec. 3.3.1).

## Results given (not useful for pack model)
Table 4 (CALCE, RMSE by temperature/profile), Table 5 (CALCE comparison), Table 6 (30Q own data, US06/FUDS), comparison table. SOC estimation errors only.

## Use
Cite at most as (a) evidence a 30Q was cycled under US06/FUDS at 25 C and (b) SOC-estimation methods background. Do not use for pack OCV or resistance.
