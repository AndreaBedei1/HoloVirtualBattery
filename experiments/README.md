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

## Provenance-aware campaign scripts (v0.2)

| Script | Needs | Output |
| --- | --- | --- |
| `run_offline_campaign.py` | archived 100 Hz traces only | `results/offline/` (E0-E5) |
| `run_native_campaign.py` | verified patched HoloOcean package | `results/native/N*/` (42 closed-loop runs) |
| `run_comm_matrix.py` | own DESERT engine on a non-default port | `results/native/desert/comm_matrix.json` |
| `run_crosslayer.py` | patched HoloOcean + own DESERT engine | `results/native/crosslayer.json` |
| `analyze_native_campaign.py` | committed native results | `results/native/tables/` (layouts, baselines, ablations) |
| `benchmark_overhead.py` | full native trace in `logs/native_campaign` | `results/native/benchmark_overhead.json` |
| `make_paper_figures.py` | matplotlib, results above | `docs/figures/paper/` |

Setup, instance isolation and reproducibility metadata: [../docs/native_runs.md](../docs/native_runs.md).
