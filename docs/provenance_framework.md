# Provenance-aware framework: technical reference (v0.2)

Configuration surface and semantics added in v0.2. The v0.1 core (battery L0/L1,
components, logging, HoloOcean contract) is described in
[generic_framework.md](generic_framework.md) and [holoenergy_design.md](holoenergy_design.md).

## Evidence registry

`holoenergy/evidence/data/`: `literature.yaml` (generated index of the workbook papers and
local PDFs, hashes only), `sources.yaml` (datasheets, code, user), `parameters/*.yaml`
(records; a parameter file may declare its own `sources:`). Load with
`holoenergy.evidence.default_registry()`.

A record has `id, component, quantity, unit, value | value_min/value_max | dataset,
bound, relation, grade, sources, location, conditions, derivation, uncertainty, notes`.

* `bound`: `exact`, `measured_mean`, `nominal`, `range`, `upper_bound`, `derived`
  (requires `derivation`), `unknown` (with `status: unconfigured`).
* `relation` of the value to the configured hardware caps the grade:
  exact -> A, representative -> B, proxy -> C, user/unsupported -> D (`cap_grade`).
  A C value is never upgraded.
* Unknown stays unknown: `value: null`, `status: unconfigured`, grade D; a component
  whose state links to such a record is excluded from the bus and listed as an
  incomplete load.
* `dataset.path` points to packaged JSON (tables, coefficients) inside `holoenergy/`.

Profiles link component states as `{evidence: <record id>, use: value|value_min|value_max}`
and vehicle-level quantities in an `evidence:` block (`propulsion`, `battery_losses`,
`converters`, `hotel_constant`, each `{record, relation}`, plus `vehicle_relation`;
`double_counting: warn|error`).

## Per-run evidence audit

`env.energy.summary()["evidence"]` and `EnergyReport.evidence` report the energy (Wh and %)
per grade, the share computed from upper bounds, the proxy-derived share, unconfigured and
legacy components, double-counting warnings and stale links. Vehicle hydrodynamics are
simulator-owned and excluded. The grade distribution is provenance, not a confidence
interval.

*Stale links*: if a configured value no longer matches the record its profile links to
(e.g. a user override of `battery.internal_resistance_ohm`, replaced actuator tables), the
link is dropped, the energy is graded D and a warning names it.

*Double counting*: [double_counting_policy.md](double_counting_policy.md).

## Units

`holoenergy.units`: `to_si`, `convert`, `unit_kind`, `Quantity`, `dbm_to_watt`,
`celsius_to_kelvin`. Levels (dB re 1 µPa, dBm) are not convertible to electrical power;
"C" is rejected as ambiguous (coulomb vs Celsius).

## Actuator geometry and allocation

Actuators may carry `position_m` (body NWU), `direction` (or `direction_deg: {azimuth,
elevation}`), `role`, `backend_index`. `holoenergy.allocation.ThrustAllocator` builds the
6×n configuration matrix B = [d; r × d] and allocates a body wrench with
`method: redistributed` (bounded, iterative redistribution), `pseudoinverse` or
`power_irls` (power-weighted IRLS), optional actuator and DOF weights. Results carry the
achieved wrench, residual, saturated actuators and rank.

```yaml
actuation:
  action_mode: wrench          # or thrusters (one effort per actuator)
  allocation: {method: redistributed}
  backend:
    mapping: direct            # or wrench_equivalent
    native_clamp_N: 28.75
    agent_type: BlueROV2
    native_geometry: [...]     # wrench_equivalent only: the backend agent's actuators
```

Bounds come from each actuator's maximum force at the present pack voltage (and the
native clamp for direct mapping). With `wrench_equivalent`, the virtual layout's achieved
wrench B_v f_v is re-allocated on the native layout within its clamp; the per-tick
`backend_residual_norm` flags ticks where the native body cannot reproduce it. Energy of
such ticks is that of the virtual actuators and is not comparable with a layout that met
the request.

Actuator electrical models: T200 manufacturer tables (force/command/power per voltage),
user force-power tables (`force_power_tables`, `reverse: null` for forward-only evidence),
or a registered custom model (`register_actuator_model`).

## Communication energy

`holoenergy.integrations.communications`: `ModemPowerProfile` (power per state TX, RX,
LISTEN, SLEEP, linked to evidence; `includes` declares the functions inside the device
figure), `CommunicationEnergyAdapter` (generic; `consume(t_end)` returns the energy accrued
since the previous call; late activity is charged exactly).
`holoenergy.integrations.desert.DesertEnergyAdapter` reads `holo_desert` PHY events
(`phy_[control_]{tx,rx}_{start,end}`, `duration_s`, `outcome`, `medium`), applies
half-duplex accounting (TX > RX > idle), and counts generated/delivered/forwarded
messages. It never sends anything to the network: use `adapter.observed(session)` or
`adapter.observe(events)`; `ensure_interfaces(...)` creates silent interfaces so their
idle power accrues from t = 0. Attach to the bus with `env.attach(adapter)` (category
`communications`). Source levels and optical/EM transmit powers are network parameters,
not electrical power.

Native DESERT setup and isolation: [native_runs.md](native_runs.md).

## Uncertainty

`holoenergy.uncertainty.energy_intervals` (also `EnergyReport.intervals`) propagates the
published ranges of the parameters actually used to mission energy: a side without a
published bound stays open (listed in `open_low` / `open_high`), never filled with an
assumed distribution. Upper-bound-derived energy is reported separately.

## Reports, CLI, dashboard

`env.energy.report()` -> `EnergyReport` (`to_dict`, `write_json`, `load`, `text`),
`holoenergy.report.compare_runs`. CLI: `holoenergy profiles | evidence <id|component|
profile> | validate <config|profile> | run <mission.yaml> | compare <a.json> <b.json> |
audit-sensors <SensorType...> | check-backend [--binary]`. Dashboard:
[dashboard.md](dashboard.md).

## Experiments and reproducibility

[native_runs.md](native_runs.md) (native HoloOcean and DESERT, instance isolation,
reproducibility record), `experiments/run_offline_campaign.py` (archived-trace sensitivity
studies), `experiments/run_native_campaign.py`, `run_comm_matrix.py`, `run_crosslayer.py`,
`analyze_native_campaign.py`, `benchmark_overhead.py`, `make_paper_figures.py`.
