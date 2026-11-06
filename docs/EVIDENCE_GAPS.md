# Evidence gaps (2026-11-06)

| Component | Missing quantity | Why needed | Current evidence | Required evidence | Search performed | Status |
| --- | --- | --- | --- | --- | --- | --- |
| T200 | thrust/power at non-zero advance speed | inflow-aware propulsion | Lam et al. 2023 (abstract only); Blue Robotics data bollard only | towing-tank current/power vs J | web + IEEE abstract | unconfigured (static mode only) |
| T200 / Basic ESC | standby power at zero command | hotel load | none | bench measurement | manufacturer pages | unconfigured |
| BlueROV2 18 Ah pack | OCV–SOC(T) | L1 voltage | none (cell datasheet gives loaded curves) | relaxed OCV test of pack | manufacturer + 8 battery papers | placeholder (D) |
| BlueROV2 18 Ah pack | DC resistance | sag, losses | cell DCIR 19.94±2 mΩ → 13.3 mΩ cell-only proxy (C) | pack pulse test | Samsung 30Q datasheet | proxy, lower bound |
| Batteries | pressure effect | deep missions | P041 (+9.2 % at 60 MPa, NCM811) vs P047 (−7 % at 100 MPa, LFP): opposite signs | chemistry-matched data | 8 local papers | not modelled |
| Thermal node | C_th, k, derating onset | battery temperature | none | enclosure thermal test | — | placeholders (D) |
| BlueROV2 Standard | vertical thruster positions | 6T allocation | Blue Robotics 2017 Gazebo dev model (0, ±0.11 m) | CAD or measurement | Wu 2018, von Benzon 2022, Einarsson 2020, ArduSub | proxy (C) |
| BlueROV2 hydrodynamics | real drag vs HoloOcean literals | validation | Gabl 2021 measured surge loads; von Benzon 2022 identified damping (3.6× Gabl); Wu 2018 assumed | consistent multi-axis tests | 5 papers | documented mismatch |
| Fathom-X tether interface, 5 V BEC | power, efficiency | hotel / converter losses | none | measurement | manufacturer pages | unconfigured |
| Oculus M750d | model-specific power | sonar load | family range 10–35 W | per-model datasheet | product pages | range only (B) |
| EdgeTech 2205 | any power figure | sidescan load | "configuration dependent" | configuration-specific sheet | brochure | unconfigured |
| Subnero WNC | sleep (non-deep) power, per-level TX | comms | upper bounds only | per-level datasheet | product page + FAQ | bounds only |
| Acoustic modems | electrical TX power vs source level (dB re 1 µPa) | mapping DESERT power events | EvoLogics per range setting only | per-level calibration | 6 manufacturers | not mapped |
| EM 868 MHz / 14 dBm | electrical TX at 14 dBm | EM PHY | SX1276 +13/+17 dBm bracket (chip only, C) | module measurement | Semtech DS rev 7 | interval proxy |
| Jetson Orin NX | idle power; segmentation workload | compute | YOLOv8s measurements (Rey 2025) | segmentation measurement | 6 papers | representative (B) |
| BlueROV2 onboard computer | measured BlueOS consumption | compute | RPi 4 official workload table | measurement | Blue Robotics pages | representative (B) |
| HoveringAUV / TorpedoAUV / SurfaceVessel proxies | thruster electrical models | proxy profiles | MARES kT≈5 W/N, Tethys η=0.49, REMUS 100 lap energies, ALR6000 fit | per-vehicle propulsor data | 18 local papers | extracted, not yet profiled |
