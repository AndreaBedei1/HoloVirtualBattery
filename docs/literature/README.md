# Literature extraction notes

Deep-reading notes for the sources added on 2026-11-16 and 2026-11-19, written by reading agents from the local PDFs
(not redistributed) and checked against the rendered pages where a value enters the evidence registry
(Lam et al. Figs. 16-17). Each note gives page, section, figure and table locations, separates
measured from derived quantities and ends with what the source can and cannot support.

| Note | Source | Use in HoloEnergy |
| --- | --- | --- |
| `lam2023_t200.md` | Lam et al. 2023, OCEANS Limerick, doi 10.1109/OCEANSLimerick52467.2023.10244513 | Record `bluerobotics_t200.advance_ratio_series_34p5rps`; inflow bias of the static T200 tables (sensitivity); insufficient for P(T, V, Va) |
| `danielis2021.md` | Danielis et al. 2021, WMU J. Maritime Affairs, doi 10.1007/s13437-021-00253-z | Comparator (power-state-machine energy model); same-mission model comparison |
| `lotusim_energy.md` | Grosset et al., arXiv:2609.17124 | Comparator (effort-linked battery plugin, no equations in the paper) |
| `tun2026.md` | Tun et al. 2026, IJRR, doi 10.1177/02783649261453998 | Not an electrical validation: energy reconstructed from static T200 curves; BlueROV2 Heavy parameter comparison only |
| `wu2026_wevj.md` | Wu et al. 2026, WEVJ 17(5):236, doi 10.3390/wevj17050236 | Not usable for the 30Q pack: no OCV or resistance data |
| `mission_energy_datasets.md` | focused search for measured mission-energy datasets | No suitable public dataset identified |
| `decarolis2014_lowcost.md` | De Carolis, Lane, Brown 2014, OCEANS Taipei, doi 10.1109/OCEANS-TAIPEI.2014.6964490 (DOI from PDF metadata) | Related work: bus-current coulomb counting and waypoint-linear energy model; results are simulated only; no V2-V4 support |
| `decarolis2018_joe.md` | De Carolis, Brown, Lane 2018, IEEE JOE 43(3), doi 10.1109/JOE.2017.2707261 | Related work: runtime energy estimation on IVER3/Nessie VII; field results plotted, no tabulated numbers; no V1-V4 support |
| `song2023_balancing.md` | Song and Lee 2023, Electronics 12(12):2587, doi 10.3390/electronics12122587 | Cell-level 30Q proxy: OCV, Ri, Rdiff, Cdiff vs SOC (Table A1, 25 degC, 0.5 C); `data/song2023_30q_ocv.csv`, `data/song2023_30q_ecm.csv`; no pack-to-30Q link |
| `lv2020_aukf.md` | Lv et al. 2020, Electronics 9(9):1425, doi 10.3390/electronics9091425 | Second independent 30Q OCV-SOC table (Table 2, 25 degC); `data/lv2020_30q_ocv.csv`; 10-parallel block resistances only |
| `leonardi2026_eis.md` | Leonardi et al. 2026, J. Energy Storage 154:121144, doi 10.1016/j.est.2026.121144 | 30Q EIS dataset (23 and 45 degC ageing); no tabulated OCV or resistance in the paper; data at doi 10.17632/g7ncmhrcrz.1 not downloaded |
| `sharma2025_pisces.md` | Sharma et al. 2025, Commun. Eng. 4:93, doi 10.1038/s44172-025-00422-5 | Not a propulsion/battery source; measured sensing and compute subsystem power (Table 2) as a weak payload-power reference |
| `simulator_sources.md` | HoloOcean ICRA 2022 / JOE 2024 (doi 10.1109/JOE.2024.3410290) / 2.0 preview (arXiv 2510.06160) / ICAR 2025 survey (doi 10.1109/ICAR65334.2025.11338622) | Positioning only: BlueROV2-based vehicles, no energy or battery model, no energy coverage in the survey |
