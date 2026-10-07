# Held-out validation runs

Runs assigned to `final_validation` before any model is fitted. They are used once,
after parameters, model fidelity, resampling and alignment are frozen, to compute
the L0 vs L1 vs real metrics (voltage/current/power MAE and RMSE, Wh relative error,
final SOC error, temperature MAE/RMSE, mission completion, endurance, derating and
cutoff timing). No run has been recorded yet; never place calibration cycles here.
