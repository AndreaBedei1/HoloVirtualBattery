# Simulator positioning sources (HoloOcean ICRA 2022, HoloOcean JOE 2024, HoloOcean 2.0 preview, ICAR 2025 survey)

Read on 2026-11-19 for positioning only; keyword-searched for energy, battery, power and thruster content, with the vehicle sections read. Page refs are PDF pages.

| Local file | Work | Citation / DOI |
| --- | --- | --- |
| Potokar22icra.pdf | HoloOcean: An Underwater Robotics Simulator (7 pp.) | E. Potokar, S. Ashford, M. Kaess, J. G. Mangelson. Venue and DOI are not printed in the PDF text; the filename suggests ICRA 2022 (not verified from the PDF). |
| HoloOcean_A_Full-Featured_Marine_Robotics_Simulator_for_Perception_and_Autonomy.pdf | HoloOcean JOE 2024 (15 pp.) | E. Potokar et al., IEEE J. Oceanic Eng., vol. 49, no. 4, Oct. 2024, p.1322 onwards. DOI 10.1109/JOE.2024.3410290 (printed p.1 and PDF metadata). |
| 2510.06160v1.pdf | A Preview of HoloOcean 2.0 (6 pp.) | B. Romrell, A. Austin, B. Meyers, R. Anderson, C. Noh, J. G. Mangelson, arXiv:2510.06160v1. No DOI printed. |
| Navigating_the_Sim-to-Real_Gap_A_Critical_Analysis_of_Underwater_Robotics_Simulators.pdf | ICAR 2025 survey (6 pp.) | L. e Silva Gomes, P. L. J. Drews-Jr, 2025 IEEE Int. Conf. on Advanced Robotics (ICAR). DOI 10.1109/ICAR65334.2025.11338622 (printed p.1). |

## What each says that matters for HoloEnergy
- HoloOcean JOE 2024 (hovering AUV section, text near the vehicle descriptions): the hovering AUV is "based on our in-house custom hovering AUV built on the BlueROV2 platform"; control applies forces of specified magnitude at the locations of the eight thrusters; a PD controller is provided; dynamics can be customised in Python. No battery, thruster-electrical or energy model is described; "energy" appears only in sonar/acoustic context.
- HoloOcean ICRA 2022: same vehicle description (custom hovering AUV based on the BlueROV2, eight thrusters); no energy or battery content.
- HoloOcean 2.0 preview (Sec. II, vehicles): adds Fossen-model dynamics, a ROS2 bridge and a BlueROV2 Heavy vehicle; features under development are sensors, rendering and environment; no energy or battery content.
- ICAR 2025 survey: taxonomy of simulators and sim-to-real gaps (sensors, physics, middleware, performance). Keyword search finds no coverage of energy or battery modelling (the word "power" appears only for computing). It mentions detailed thruster models for some simulators (refs [19], [31]); this supports the claim that energy models are an unaddressed gap, stated as our reading, not the survey's claim.

## Supports in HoloEnergy
V0-V4: none of these provides electrical or energy data. They support related-work positioning only: HoloOcean provides the BlueROV2-style vehicle and thrust-force interface to which an evidence-aware energy layer attaches, and the community survey does not cover energy fidelity.
