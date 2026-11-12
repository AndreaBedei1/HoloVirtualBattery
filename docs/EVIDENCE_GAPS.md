# Evidence gaps (updated 2026-11-12)

| Component | Missing quantity | Why needed | Current evidence | Required evidence | Search performed | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T200 | thrust/power at non-zero advance speed | inflow-aware propulsion | Lam et al. 2023 (abstract only); Blue Robotics data bollard only | towing-tank current/power vs J | web + IEEE abstract | unconfigured (static mode only) |
| T200 / Basic ESC | standby power at zero command | hotel load | none | bench measurement | manufacturer pages | unconfigured |
| BlueROV2 18 Ah pack | OCV–SOC(T) | L1 voltage | none (cell datasheet gives loaded curves) | relaxed OCV test of pack | manufacturer + 8 battery papers | placeholder (D) |
| BlueROV2 18 Ah pack | DC resistance | sag, losses | cell DCIR 19.94±2 mΩ → 13.3 mΩ cell-only proxy (C) | pack pulse test | Samsung 30Q datasheet | proxy, lower bound |
| Batteries | pressure effect | deep missions | P041 (+9.2 % at 60 MPa, NCM811) vs P047 (−7 % at 100 MPa, LFP): opposite signs | chemistry-matched data | 8 local papers | not modelled |
| Thermal node | C_th, k, derating onset | battery temperature | none | enclosure thermal test | — | placeholders (D) |
| BlueROV2 Standard | vertical thruster positions | 6T allocation | Blue Robotics 2017 Gazebo dev model (0, ±0.11 m) | CAD or measurement | Wu 2018, von Benzon 2022, Einarsson 2020, ArduSub | proxy (C) |
| BlueROV2 hydrodynamics | real drag vs HoloOcean literals | validation | Gabl et al. 2021 (Ocean Eng. 234:109279, Table 1): restrained standard BlueROV2, head-on, mean ΣFx; von Benzon 2022: damping identified on a free-running Heavy; Wu 2018: adopted (Sandøy 2016), not measured | consistent force measurements on the Heavy configuration, measured speed at the model, multiple axes | 5 papers + audit ([comparison](bluerov2_hydrodynamic_external_comparison.md)) | HoloOcean 3.8-4.5x Gabl at 0.4-1.0 m/s, 0.86-1.16x von Benzon: references disagree 3-4x; registered (grade B/C/D) |
| Fathom-X tether interface, 5 V BEC | power, efficiency | hotel / converter losses | none | measurement | manufacturer pages | unconfigured |
| Oculus M750d | model-specific power | sonar load | family range 10–35 W | per-model datasheet | product pages | range only (B) |
| EdgeTech 2205 | any power figure | sidescan load | "configuration dependent" | configuration-specific sheet | brochure | unconfigured |
| Subnero WNC | sleep (non-deep) power, per-level TX | comms | upper bounds only | per-level datasheet | product page + FAQ | bounds only |
| Acoustic modems | electrical TX power vs source level (dB re 1 µPa) | mapping DESERT power events | EvoLogics per range setting only | per-level calibration | 6 manufacturers | not mapped |
| EM 868 MHz / 14 dBm | electrical TX at 14 dBm | EM PHY | SX1276 +13/+17 dBm bracket (chip only, C) | module measurement | Semtech DS rev 7 | interval proxy |
| Jetson Orin NX | idle power; segmentation workload | compute | YOLOv8s measurements (Rey 2025) | segmentation measurement | 6 papers | representative (B) |
| BlueROV2 onboard computer | measured BlueOS consumption | compute | RPi 4 official workload table | measurement | Blue Robotics pages | representative (B) |
| HoveringAUV / TorpedoAUV / SurfaceVessel proxies | thruster electrical models | proxy profiles | MARES kT≈5 W/N (P017 Eq. 13), Tethys 12 W @ 7 N (P032), REMUS 2000 design 15/110 W @ 3/5.6 kn (P022), ALR6000 fit P=70.145U^2.4333 (P024); REMUS 100 lap energies (P023) cross-check only | per-vehicle propulsor force–power data, bus voltages, battery limits | 18 local papers | proxy profiles (C) built for hovering-mares-like and torpedo-remus/tethys/autosub-like (`parameters/proxy_vehicles.yaml`); AMOUR and both surface profiles dropped (no force-indexed power) |
| Hydromea LUMA 250LP | bitrate | optical airtime | none registered (DESERT optical PHY bitrate used) | datasheet bitrate | datasheet | airtime from the DESERT setting |
| BlueROV2 pack | power-limit behaviour under derating | power-limit experiments | 60 A continuous (manufacturer, A) | pack pulse/limit test | manufacturer | limit modelled at 60 A; pack response unvalidated |
| Native torpedo/hovering agents | fin/command adapter for closed-loop runs of proxy profiles | native proxy runs | HoloOcean TorpedoAUV takes 4 fin angles + thrust | adapter (software) | — | proxy profiles exercised offline only |
