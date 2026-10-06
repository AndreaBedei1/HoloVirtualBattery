# Scientific sources and model decisions

Research date: 2026-10-06. Raw search records are in `sources/research*.json`.
Search backend: web.run; parallel-cli was unavailable. Publisher HTML sometimes
returned 403/429; accessible publisher PDFs and institutional author copies were
used. No numerical parameters were transferred between different cell chemistries.

## Bibliography

| ID | Reference and access | Used for |
| --- | --- | --- |
| S1 | Bernardi, D., Pawlikowski, E., Newman, J. (1985). A General Energy Balance for Battery Systems. *J. Electrochem. Soc.* 132(1), 5–12. [DOI 10.1149/1.2113792](https://doi.org/10.1149/1.2113792), [author technical-report record](https://escholarship.org/uc/item/9fx5f0h8). The record is a 1984 precursor; the publication is 1985. | Heat-balance framework. The original publisher full text was not accessible; simplified equation corroborated by S2. |
| S2 | Alhanouti, M., Gießler, M., Blank, T., Gauterin, F. (2016). New Electro-Thermal Battery Pack Model of an Electric Vehicle. *Energies* 9, 563. [DOI 10.3390/en9070563](https://doi.org/10.3390/en9070563), [full text, KIT](https://publikationen.bibliothek.kit.edu/1000059427/3890227). | ECM tradeoffs, thermal balance §4 Eq. 7a–b, temperature-dependent resistance and OCV. |
| S3 | Zhang, R. et al. (2018). A Study on the Open Circuit Voltage and State of Charge Characterization of High Capacity Lithium-Ion Battery Under Different Temperature. *Energies* 11, 2408. [DOI 10.3390/en11092408](https://doi.org/10.3390/en11092408), [publisher PDF](https://mdpi-res.com/d_attachment/energies/energies-11-02408/article_deploy/energies-11-02408.pdf). | Temperature-specific OCV characterization and SOC definitions. |
| S4 | Pózna, A. I., Hangos, K. M., Magyar, A. (2019). Temperature Dependent Parameter Estimation of Electrical Vehicle Batteries. *Energies* 12, 3755. [DOI 10.3390/en12193755](https://doi.org/10.3390/en12193755). | Temperature-dependent capacity and electrical parameters; parameter identification §3.4. Simulation verification, not BlueROV2 validation. |
| S5 | [Blue Robotics 18 Ah 4S battery product](https://bluerobotics.com/store/comm-control-power/powersupplies-batteries/battery-li-4s-18ah-r3/), [battery guide](https://bluerobotics.com/learn/battery-info/), [Samsung INR18650-30Q datasheet hosted by Blue Robotics](https://bluerobotics.com/wp-content/uploads/2018/10/INR18650-30Q-Data-Sheet.pdf). | Pack ratings and operational bounds. Cell ratings do not replace pack ratings. |
| S6 | [Blue Robotics T200 product and test data](https://bluerobotics.com/store/thrusters/t100-t200-thrusters/t200-thruster-r2-rp/), [official September 2019 workbook](https://cad.bluerobotics.com/T200-Public-Performance-Data-10-20V-September-2019.xlsx). | Measured electrical input power and thrust vs PWM and voltage. |
| S7 | [Blue Robotics Low-Light HD USB Camera](https://bluerobotics.com/store/sensors-cameras/cameras/cam-usb-low-light-r1/). | 5 V supply, maximum 220 mA, hence upper bound 1.1 W. |
| S8 | [Blue Robotics Ping360](https://bluerobotics.com/store/sonars/imaging-sonars/ping360-sonar-r1-rp/). | Maximum input power 5 W; supply 11–25 V. |
| S9 | Raj, A., Texas Instruments (2010, revised 2020). [Calculating Efficiency, SLVA390A](https://www.ti.com/lit/an/slva390/slva390.pdf), Eq. 13. | Converter efficiency and power-loss definition. |
| S10 | [HoloOcean BlueROV2 2.2](https://byu-holoocean.github.io/holoocean-docs/v2.2.0/agents/agents/blue-rov-agent.html), [agent API 2.2](https://byu-holoocean.github.io/holoocean-docs/v2.2.0/holoocean/agents.html), [environment API 2.3](https://byu-holoocean.github.io/holoocean-docs/v2.3.0/holoocean/environments.html). | Eight thruster forces, control scheme 0; simulated tick timing. These are inspected API versions, not a claim of runtime compatibility with every version. |

## Selection

L0 is an ideal energy bucket for accounting baselines. L1 uses an OCV source and
series effective DC resistance. It captures sag and resistive loss with two dynamic
states (reference SOC and average pack temperature). RC polarization, diffusion,
hysteresis, aging and charging are excluded. S2 compares richer ECMs: their
parameters need pulse/relaxation measurements unavailable for this particular pack.
L1 is a first calibratable approximation, not experimentally validated here.

One lumped thermal node is implemented. S2 Eq. 7b reduces to
`C_th dT/dt = I² R - k (T-T_water)` for this Rint circuit. Optional reversible
heat is `-I T_K dU_oc/dT` (positive discharge current). The entropy coefficient
must be measured; its omission is explicit, not a statement that it is zero in
all Li-ion cells. Enclosure conduction, internal air and water exchange are
combined into an effective `k`; radiation and internal temperature gradients
are omitted. A second enclosure node is deferred until validation shows a need.

Temperature dependence uses measured tables rather than universal correction
coefficients. S3 supports OCV characterization at temperature; S4 motivates
identifying capacity and electrical parameters at multiple temperatures. Table
interpolation is an engineering representation of these measurements, not an
equation or dataset copied from either article. No Arrhenius activation energy
or Peukert exponent is assigned without pack-specific data.
