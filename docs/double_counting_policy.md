# Double-counting policy

Every electrical function is counted once. A component profile lists, under `includes`,
the functions whose power is already inside its published electrical figure. When two
loads declare the same function, the run reports
`possible double counting: '<function>' provided by <a>, <b>` (in `env.warnings`, the
evidence summary and the `EnergyReport`). With `evidence: {double_counting: error}` the
configuration is rejected instead; an attached load source that would create a conflict
raises and is not attached.

| Case | How it is detected | Test |
| --- | --- | --- |
| Navigator (internal IMU, magnetometer, barometer) + separate IMU/magnetometer (e.g. VectorNav VN-100) | both declare `imu`, `magnetometer` | `test_navigator_plus_separate_imu_magnetometer_is_flagged` |
| Integrated INS/DVL (Sonardyne SPRINT-Nav Mini: DVL, IMU, magnetometer, pressure) + standalone DVL (Water Linked A50) | both declare `dvl` | `test_integrated_ins_dvl_plus_standalone_dvl_is_flagged` |
| Semantic segmentation camera + camera + compute | `SemanticSegmentationCamera` (and `RaycastSemanticLidar`) are derived simulator outputs: a component mapped to them is refused; the electrical load is the physical camera plus a compute workload | `test_semantic_camera_is_not_an_electrical_load` |
| Modem with integrated signal processing + separate compute doing the same processing | modem profiles declare `modem_signal_processing` by default; a compute component declaring it conflicts when the modem's energy source is attached with `env.attach` | `test_modem_internal_processing_plus_separate_compute_is_flagged` |

Scope and limits:

* Detection is declarative. A profile that omits `includes` cannot be checked; profiles in
  the package declare the functions their datasheets state as integrated.
* Two physically distinct devices of the same kind (two cameras, two computers) are not a
  double count and are not flagged; capability names describe functions, not device
  classes.
* HoloOcean state sensors (Pose, Velocity, Dynamics, ...) are 0 W and are refused as
  electrical loads (`holoenergy.sensor_policy`), so they can never double count a real
  navigation sensor.
