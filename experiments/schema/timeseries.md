# `timeseries.csv` column contract

One header row, comma separated, UTF-8. One row per synchronized sample on the
original acquisition time base (do not resample before archiving; resampling for
evaluation is an explicit, documented analysis step). Empty cell = missing value.
Units are part of the column name and must match `metadata.json/channels`.

| Column | Required | Unit / values | Notes |
| --- | --- | --- | --- |
| `time_s` | yes | s | strictly increasing, from the run start (`start_time_utc`) |
| `battery_voltage_V` | yes | V | pack terminal voltage, calibrated meter preferred |
| `battery_current_A` | yes | A | positive = discharge |
| `battery_temperature_C` | yes | °C | pack sensor; record its placement in metadata |
| `water_temperature_C` | yes | °C | independent water sensor |
| `mission_phase` | yes | text | protocol phase label, e.g. `idle`, `hover`, `surge_out` |
| `thruster_<id>_command_<unit>` | ≥ 1 | `N`, `pwm_us` or `norm` | commands actually sent; one column per thruster |
| `thruster_<id>_rpm` | optional | rpm | if ESC telemetry is available |
| `depth_m` | vehicle state: ≥ 1 of these | m | positive down |
| `position_x_m`, `position_y_m`, `position_z_m` | | m | frame declared in metadata |
| `velocity_x_m_s`, `velocity_y_m_s`, `velocity_z_m_s` | | m/s | e.g. DVL, frame declared |
| `roll_deg`, `pitch_deg`, `yaw_deg` | | deg | attitude |
| `sensor_<name>_state` | ≥ 1 if sensors fitted | text | e.g. `OFF`, `IDLE`, `ACTIVE` |
| `rail_<name>_power_W` | optional | W | per-rail measurement where available |
| `soc_reference` | optional | 0–1 | only from an independently calibrated charge count |

A PWM command history is not a HoloOcean force history: converting `pwm_us` to
force requires the identified thruster/ESC map and is an analysis step, never done
silently. The checker is `tools/check_experiment_run.py`.
