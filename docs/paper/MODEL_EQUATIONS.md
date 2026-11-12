# Model equations (paper reference)

Every equation the paper needs, as implemented. Units are SI unless stated; energies in
the reports are converted to Wh by dividing joules by 3600. "Source" names the model
origin; "Adaptation" states what HoloEnergy changes; "Code" is the implementing function.
Source identifiers refer to `holoenergy/evidence/data/sources.yaml` and
[scientific_sources.md](../scientific_sources.md).

## 1. Time discretisation and energy integration

All quantities are evaluated once per simulator tick of fixed length Δt (0.01 s for the
native HoloOcean runs). Powers are held constant over a tick (rectangle rule), so

$$E_c = \sum_k P_{c,k}\,\Delta t, \qquad E^{\mathrm{Wh}}_c = E_c / 3600,$$

for every category c (propulsion, sensors, compute, communications, auxiliaries, converter
losses, battery losses), device and device state. The bus (terminal) energy is
$E_{\mathrm{bus}} = \sum_{c \neq \mathrm{battery\ losses}} E_c$ and the battery-side (OCV) work
is $E_{\mathrm{OCV}} = E_{\mathrm{bus}} + E_{\mathrm{loss}}$.

| Variables | Units | Source | Adaptation | Code |
| --- | --- | --- | --- | --- |
| P (W), Δt (s), E (J, Wh) | W, s, J | standard discrete integration | power constant within the simulator tick (the dynamics backend applies the same force over the tick) | `holoenergy/accounting.py` `EnergyRuntime.record` |

## 2. Actuator geometry and allocation

For n actuators with positions $r_i$ (m, body frame) and unit thrust directions $d_i$:

$$\tau = B f,\qquad B = \begin{bmatrix} d_1 & \cdots & d_n \\ r_1\times d_1 & \cdots & r_n\times d_n\end{bmatrix}\in\mathbb{R}^{6\times n},$$

with $\tau = [F_x,F_y,F_z,M_x,M_y,M_z]^\top$ (N, N·m) and actuator forces $f$ (N). The
controller requests $\tau^\ast$; allocation solves

$$f = \arg\min_{f_{\min}(V)\le f\le f_{\max}(V)} \lVert W (B f - \tau^\ast)\rVert_2 ,$$

by weighted pseudo-inverse with saturation and redistribution ("redistributed" method); the
bounds are each actuator's maximum forward/reverse force at the present pack voltage (and the
simulator clamp for direct mapping). The allocation residual is
$\varepsilon_a = \lVert B f - \tau^\ast\rVert$; rank(B) gives the controllable DOFs.

| Variables | Units | Source | Adaptation | Code |
| --- | --- | --- | --- | --- |
| B, f, τ, r, d | N, N·m, m | control allocation survey, Johansen and Fossen (2013), doi:10.1016/j.automatica.2013.01.035 | voltage-dependent bounds from the thruster tables; residual and saturation reported per tick | `holoenergy/allocation.py` `ThrustAllocator.allocate`; `holoenergy/actuation.py` `ActuationLayer.allocate` |

**Wrench-equivalent actuation.** For a virtual layout $B_v$ evaluated on a native body
$B_n$ with clamp $c$: $\tau_v = B_v f_v$, $f_n = \arg\min_{|f_n|\le c}\lVert B_n f_n - \tau_v\rVert$,
native residual $\varepsilon_n = \lVert B_n f_n - \tau_v\rVert$. Electrical power is computed
from $f_v$; dynamics from $f_n$. Ticks with $\varepsilon_n > 10^{-6}$ are flagged as
dynamics/energy inconsistent. Code: `ActuationLayer.backend_action`.

## 3. Thruster electrical power

$$P_i = g\!\left(|f_i|,\ V,\ \mathrm{sign}(f_i)\right),$$

where g interpolates the manufacturer table of electrical input power against thrust at
measured voltages: linearly in force within each voltage table, then linearly in voltage.
The T200 tables (Blue Robotics, September 2019 workbook, S6) are static (bollard) data, so g
does not depend on advance speed; applied with inflow they are a representative, not exact,
model (grade B). Forces beyond the table maximum are refused, not extrapolated.

| Variables | Units | Source | Adaptation | Code |
| --- | --- | --- | --- | --- |
| f (N), V (V), P (W) | N, V, W | S6 (manufacturer bollard data, 10-20 V) | cumulative-max envelope of the published points (`tools/import_t200.py`); evaluated at the terminal voltage of the same tick | `holoenergy/models/propulsion.py` `ThrusterModel.power`, `PropulsionModel.powers` |

## 4. Bus, converters and power limiting

$$P_{\mathrm{bus}} = \frac{\sum_i P_i}{\eta_p} + \frac{P_{\mathrm{payload}}}{\eta_{pl}} + \frac{P_{\mathrm{hotel}}}{\eta_h},\qquad P_{\mathrm{conv}} = P_{\mathrm{bus}} - \Big(\sum_i P_i + P_{\mathrm{payload}} + P_{\mathrm{hotel}}\Big),$$

where $P_{\mathrm{payload}}$ is the sum of sensor and compute component powers and of the
event-driven loads attached with `env.attach` (e.g. modem energy per tick divided by Δt).

The BlueROV2 profiles use $\eta = 1$ (T200 data already include ESC losses; 5 V supply
losses are an unconfigured gap). The power manager scales all actuator demands by one
factor $s\in[0,1]$, the largest s with $P_{\mathrm{bus}}(s f, V_{\min}) \le I_{\max} V_{\min}$
(bisection), where $V_{\min} = U - I_{\max} R$; the operating current then solves

$$P_{\mathrm{bus}}\big(s f,\ U - I R\big) = I\,(U - I R)$$

on the high-voltage branch (bisection). Loads that cannot be served are reduced by a
service factor (accounting approximation, not a brownout model).

| Variables | Units | Source | Adaptation | Code |
| --- | --- | --- | --- | --- |
| η (-), s (-), I (A), U, V (V), R (Ω) | -, A, V, Ω | converter efficiency definition, TI SLVA390A (S9) | uniform derating factor across actuators | `holoenergy/models/converters.py`, `holoenergy/models/power_manager.py` `PowerManager.plan` |

## 5. Battery L1 (Rint equivalent circuit)

$$V = U(\mathrm{SOC},T) - I R(\mathrm{SOC},T),\qquad I = \frac{2P}{U + \sqrt{U^2 - 4RP}},$$

$$P_{\mathrm{loss}} = I^2 R,\qquad P_{\mathrm{OCV}} = U I = P + P_{\mathrm{loss}},\qquad \mathrm{SOC}_{k+1} = \mathrm{SOC}_k - \frac{I\,\Delta t}{3600\,C_{\mathrm{Ah}}}.$$

Current limit:
$I_{\max} = \min\!\big(I_{\mathrm{rated}}\,f_I(T)\,f_{\mathrm{th}},\ Q_{\mathrm{avail}}/\Delta t,\ I_{\mathrm{th}},\ U/(2R),\ (U - V_{\mathrm{cut}})/R\big)$;
cutoff when the available charge is exhausted or $U - IR \le V_{\mathrm{cut}}$.

| Variables | Units | Source | Adaptation | Code |
| --- | --- | --- | --- | --- |
| U (V), R (Ω), I (A), C (Ah), SOC (-) | V, Ω, A, Ah | Rint ECM, S2 (Alhanouti et al. 2016); OCV characterisation S3 | stable root of the quadratic; for the BlueROV2 pack U(SOC) is a placeholder (D) and R a cell-derived proxy (C) | `holoenergy/models/battery.py` `RintBattery.step`, `current_for_power`, `current_limit` |

## 6. Battery L0 (energy bucket)

$$V = V_{\mathrm{nom}},\quad P = \min(P_{\mathrm{req}}, V_{\mathrm{nom}} I_{\max}),\quad \mathrm{SOC}_{k+1} = \mathrm{SOC}_k - \frac{P\,\Delta t}{3600\,E_{\mathrm{Wh}}},\quad P_{\mathrm{loss}} = 0.$$

Code: `holoenergy/models/battery.py` `EnergyBucketBattery.step`. Because thruster power depends
on voltage (Section 3), L0 changes propulsion energy as well as removing losses.

## 7. Lumped thermal node

$$C_{\mathrm{th}}\frac{dT}{dt} = Q - k\,(T - T_w),\qquad Q = I^2R - I\,T\,\frac{\partial U}{\partial T},$$

integrated exactly for Q held constant over a tick:
$T_{k+1} = T_w + Q/k + (T_k - T_w - Q/k)\,e^{-k\Delta t/C_{\mathrm{th}}}$. The entropic term
is zero for the BlueROV2 pack (no data); $C_{\mathrm{th}}$, k and the derating onset are
placeholders (D), so temperatures are illustrative. Thermal derating factor:
$f_{\mathrm{th}} = (T_c - T)/(T_c - T_d)$ for $T_d < T < T_c$.

| Variables | Units | Source | Code |
| --- | --- | --- | --- |
| C_th (J/K), k (W/K), T, T_w (°C), Q (W) | J/K, W/K, °C, W | heat balance S1 (Bernardi et al. 1985), S2 Eq. 7b | `holoenergy/models/thermal.py` `ThermalModel.step`, `derating_factor` |

## 8. Communication-state energy (observe-only)

For each modem interface j, from the PHY events of the network simulator on [0, t]:
$\mathcal{T}_j$ = union of transmission intervals, $\mathcal{R}_j$ = union of synchronized
receptions minus $\mathcal{T}_j$ (half duplex), $t^{L}_j = t - |\mathcal{T}_j \cup \mathcal{R}_j|$;

$$E_j = P^{TX}_j |\mathcal{T}_j| + P^{RX}_j |\mathcal{R}_j| + P^{L}_j\, t^{L}_j .$$

Per-tick charging uses cumulative differences $E_j(t_{k+1}) - E_j(t_k)$, so events that
arrive late are charged exactly in total. Source levels (dB re 1 µPa) and optical/EM transmit
powers are network parameters, never electrical power. Code:
`holoenergy/integrations/communications.py` `InterfaceLedger`, `CommunicationEnergyAdapter.consume`;
`holoenergy/integrations/desert.py` `DesertEnergyAdapter.observe`.

## 9. Evidence-weighted reporting

Each device state (and actuator, battery-loss and converter energy) carries a grade
$g = \mathrm{cap}(g_{\mathrm{record}}, \mathrm{relation})$ with exact→A, representative→B,
proxy→C, user/unsupported→D. Reported shares are

$$\mathrm{share}_g = \frac{\sum_{(d,s):\,\mathrm{grade}=g} E_{d,s}}{\sum_{d,s} E_{d,s}},$$

together with the upper-bound share (energy from published maxima) and the proxy share. These
are provenance descriptors, not confidence levels; vehicle hydrodynamics are excluded. Code:
`holoenergy/evidence/__init__.py` `cap_grade`, `coverage`; `holoenergy/evidence/runtime.py`
`EvidenceMap.summarize`.

## 10. Interval propagation

For device states whose record publishes a range, with used value $p_0$ and range
$[p_{lo}, p_{hi}]$:

$$E_{lo} = E + \sum E_{d,s}\Big(\frac{p_{lo}}{p_0} - 1\Big),\qquad E_{hi} = E + \sum E_{d,s}\Big(\frac{p_{hi}}{p_0} - 1\Big),$$

where a side without a published bound is reported as open (never filled with an assumed
distribution). This is a first-order interval: changes of battery current, losses and
derating caused by the varied load are not propagated. Code: `holoenergy/uncertainty.py`
`energy_intervals`.

## 11. Hydrodynamic quantities used in verification and comparison

HoloOcean 2.3.0 (patched) applies $F_D = -\tfrac12\rho C_D A\,|v_r|\,v_r$ with $v_r = v - v_c$
(relative to the current), at the centre of mass, isotropic, plus Unreal linear damping
$v \leftarrow v\,(1 - c\,\Delta t)$ on the world-frame velocity (PhysX explicit damping factor; a 1-DOF point mass with this update reproduces the native traces to $5\times10^{-8}$ m, review B-03). The chain-closure check infers
the net force from the measured centre-of-mass velocity change,
$F = m\big(v_{k+1}/(1 - c\Delta t) - v_k\big)/\Delta t$, and compares it with thrust plus drag.
External comparison: restrained load (Gabl et al. 2021) vs $\tfrac12\rho C_D A U^2$; identified
damping $X_u u + X_{uu} u|u|$ (von Benzon et al. 2022) vs $\tfrac12\rho C_D A u^2 + m c u$.
Code: `tools/audit_holoocean_drag.py`, `tools/verify_energy_chain.py`,
`experiments/run_native_campaign.py` `close_chain`, `experiments/run_offline_campaign.py`
`external_drag`.

## 12. Baselines (comparison models, not part of HoloEnergy)

$P = a + b\,|u|^3$ with u the speed over ground or the speed through the water
$|v - v_c|$; and $P = \bar P$ (constant). Both fitted by least squares on the calm-water
transit only and evaluated on other runs. Code: `experiments/analyze_native_campaign.py`
`fit_baselines`, `baseline_energy`.
