# Review of the grade D and upper-bound parameters (2026-11-18)

This review covers the 15 parameters with effective grade D and the 8 upper-bound-only parameters in
`data/evidence/final_parameter_audit.*`, the audit of the final configurations.

Categories:
1. Legitimate scenario choice or structural fact. Can remain D without harming the model.
2. Unsupported but non-critical. Remains unknown; excluded from claims.
3. Scientifically important. Affects central results. It must gain a source, become an explicit
   uncertainty or gap, be excluded from the result, or have its claim removed.

The new literature (docs/literature/) contains no value for any of these parameters. In particular:
- Wu et al. 2026 gives no 30Q OCV or resistance data.
- Lam et al. 2023 gives no ESC idle power.

## Grade D parameters

| # | Parameter | Used as | Category | Effect on central results | Disposition |
| --- | --- | --- | --- | --- | --- |
| 1 | `bluerobotics_4s_18ah.ocv_curve` | bus open-circuit voltage | **3** for C16 (low SOC) and C15 (bus-voltage effect); 2 for full-charge missions | The final missions start at full charge and use under 1 % of the charge. Only the top of the curve matters, and it is anchored by the 4.2 V/cell charge voltage. The low-SOC run (C16) depends on the whole curve and on its inconsistent SOC-0 point (review C-02). | Kept D. C16 is stated as model behaviour without a quantitative claim. The fix needs a measured 30Q OCV dataset (Mendeley doi 10.17632/g7ncmhrcrz.2), pending the author's download decision. |
| 2 | `bluerobotics_fathom_x.power` | tether interface ACTIVE | 2 | Unknown, excluded from the bus | Explicit gap (`scientific_warnings`: unknown) |
| 3 | `bluerobotics_t200.esc_idle_power` | ESC standby | **3** for the still-water statement C12 | Eight ESCs at zero command draw an unknown standby power. "In still water only hotel loads consume energy" omits it. | Explicit gap. C12 wording: zero propulsion is a simulator property, and ESC standby is not included. |
| 4 | `bluerov2.bec_5v_efficiency` | payload converter efficiency (value 1.0 used) | **3** | Every 5 V hotel and payload load is charged without conversion loss, so hotel and payload energies are lower bounds | Explicit uncertainty: an unconfigured converter efficiency now opens the upper side of the interval of every load it serves (decision API, §5 of EVIDENCE_ARCHITECTURE) |
| 5 | `bluerov2_heavy.translational_damping_wu2018` | EXP9 external comparison only | 2 | None (proxy, not used in the final missions) | Kept as proxy comparison |
| 6 | `config:battery.capacity_temperature_curve` = [[25, 1]] | no temperature dependence | 2 | Isothermal missions near 20 °C; thermal results are not claimed | Accepted limitation |
| 7 | `config:battery.max_current_temperature_curve` = [[25, 1]] | same | 2 | same | Accepted limitation |
| 8 | `config:battery.resistance_temperature_curve` = [[25, 1]] | same | 2 | same | Accepted limitation |
| 9 | `config:converters.hotel_efficiency` = 1.0 | hotel conversion | **3** (with #4) | same as #4 | Explicit uncertainty (as #4) |
| 10 | `config:converters.payload_efficiency` = 1.0 | payload conversion | **3** (with #4) | same as #4 | Explicit uncertainty (as #4) |
| 11 | `config:converters.propulsion_efficiency` = 1.0 | propulsion conversion | **1** (structural) | The T200 tables give electrical power at the ESC input, which is the battery side, so no converter sits between pack and table | Kept; documented as structural, not a parameter |
| 12 | `config:hotel_load.constant_W` = 0 | unenumerated hotel load | 2 | Assumes every hotel load is listed as a component | Accepted limitation, stated with the payload results |
| 13 | `config:thermal.cooling_coeff_W_per_C` = 2.0 | thermal model | 2 (excluded) | Thermal behaviour is not part of any claim. Review C-06 showed the results are sensitive to it. | Thermal model marked illustrative; no quantitative thermal conclusion |
| 14 | `config:thermal.derating_temperature_C` = 40 | thermal derating onset | 2 (excluded) | same | same |
| 15 | `config:thermal.thermal_capacity_J_per_C` = 1200 | thermal model | 2 (excluded) | same | same |

**Before:** 15 grade D parameters, none classified.

**After:**
- **Category 1 (structural):** 1 parameter, #11.
- **Category 2 (non-critical):** 9 parameters (#2, #5, #6–8, #12–15). They stay excluded and are flagged.
- **Category 3 (important):** 5 parameters (#1, #3, #4, #9, #10). None could be sourced.
  - #1 and #3 are handled by narrowing claims C12 and C16.
  - #4, #9 and #10 are handled as an explicit open upper bound in the interval and in the decision
    rule.

## Upper-bound parameters

| Parameter | Source wording | Better typical value? | Operating-state value? | Range? | Only maximum? | Treatment |
| --- | --- | --- | --- | --- | --- | --- |
| `bluerobotics_4k_camera.power_max` (5 W) | "Max Power 5 W" | not published | no | no | **yes** | Upper-bound-derived estimate; open lower side |
| `bluerobotics_lowlight_usb_camera.power_max` (1.1 W) | "Max Power Draw 220 mA" (× 5 V) | not published | no | no | **yes** | Same |
| `bluerobotics_lumen.power_full` (15 W) | over 1500 lm at 15 W | no | yes, for full output | no (dimmed states unpublished) | for dimmed states | Point value at full output. Any dimmed use is upper-bound-derived. |
| `evologics_s2cm_18_34.rx` (0.8 W) | "less than 0.8 W" (RS-232) | no | no | no | **yes** | Upper-bound-derived; RX = LISTEN without a wake-up module (D-12) |
| `evologics_s2cm_18_34.tx_max` (55 W) | "max. available" setting | n/a: a setting, not a load estimate | yes, at that setting | no | yes, as a setting | Sensitivity only (EXP10 part 2) |
| `hydromea_luma250lp.sleep` (0.01 W) | below 10 mW | no | no | no | **yes** | Upper-bound-derived; negligible energy |
| `hydromea_luma250lp.tx` (2–5 W) | range | no | no | **yes** | no | Profile uses the maximum (5 W). The interval [2, 5] W is closed and reported. |
| `tritech_gemini_720is.power_range` (16–27 W) | 16–27 W, "range dependent" | no | no | **yes** | no | Profile uses the maximum (27 W). The interval [16, 27] W is closed. The 19–74 V supply needs a step-up converter (unconfigured, open upper side). |

Reports separate the three kinds of value:
- **Point estimate:** the nominal value used.
- **Upper-bound-derived estimate:** energy from a published maximum. It is reported as
  `upper_bound_energy_Wh`. Its interval has an open lower side, never an assumed lower value.
- **Open interval:** a side with no published bound, listed in `open_low` / `open_high`, plus every
  unconfigured load and converter (`scientific_warnings`).

The maximum is never used silently as typical. Every upper-bound use is labelled in the record
(`bound: upper_bound`), in the component profile (`use: value_max`) and in the run's evidence summary.
