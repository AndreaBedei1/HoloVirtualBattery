# LOTUSim-Energy: energy/battery model findings

Status: the battery model equations, SOC update, propulsion power formula and energy feedback were NOT located in the readable repository content. Findings below are limited to what was verified.

## Sources read
- Repo page: https://github.com/IRL-Crossing-CNRS/LOTUSim-Energy (README, license, top-level listing)
- Git tree API (partial, first 100k of ~1.67 MB JSON): https://api.github.com/repos/IRL-Crossing-CNRS/LOTUSim-Energy/git/trees/HEAD?recursive=1
- Commits API: https://api.github.com/repos/IRL-Crossing-CNRS/LOTUSim-Energy/commits?per_page=1
- Directory listings: .../contents/Assets, .../contents/Assets/Scripts, .../contents/Assets/Scripts/lotusim_interface, .../contents/Assets/Scripts/lotusim_interface/ROS2_interface, .../contents/PythonScripts, .../contents/Submodules
- Consumer script: https://github.com/IRL-Crossing-CNRS/LOTUSim-Energy/blob/main/Assets/Scripts/EditorEnvironment/AgentBatteryHUD.cs
- Raw file: https://raw.githubusercontent.com/IRL-Crossing-CNRS/LOTUSim-Energy/main/Untitled-1.txt
- Gazebo reference: https://gazebosim.org/api/sim/8/classgz_1_1sim_1_1systems_1_1LinearBatteryPlugin.html
- Repo of the simulator this fork is based on (listing only, not read for battery): https://github.com/naval-group/lxdyn

## Findings (verified)
- License: EPL-2.0 (LICENSE file and About section, per README page).
- Last commit: 2026-11-16T05:07:18Z, message "docs: the README opens on the documentation site".
- README: no battery or energy model description; no SOC or battery parameters. Appendix gives hydrodynamic parameters only. Cites an IROS 2026 paper by Buche et al.
- Battery HUD (AgentBatteryHUD.cs): a display consumer, not a model. It subscribes to a per-agent topic (default pattern `{0}/{1}/battery/state`; header comment mentions `linear_battery/state`, which does not match the default). Percentage = charge / capacity x 100 when capacity > 0.001, else the message's percentage field. Colour thresholds 40% and 20%. Voltage and current copied from the message.
- Agent configuration: Untitled-1.txt references `"sdf_file": "model-battery.sdf"` for BlueROV, WAMV and X500 agents, and `"world_file": "energy.world"`. Wind turbine block has `"cp": 0.35`, `"ct": 0.8` (wake entry) and `"alpha_e_aud_per_kwh": 0.5` (LCOE). Ct/Cp are turbine coefficients, not vehicle thrust.
- Gazebo LinearBatteryPlugin (reference model, if model-battery.sdf uses it; NOT verified): parameters voltage, open_circuit_voltage_constant_coef, open_circuit_voltage_linear_coef, initial_charge (Ah), capacity (Ah), resistance (Ohm), power_load (W, required), enable_recharge, charging_time, power_draining_topic / stop_power_draining_topic. Equations are not given on the doc page.
- Thruster/propulsion: only propeller animation assets found (Assets/Animations/propeller*.anim/.controller). LotusimBaseInterface.cs populates propeller data, per earlier listing; not read in full.

## Not found / not verified
- model-battery.sdf: not located in the repo listing read so far; not found via web search.
- Battery equations, SOC update, Rint/ECM choice: not located.
- Propulsion power formula, thrust model, coefficients: not located.
- Sensor, compute, communication loads and power states: no files found by name.
- Energy feedback to thrust at low SOC: not found.
- Repo tree: only the first ~7% of the recursive tree JSON was read (100k of 1.67 MB). Remaining paths, including any .sdf or energy plugin source, are unchecked. Next step: page the tree with offset 100000 onward, or clone the repo locally.
- GitHub code search requires sign-in, so it was not usable.
