# Experimental data (future BlueROV2 calibration and validation)

This directory is the home of **real** measurements. It intentionally contains no
data yet: no physical run has been performed by this project. Synthetic data are
allowed only as test fixtures under `tests/` and must be declared
`dataset_kind: synthetic_test_fixture`.

```text
experiments/
  calibration/   runs used for parameter identification and model selection
  validation/    frozen held-out runs used once, for final accuracy
  schema/        run metadata schema and time-series column contract
```

Each run lives in its own directory:

```text
experiments/<calibration|validation>/<run_id>/
  metadata.json      run metadata (schema/run_metadata.schema.json)
  timeseries.csv     synchronized samples (schema/timeseries.md)
  raw/               untouched instrument/autopilot logs (BlueOS, DataFlash, meters)
  notes.md           operator notes, anomalies, deviations from the protocol
```

Check a run before archiving it:

```powershell
python tools/check_experiment_run.py experiments/calibration/<run_id>
```

Register runs in a dataset manifest (`holoenergy.analysis.datasets`, schema
version 1) with roles `parameter_identification`, `model_selection` or
`final_validation`, a raw-file SHA256 and an `independence_group` per physical
cycle/mission. A physical cycle never crosses roles. Held-out runs are not
inspected while choosing model structure, parameters or alignment.

Every run must contain or reference: timestamp, battery voltage, battery current,
battery temperature, water temperature, thruster commands (with units), vehicle
state, sensor states and mission phase. Missing channels are recorded as missing,
never filled with model values.

Safety: never power the thrusters out of water and never activate the BlueROV2
unless it is in water, secured and supervised by authorized personnel following
Blue Robotics' instructions. HoloEnergy never commands hardware. The campaign order
and metrics are defined in [the validation protocol](../docs/validation_protocol_bluerov2.md).
