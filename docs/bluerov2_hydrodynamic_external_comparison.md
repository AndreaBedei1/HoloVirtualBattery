# BlueROV2 drag: external comparison audit (E4)

Audit date: 2026-11-12. Scope: `external_drag()` in `experiments/run_offline_campaign.py`
(constants `HOLOOCEAN_DRAG`, `GABL_2021`) and `experiments/results/offline/E4_external_drag.csv`.
No simulator was run and no coefficient is changed or proposed.

## 1. Purpose and scope

The drag-units fix and `tools/audit_holoocean_drag.py` (source HO-DRAG-AUDIT) verify that the patched
HoloOcean 2.3.0 backend applies the drag equation written in its own source. That is verification of an
implementation. It says nothing about whether the equation and its literals represent a physical
BlueROV2. This note checks what the published external data can and cannot say about the second
question, which numbers in E4 are like-for-like, and how the E4 claim ("HoloOcean drag is 3.8-7.2x the
measured surge load") should be worded.

## 2. Sources and evidence type

| Source | Vehicle | Evidence type | Location used |
| --- | --- | --- | --- |
| Gabl et al. 2021, Ocean Eng. 234:109279, doi:10.1016/j.oceaneng.2021.109279 (accepted manuscript, PolyU IRA hdl:10397/92240; page numbers below refer to it) | BlueROV2, standard 6-thruster frame | Direct measurement: in-line load cells on eight restraining tethers | Table 1 (p. 9); Sections 2.1-2.3, 3.2-3.4, 4; Figs. 5, 8-10 |
| Gabl et al. 2020, Data 5(3):57, doi:10.3390/data5030057 (registry P003) | same campaign | Data descriptor: set-up, test matrix, zero correction | Sections 1, 2.1-2.4, 3.2; Tables 1, 6, 8; Fig. 8 |
| Gabl et al. 2020, Edinburgh DataShare, doi:10.7488/ds/2835 | same campaign | Raw and processed time series | not downloaded in this audit |
| von Benzon et al. 2022, J. Mar. Sci. Eng. 10:1898, doi:10.3390/jmse10121898 (registry P004) | BlueROV2 Heavy, 8 T200 | Identified from free-running motion data with a thrust model | Section 4.2; Tables 4, 5, A1; Fig. 6 |
| Wu 2018, MEng thesis, Flinders University (flex.flinders.edu.au, ThesisWu2018.pdf) | BlueROV2 Heavy (target vehicle) | Not measured: values adopted from Sandøy (2016), a thesis on the original BlueROV | Section 5.2, Table 5.3 (thesis p. 48) |
| HoloOcean 2.3.0 source (HO-SRC-2.3.0), patched tree `C:/HOB/src/after` | BlueROV2 agent (Heavy layout, 8 thrusters) | Simulator literals | `HolodeckBuoyantAgent.cpp` l. 86-97; `HolodeckBuoyantAgent.h` l. 26; `BlueROV2.cpp` l. 15-24, 72-74 |

Einarsson and Lipenitis (2020), listed in `docs/EVIDENCE_GAPS.md`, was not consulted for this note.

## 3. HoloOcean drag as implemented

- Force: F = -1/2 rho Cd A |v_rel|^2 v_rel/|v_rel|, with v_rel = v_body,world - v_current,
  rho = 997 kg/m3, Cd = 0.8, A = 0.45 m2, so Cd A = 0.36 m2 and k = 1/2 rho Cd A = 179.46 N s2/m2.
  The force is applied at the centre of mass in world axes and scaled by the submerged fraction
  (1 when fully submerged). The literals and the equation lines are identical in the pristine tree
  (`C:/HOB/src/before`); the unit scaling at l. 94 is present only in the patched tree.
- Isotropy: the force depends only on the relative-velocity vector. The same Cd A acts in surge, sway,
  heave and any oblique direction, with no lift and no drag moment.
- Current: drag is relative to the current (l. 87-90; the Y component is sign-flipped for UE axes in
  `GetOceanCurrentVelocity`).
- Linear damping: `ABlueROV2::EnableDamping()` calls `SetLinearDamping(1.0)` and
  `SetAngularDamping(0.75)`; it is invoked by the thruster and PD control schemes
  (`BlueROV2ControlThrusters.cpp` l. 23, `BlueROV2ControlPD.cpp` l. 28). This is UE rigid-body damping:
  a scalar applied to the body's own world-frame velocity, with no access to the current. The audit tool
  models it as v <- max(0, 1 - c dt)(v + F dt/m) (`predicted_velocity`). The equivalent steady
  resistance is m c v = 11.5 v N (times 1/(1 - c dt) = 1.01 at dt = 0.01 s).

Consequence: for a vehicle held fixed in a current U (v_world = 0) HoloOcean applies only 179.46 U^2.
For the same vehicle moving at U through still water it applies about 179.46 U^2 + 11.5 U. The two
cases are physically equivalent apart from turbulence, but HoloOcean treats them differently.

## 4. Test conditions of the external measurement

| Item | Gabl et al. (2020, 2021) | HoloOcean counterpart |
| --- | --- | --- |
| Facility | FloWave, 25 m diameter circular basin, 2 m water depth, current from 28 impeller units (2021 Sect. 2.1; 2020 Sect. 2.2) | unbounded uniform current |
| Vehicle | BlueROV2 standard: 6 T200 (4 vectored horizontal, 2 vertical), 0.457 x 0.338 x 0.254 m, about 0.2 kg net positive buoyancy; Raspberry Pi 3 replaced by a Jetson Nano, Ping360 sonar added (2020 Sect. 2.1). Mass not reported | BlueROV2 agent with 8-thruster Heavy layout, 11.5 kg |
| Orientation | Main flow at 180 deg travels in -x; ROV forward is +x (2021 Sect. 3.2), so the current meets the bow along the surge axis. 0 deg (stern) and +/-90 deg (beam) were tested up to 0.6 m/s; 1 m/s only at 180 deg (2021 Sect. 3.3) | isotropic, orientation irrelevant |
| Restraint | Eight Dyneema tethers to a scaffold frame (48.3 mm pipes, 3.47 x 2.52 m, about 2.5 m high, surface piercing), each with an in-line submersible load cell and a turnbuckle; target preload about 20 N per tether; tether directions from underwater motion capture, 128 Hz (2020 Sect. 2.2-2.3, 3.2; 2021 Sect. 2.2) | free body |
| Load cells | Applied Measurements DDEN; six rated 100 N, LC7-8 rated 500 N and noisier at low load; accuracy below +/-0.15 % of rated capacity, 0.05 % typical (2021 Sect. 2.2) | n/a |
| Force reported | Sum Fx: sum of the x-components of the eight tether tensions, after a still-water zero correction that equalises the preloads (constant buoyancy neglected), sign = force needed to hold the ROV (2020 Sect. 3.2; 2021 Sect. 3.2, 4) | in-line drag on the body |
| Rig contribution | No flowing-water tare; drag on ropes, load cells and turnbuckles is not separated. The authors report no significant interference from the set-up but do not quantify it (2021 abstract, Sect. 4) | none |
| Tether/umbilical | Umbilical fixed to the support frame so that its remaining length does not load the ROV (2021 Sect. 4); the ROV-to-frame segment is not quantified | none |
| Thrusters | Passive in all current-only cases (2020 Sect. 2.4); whether propellers could windmill is not stated | not commanded |
| Statistic | Mean over the full capture time (512 s for Curr03-08, 2020 Table 6); Fig. 8 error bars are standard deviations, which Table 1 does not list | steady value |
| Speed definition | Set by impeller RPM; the value is from an earlier tank calibration (Noble et al. 2015), described as "a mean velocity at the centre of the tank in mid water depth" (2020 Sect. 2.4). It was not measured at the model during these runs; turbulence is at the tank's realistic level (2021 Sect. 4) | exact uniform vector |
| Depth | ROV at mid-depth, about 1 m below the free surface (2020 Sect. 2.2); free-surface and blockage effects not discussed | none |
| Water | Density and temperature not reported; rho = 997 kg/m3 is used below (rho = 1000 changes Cd A by 0.3 %) | 997 kg/m3 |
| Repeats | Two 1 m/s runs at 180 deg without obstacle (Curr07, Curr08, 2020 Table 6), both with long motion-capture gaps; only samples with load-cell and motion data were analysed (2021 Sect. 4). Table 1 does not label run IDs, so the assignment is by elimination. At 0.4 m/s two runs exist (Curr04, Curr10) but Table 1 lists one value; which run it is was not verified | n/a |

## 5. Comparable quantities

Gabl et al. (2021, Table 1, column d = infinity, 180 deg) reproduce the six `GABL_2021` values exactly.
The like-for-like HoloOcean quantity is the in-line drag on a vehicle held fixed in a uniform current,
that is the quadratic term alone. The "+ linear" column is what HoloOcean applies to the same vehicle
moving at U through still water; it is given as an upper bracket, not as the restrained counterpart.

| U (m/s, nominal) | Measured sum Fx (N) | Implied Cd A (m2) | HoloOcean quadratic (N) | Quadratic + 11.5 U (N) | Ratio, quadratic | Ratio, + linear |
| --- | --- | --- | --- | --- | --- | --- |
| 0.2 | 1.0 | 0.050 | 7.18 | 9.48 | 7.18 | 9.48 |
| 0.4 | 6.4 | 0.080 | 28.71 | 33.31 | 4.49 | 5.21 |
| 0.6 | 16.4 | 0.091 | 64.61 | 71.51 | 3.94 | 4.36 |
| 0.8 | 28.8 | 0.090 | 114.85 | 124.05 | 3.99 | 4.31 |
| 1.0 (run a) | 45.2 | 0.091 | 179.46 | 190.96 | 3.97 | 4.22 |
| 1.0 (run b) | 46.9 | 0.094 | 179.46 | 190.96 | 3.83 | 4.07 |

Implied Cd A = 2 sum Fx/(rho U^2). Uncertainty: Table 1 gives means only. The still-water row of
Table 1 is -0.6 N and the corrected zero measurements lie within +/-1 N (2020 Sect. 3.2, Fig. 8). The
0.2 m/s value is therefore of the same order as the zero residual, and its ratio is not resolved
(subtracting the -0.6 N residual alone would move it from 7.2 to 4.5). From 0.4 to 1.0 m/s the
ratio is 3.8-4.5 (quadratic) or 4.1-5.2 (with linear damping).

The implied Cd A rises from 0.050 to about 0.09 m2 between 0.2 and 0.6 m/s and is nearly constant
above; HoloOcean's law is purely quadratic. On the bounding frontal area of the standard frame
(0.338 x 0.254 = 0.0859 m2) the implied Cd is 1.05-1.10 for 0.6-1.0 m/s. The HoloOcean literal
A = 0.45 m2 is 5.2 times that area and 5.1 times the CAD surge projected area of the Heavy
(A_u = 0.0877 m2, von Benzon et al. 2022, Table 5), while its Cd = 0.8 is lower than the implied Cd.
The factor of about four is thus carried by the area literal.

## 6. Other published coefficients (context only)

| Source, method | X_u (N s/m) | X_u\|u\| (N s2/m2) | Surge force at 0.4 / 0.6 / 0.8 / 1.0 m/s (N) | Ratio to Gabl | HoloOcean / source |
| --- | --- | --- | --- | --- | --- |
| von Benzon et al. 2022, Heavy, identified (Table A1, "Experimental") | 13.7 | 141.0 | 28.0 / 59.0 / 101.2 / 154.7 | 4.4 / 3.6 / 3.5 / 3.3-3.4 | 1.02 / 1.10 / 1.13 / 1.16 (0.86 at 0.2 m/s) |
| Wu 2018, Table 5.3, adopted from Sandøy (2016) for the original BlueROV | 4.03 | 18.18 | 4.5 / 9.0 / 14.9 / 22.2 | 0.71 / 0.55 / 0.52 / 0.47-0.49 | 6.4 / 7.2 / 7.7 / 8.1 |

von Benzon et al. (2022, Sect. 4.2) estimated damping by matching model output to open-loop runs in a
1.15 m deep, 6.1 m diameter pool, with inputs from 20 % to 100 % in 10 % steps per degree of freedom;
each run was repeated, one copy for estimation and one for validation. Velocity came from SBL
positioning, tether disturbance was reduced but not eliminated, and the surge model error is about
10 % (Fig. 6). The thrust map is a regression from earlier experiments (Pedersen et al. 2019), not
checked here. The maximum surge speed is 0.72 m/s at 85 N (Table 4), so the 0.8 and 1.0 m/s entries
extrapolate the fit. The quadratic term corresponds to Cd A = 0.282 m2 (rho = 1000 kg/m3, Table A1),
or Cd = 3.2 on A_u, well above the 1.05-1.10 implied by the restrained data. Possible reasons for the
3-4x gap between the two experimental sources include variant geometry (Heavy width 0.58 m in
Table 5 versus 0.338 m for the standard frame), thrust-map error at non-zero advance speed or tether
drag absorbed into the identified damping, free-running versus restrained conditions, and the
nominal tank speed. None of these was quantified by the authors or here.

Wu (2018, Sect. 5.2) states that the identification experiments were not performed and that the
damping values were taken from Sandøy (2016). They are not BlueROV2 measurements and should not be
used as validation evidence.

## 7. Quantities that are not comparable

- Gabl +/-90 deg and 0 deg runs: comparable in principle, since HoloOcean drag is isotropic, but the
  values appear only in Fig. 8 and were not extracted. They would allow a check of the isotropy
  assumption from the DataShare files.
- Sum Fz and moments: Gabl et al. report a vertical force growing with speed and attitude changes
  (Figs. 8-9); HoloOcean drag has no lift or moment.
- Wave, irregular-wave and obstacle cases: no HoloOcean counterpart in E4.
- Active-thrust cases (about -92 N forward, 86 N backward, 64 N lateral; 2021 Sect. 3.2, Fig. 5): these
  are thrust of the 6-thruster vehicle against the restraint, not drag.
- von Benzon and Wu coefficients: not forces measured at a stated current; different method and, for Wu,
  a different vehicle.
- E4 row at 0.5 m/s: no measured value.
- Power: E4 maps both forces through the static T200 curve at 15.5 V. The CSV ratios are 4.63, 9.28,
  8.55, 8.69, 4.83 and 4.53, i.e. 4.5-9.3, not the 4.6-9.4 quoted in `docs/RESEARCH_STATUS.md`. At
  1.0 m/s the HoloOcean force cannot be allocated within T200 bounds (residual 53.9 N), so that ratio
  is a saturated lower bound. The 7.18 N and 6.4 N demands both map to 12.4 W, which suggests the
  low-force end of the curve is coarsely resolved; this was not examined further. The HoloOcean agent
  itself saturates near 81 N in surge (4 x 28.75 N/sqrt 2), consistent with the 80.5 N mean surge
  wrench at 0.8 m/s in `E4_backend_consistency.csv`.

## 8. Conclusion on the 3.8-7.2x claim

The numbers are correctly transcribed and the arithmetic reproduces. Omitting the linear damping is
correct for a restrained-in-current comparison, because UE damping acts on world-frame velocity, which
is zero there. The claim should be refined and its interpretation weakened:

1. Report 3.8-4.5x for 0.4-1.0 m/s; the 0.2 m/s value lies within the zero-flow residual.
2. State that the reference is a modified standard BlueROV2 under a nominal tank speed, not the Heavy
   configuration that the HoloOcean agent represents.
3. Do not present the ratio as HoloOcean overestimating "real BlueROV2 drag". Surge damping identified
   on a free-running Heavy (von Benzon et al. 2022) is 3.3-4.4x the restrained load over the same
   speeds, and HoloOcean's quadratic law is within 0.86-1.16x of it over 0.2-1.0 m/s.
4. The power ratio holds only as a consequence of the force ratio and the static T200 curve; quote
   4.5-9.3x with the saturation caveat at 1.0 m/s, or omit it.

Defensible wording:

> For a head-on current of 0.4-1.0 m/s, the drag that HoloOcean 2.3.0 applies to its BlueROV2 agent
> (1/2 rho Cd A U^2 with Cd A = 0.36 m2) is 3.8-4.5 times the mean in-line restraint load measured on
> a tethered standard BlueROV2 by Gabl et al. (2021, Table 1); at 0.2 m/s the measured load (1.0 N) is
> of the order of the zero-flow residual. The same law is within 0.86-1.16 times the surge damping
> identified for a free-running BlueROV2 Heavy by von Benzon et al. (2022), so the two external
> references differ from each other by a factor of 3-4. The verified backend is therefore not a
> validated BlueROV2 hydrodynamic model, and the comparison does not establish the drag of the
> Heavy configuration.

## 9. Limitations

- Only the accepted manuscript of Gabl et al. (2021) was read; page numbers of the published version
  were not checked.
- The DataShare files were not inspected: run-to-value mapping at 0.4 and 1.0 m/s, standard
  deviations and side-flow values are unverified.
- Water density and temperature, propeller windmilling, and the load carried by ropes, load cells and
  the umbilical segment are not reported by the authors.
- The thrust regression behind von Benzon et al. (Pedersen et al. 2019), the original data of
  Sandøy (2016) and Einarsson and Lipenitis (2020) were not consulted.
- The discrete form of UE linear damping is taken from `tools/audit_holoocean_drag.py`; this audit
  verified only that HoloOcean passes a scalar to `SetLinearDamping` and uses the current solely in
  `ApplyBuoyancyDragForce`.
- `docs/EVIDENCE_GAPS.md` gives "3.6x Gabl" for von Benzon; that is the 0.6 m/s value of a
  3.3-4.4x range (0.4-1.0 m/s; 8.4x at 0.2 m/s).
